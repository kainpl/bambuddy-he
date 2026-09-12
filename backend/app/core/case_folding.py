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

# Process state, written by ``probe_postgres`` only. Defaults describe a
# database that folds natively — and are what a failed probe leaves behind.
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


async def probe_postgres(engine) -> None:
    """Ask the database once whether it folds Unicode; pick a collation if not.

    Runs at engine start, before the migrations (m137's backfill uses ilike).
    Must never prevent boot: any failure logs and keeps the native defaults.
    """
    global pg_native_folds, pg_fold_collation
    try:
        async with engine.connect() as conn:
            native = bool((await conn.execute(text("SELECT lower('Ж') = 'ж'"))).scalar())
            if native:
                pg_native_folds, pg_fold_collation = True, None
                return
            ctype = (
                await conn.execute(text("SELECT datctype FROM pg_database WHERE datname = current_database()"))
            ).scalar()
            rows = await conn.execute(
                text("SELECT collname FROM pg_collation WHERE collname = ANY(:names)"),
                {"names": list(FOLD_COLLATIONS)},
            )
            available = {r[0] for r in rows}
            chosen = choose_fold_collation(False, available)
            if chosen is not None:
                # Trust, but verify: an ICU collation can exist on a build whose ICU is broken.
                ok = (await conn.execute(text(f"SELECT lower('Ж' COLLATE \"{chosen}\") = 'ж'"))).scalar()
                if not ok:
                    chosen = None
    except Exception as exc:  # noqa: BLE001 — the app must boot whatever the server says
        logger.warning("Case-folding probe failed (%s); assuming the database folds natively", exc)
        pg_native_folds, pg_fold_collation = True, None
        return
    pg_native_folds, pg_fold_collation = False, chosen
    if chosen is not None:
        logger.info(
            "PostgreSQL database ctype is %r and does not fold non-ASCII case; "
            "case-insensitive search will fold through collation %r (full-text ranking is off)",
            ctype,
            chosen,
        )
    else:
        logger.warning(
            "PostgreSQL database ctype is %r: case-insensitive search folds ASCII only, and this server offers "
            "no Unicode collation (needs PostgreSQL 17+ or an ICU build). Recreate the database with a UTF-8 "
            "locale — see docs: features/postgresql (Using an external server)",
            ctype,
        )


def _collated(sql: str) -> str:
    return f'{sql} COLLATE "{pg_fold_collation}"'


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
