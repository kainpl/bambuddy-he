"""Case folding is Unicode-aware on every backend — decided here, once.

Every ``Column.ilike()`` and every ``func.lower()`` / ``func.upper()`` in the
app assumes "case-insensitive" means Unicode. Two backends disagree:

- SQLite's built-in ``lower()`` folds ASCII only, and SQLAlchemy compiles
  ``ilike`` to ``lower(col) LIKE lower(:q)`` there — so ``?q=ЛАМПА`` never found
  «лампа» on the default backend. Fix: an application-defined ``lower``/``upper``
  on every connection (SQLite lets an app function shadow a built-in), backed
  by Python's ``str.lower()``. No expression index in this schema uses
  ``lower()`` (uniqueness lives in ``name_key`` columns), so no REINDEX.
- A PostgreSQL database created with ``LC_CTYPE = C`` folds ASCII only in
  ``lower()``, ``ILIKE`` and ``to_tsvector``. Fix: probe once at engine start;
  when the database cannot fold, pick a collation that can (``pg_c_utf8`` on
  17+, else ICU's ``und-x-icu``) and let the compiler render it — see
  ``pg_fold_collation`` and ``BamDudePGCompiler``. A database that folds
  natively (the bundled server, the official Docker image) compiles exactly as
  before.

Routes never re-implement any of this.
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.dialects.postgresql.base import PGCompiler
from sqlalchemy.sql import sqltypes

logger = logging.getLogger(__name__)


def sqlite_lower(value):
    """Unicode ``lower`` for SQLite; NULL stays NULL, non-text passes through.

    The passthrough is a deliberate divergence from the built-in, which
    stringifies its argument (``lower(5)`` → ``'5'``, ``lower(1e20)`` →
    ``'1.0e+20'``); Python's ``str()`` cannot reproduce SQLite's float
    formatting, so a faithful mirror is not available and guessing one would
    hand callers subtly wrong text. No caller passes non-text today (every
    ``func.lower``/``func.upper`` in the app reads a text column). Should one
    ever appear, note that the ``int`` we return can never satisfy
    ``lower(col) = :str``: SQLite does not coerce across storage classes, so the
    comparison is simply false rather than an error.
    """
    return value.lower() if isinstance(value, str) else value


def sqlite_upper(value):
    """Unicode ``upper`` for SQLite; NULL stays NULL, non-text passes through.

    Same deliberate divergence as ``sqlite_lower`` for non-text input — see
    there for why a faithful mirror of the built-in is not available and what a
    passed-through number does to a comparison.
    """
    return value.upper() if isinstance(value, str) else value


def register_sqlite_functions(dbapi_conn) -> None:
    """Shadow SQLite's ASCII-only ``lower``/``upper`` on this connection.

    ``deterministic=True`` so SQLite may use them in indexed expressions should
    one ever appear; the same function must then be registered on every
    connection that touches the file, which the ``connect`` listener guarantees.
    """
    dbapi_conn.create_function("lower", 1, sqlite_lower, deterministic=True)
    dbapi_conn.create_function("upper", 1, sqlite_upper, deterministic=True)


# Preference order. ``pg_c_utf8`` is the builtin provider's C.UTF-8 — on every
# PostgreSQL 17+ UTF-8 database, no ICU needed, Unicode simple case mapping.
# ``und-x-icu`` exists on any ICU build since 10. Nothing else is ever rendered
# into a COLLATE clause.
FOLD_COLLATIONS: tuple[str, ...] = ("pg_c_utf8", "und-x-icu")

# Process state, written by ``probe_postgres_case_folding`` only. Defaults
# describe a database that folds natively — and are what a probe that never got
# an answer leaves behind.
#
# ⚠️ SQLAlchemy's compiled-SQL cache is keyed on the statement, not on
# ``pg_fold_collation``, so a statement compiled before this value changed would
# be reused with the old text. That is correct only because the probe runs once,
# before any application query (``init_db``), and ``reinitialize_database``
# builds a fresh engine with a fresh cache. A re-probe mid-life would have to
# clear ``engine.dialect._compiled_cache`` / the engine's cache as well.
pg_native_folds: bool = True
pg_fold_collation: str | None = None


def choose_fold_collation(native: bool, available: set[str]) -> str | None:
    """The collation to fold through, or None when the database folds itself (or nothing can help)."""
    if native:
        return None
    for name in FOLD_COLLATIONS:
        if name in available:
            return name
    return None


def reset_for_tests() -> None:
    global pg_native_folds, pg_fold_collation
    pg_native_folds, pg_fold_collation = True, None


async def _verified_collation(conn) -> tuple[str | None, str | None]:
    """``(datctype, the first collation that verifiably folds)`` on a database
    that does not fold by itself.

    Trust, but verify, one candidate at a time: a collation can be listed on a
    build whose ICU is broken, so a candidate is asked to fold «Ж» before it is
    chosen — and a candidate that answers wrong, or raises, costs only its own
    turn. ``choose_fold_collation`` stays the single place that knows the
    preference order; this loop just takes the candidates off the list.
    """
    ctype = (await conn.execute(text("SELECT datctype FROM pg_database WHERE datname = current_database()"))).scalar()
    # The names are our own constants, never anything a user can reach, so they
    # are written into the statement as literals. A bound list would mean
    # ``= ANY(:names)`` — an array parameter, and this statement decides whether
    # the whole feature engages, so it must not depend on driver array handling.
    quoted = ", ".join(f"'{name}'" for name in FOLD_COLLATIONS)
    rows = await conn.execute(text(f"SELECT collname FROM pg_collation WHERE collname IN ({quoted})"))
    remaining = {r[0] for r in rows}
    while (candidate := choose_fold_collation(False, remaining)) is not None:
        remaining.discard(candidate)
        try:
            folds = bool((await conn.execute(text(f"SELECT lower('Ж' COLLATE \"{candidate}\") = 'ж'"))).scalar())
        except Exception as exc:  # noqa: BLE001 — the next candidate still deserves its turn
            logger.info("Collation %r could not be used for case folding (%s); trying the next", candidate, exc)
            # PostgreSQL aborts the transaction on a failed statement, so
            # without this the next candidate would fail too.
            await conn.rollback()
            continue
        if folds:
            return ctype, candidate
        logger.info("Collation %r exists but does not fold non-ASCII case; trying the next", candidate)
    return ctype, None


async def probe_postgres_case_folding(engine) -> None:
    """Ask the database once whether it folds Unicode; pick a collation if not.

    Runs at engine start, before the migrations (m137's backfill uses ilike).
    Must never prevent boot: any failure logs and carries on.

    Only the first question — does this database fold? — may leave the native
    defaults behind. Once the answer is measured as *no*, a later failure keeps
    it: re-opening the FTS gate on a database whose tsvectors hold unfolded
    tokens would search wrongly and silently, which is worse than searching
    ASCII-folded and saying so.
    """
    global pg_native_folds, pg_fold_collation
    ctype: str | None = None
    # Start from "no answer yet from THIS probe", so the guard in the handler
    # below means *this* call measured non-folding — a re-probe after a restore
    # must not inherit the previous database's collation when it cannot even
    # ask the first question.
    pg_native_folds, pg_fold_collation = True, None
    try:
        async with engine.connect() as conn:
            native = bool((await conn.execute(text("SELECT lower('Ж') = 'ж'"))).scalar())
            if native:
                pg_native_folds, pg_fold_collation = True, None
                return
            pg_native_folds, pg_fold_collation = False, None  # measured; stands from here on
            ctype, chosen = await _verified_collation(conn)
            pg_fold_collation = chosen
    except Exception as exc:  # noqa: BLE001 — the app must boot whatever the server says
        if not pg_native_folds:
            logger.warning(
                "The database does not fold non-ASCII case and the case-folding probe could not finish (%s); "
                "case-insensitive search folds ASCII only",
                exc,
            )
            return
        logger.warning("Case-folding probe failed (%s); assuming the database folds natively", exc)
        pg_native_folds, pg_fold_collation = True, None
        return
    if pg_fold_collation is not None:
        logger.info(
            "PostgreSQL database ctype is %r and does not fold non-ASCII case; "
            "case-insensitive search will fold through collation %r (full-text ranking is off)",
            ctype,
            pg_fold_collation,
        )
    else:
        logger.warning(
            "PostgreSQL database ctype is %r: case-insensitive search folds ASCII only, and this server offers "
            "no Unicode collation (needs PostgreSQL 17+ or an ICU build). Recreate the database with a UTF-8 "
            "locale — see docs: features/postgresql (Using an external server)",
            ctype,
        )


def _collated(sql: str) -> str:
    """``COLLATE`` binds tighter than every operator, so the operand is
    parenthesised: without it ``a || b COLLATE "c"`` collates only ``b``."""
    return f'({sql}) COLLATE "{pg_fold_collation}"'


class BamDudePGCompiler(PGCompiler):
    """Stock PostgreSQL SQL, except that when the database cannot fold case the
    case-insensitive operators go through ``pg_fold_collation``. With the
    collation unset every method defers to the stock compiler."""

    def _like_through_collation(self, binary, negate: bool, **kw) -> str:
        escape = binary.modifiers.get("escape", None)
        left = _collated(self.process(binary.left, **kw))
        right = _collated(self.process(binary.right, **kw))
        op = "NOT LIKE" if negate else "LIKE"
        return f"lower({left}) {op} lower({right})" + (
            " ESCAPE " + self.render_literal_value(escape, sqltypes.STRINGTYPE) if escape is not None else ""
        )

    def visit_ilike_op_binary(self, binary, operator, **kw):
        if pg_fold_collation is None:
            return super().visit_ilike_op_binary(binary, operator, **kw)
        return self._like_through_collation(binary, negate=False, **kw)

    def visit_not_ilike_op_binary(self, binary, operator, **kw):
        if pg_fold_collation is None:
            return super().visit_not_ilike_op_binary(binary, operator, **kw)
        return self._like_through_collation(binary, negate=True, **kw)

    def _fold_func(self, name: str, fn, **kw):
        # ⚠️ Never call self.visit_function() from here: it dispatches back to
        # visit_<name>_func and would recurse. Render the stock form by hand.
        args = [self.process(c, **kw) for c in fn.clauses]
        if pg_fold_collation is None or len(args) != 1:
            return f"{name}({', '.join(args)})"
        return f"{name}({_collated(args[0])})"

    def visit_lower_func(self, fn, **kw):
        return self._fold_func("lower", fn, **kw)

    def visit_upper_func(self, fn, **kw):
        return self._fold_func("upper", fn, **kw)
