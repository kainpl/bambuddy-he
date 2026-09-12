"""Case folding is Unicode-aware on every backend (core/case_folding.py).

SQLite's built-in lower() knows ASCII only; the app shadows it with Python's
on every connection. A ``C``-locale PostgreSQL folds ASCII only too; there a
probe picks a collation and the compiler renders it — see the tests below.
"""

import pytest
from sqlalchemy import text

from backend.app.core import case_folding


class TestSqliteFunctions:
    def test_lower_folds_cyrillic_and_keeps_null(self):
        assert case_folding.sqlite_lower("ЛАМПА Настільна") == "лампа настільна"
        assert case_folding.sqlite_lower(None) is None

    def test_upper_folds_cyrillic(self):
        assert case_folding.sqlite_upper("ґудзик") == "ҐУДЗИК"

    def test_non_text_passes_through(self):
        # SQLite may hand a BLOB (bytes) or a number to the function; it is not ours to fold.
        assert case_folding.sqlite_lower(b"\x00\x01") == b"\x00\x01"
        assert case_folding.sqlite_lower(5) == 5


@pytest.mark.asyncio
async def test_the_test_engine_lowers_unicode(test_engine):
    async with test_engine.connect() as conn:
        assert (await conn.execute(text("SELECT lower('ЛАМПА')"))).scalar() == "лампа"
        assert (await conn.execute(text("SELECT upper('лампа')"))).scalar() == "ЛАМПА"
        assert (await conn.execute(text("SELECT 'Лампа' LIKE '%' || lower('ЛАМПА') || '%'"))).scalar() == 0
        # The shape SQLAlchemy emits for ilike on SQLite: lower(col) LIKE lower(:q)
        assert (await conn.execute(text("SELECT lower('Лампа настільна') LIKE lower('%ЛАМПА%')"))).scalar() == 1
