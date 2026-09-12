"""Case folding is Unicode-aware on every backend (core/case_folding.py).

SQLite's built-in lower() knows ASCII only; the app shadows it with Python's
on every connection. A ``C``-locale PostgreSQL folds ASCII only too — the
PostgreSQL half (probe + compiler) is tested here once it lands.
"""

from unittest.mock import Mock

import pytest
from sqlalchemy import text

from backend.app.core import case_folding


class TestSqliteFunctions:
    def test_lower_folds_cyrillic_and_keeps_null(self):
        assert case_folding.sqlite_lower("ЛАМПА Настільна") == "лампа настільна"
        assert case_folding.sqlite_lower(None) is None

    def test_upper_folds_cyrillic(self):
        assert case_folding.sqlite_upper("ґудзик") == "ҐУДЗИК"
        assert case_folding.sqlite_upper(None) is None

    def test_non_text_passes_through(self):
        # SQLite may hand a BLOB (bytes) or a number to the function; it is not ours to fold.
        assert case_folding.sqlite_lower(b"\x00\x01") == b"\x00\x01"
        assert case_folding.sqlite_lower(5) == 5

    def test_both_names_are_registered_as_deterministic(self):
        """The registration contract, not just the functions: SQLite may only use
        an application function in an indexed expression when it is declared
        deterministic, and it shadows the built-in only under the exact name."""
        conn = Mock()

        case_folding.register_sqlite_functions(conn)

        assert [c.args for c in conn.create_function.call_args_list] == [
            ("lower", 1, case_folding.sqlite_lower),
            ("upper", 1, case_folding.sqlite_upper),
        ]
        assert [c.kwargs for c in conn.create_function.call_args_list] == [
            {"deterministic": True},
            {"deterministic": True},
        ]


@pytest.mark.asyncio
async def test_the_test_engine_lowers_unicode(test_engine):
    async with test_engine.connect() as conn:
        assert (await conn.execute(text("SELECT lower('ЛАМПА')"))).scalar() == "лампа"
        assert (await conn.execute(text("SELECT upper('лампа')"))).scalar() == "ЛАМПА"
        assert (await conn.execute(text("SELECT 'Лампа' LIKE '%' || lower('ЛАМПА') || '%'"))).scalar() == 0
        # The shape SQLAlchemy emits for ilike on SQLite: lower(col) LIKE lower(:q)
        assert (await conn.execute(text("SELECT lower('Лампа настільна') LIKE lower('%ЛАМПА%')"))).scalar() == 1
