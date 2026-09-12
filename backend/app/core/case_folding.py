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
