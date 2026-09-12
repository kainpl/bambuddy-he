"""Case folding is Unicode-aware on every backend (core/case_folding.py).

SQLite's built-in lower() knows ASCII only; the app shadows it with Python's
on every connection. A ``C``-locale PostgreSQL folds ASCII only too: it is
probed once at boot, and when it cannot fold, ``ilike``/``lower``/``upper``
compile through a collation that can — tested here without a server, because
the compiler is pure text.
"""

import logging
from unittest.mock import Mock

import pytest
from sqlalchemy import Column, MetaData, String, Table, func, select, text
from sqlalchemy.dialects import postgresql

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


class TestChooser:
    def test_native_needs_no_collation(self):
        assert case_folding.choose_fold_collation(True, {"pg_c_utf8", "und-x-icu"}) is None

    def test_prefers_the_builtin_over_icu(self):
        assert case_folding.choose_fold_collation(False, {"und-x-icu", "pg_c_utf8"}) == "pg_c_utf8"

    def test_falls_back_to_icu(self):
        assert case_folding.choose_fold_collation(False, {"und-x-icu"}) == "und-x-icu"

    def test_nothing_available(self):
        assert case_folding.choose_fold_collation(False, set()) is None


class _FakeResult:
    def __init__(self, value=None, rows=()):
        self._value = value
        self._rows = rows

    def scalar(self):
        return self._value

    def __iter__(self):
        return iter(self._rows)


class _FakeEngine:
    """Just enough engine for ``probe_postgres_case_folding``: ``connect()`` as
    an async context manager, ``execute()`` answering by the SQL it is handed."""

    def __init__(
        self,
        *,
        folds: bool,
        collations: tuple[str, ...] = (),
        collation_folds: bool = True,
        verify_raises: tuple[str, ...] = (),
        fail=None,
        fail_on: str | None = None,
    ):
        self._folds = folds
        self._collations = collations
        self._collation_folds = collation_folds
        self._verify_raises = verify_raises
        self._fail = fail
        self._fail_on = fail_on
        self.statements: list[str] = []
        self.rollbacks = 0

    def connect(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def rollback(self):
        self.rollbacks += 1

    async def execute(self, stmt, params=None):
        sql = str(stmt)
        self.statements.append(sql)
        if self._fail is not None:
            raise self._fail
        if self._fail_on is not None and self._fail_on in sql:
            raise RuntimeError(f"the server refused a statement mentioning {self._fail_on}")
        if "COLLATE" in sql:  # before the bare probe: this statement also contains lower('Ж')
            name = next(c for c in case_folding.FOLD_COLLATIONS if f'"{c}"' in sql)
            if name in self._verify_raises:
                raise RuntimeError(f"could not open collator for locale {name}")
            return _FakeResult(value=self._collation_folds)
        if "lower('Ж')" in sql:
            return _FakeResult(value=self._folds)
        if "datctype" in sql:
            return _FakeResult(value="C")
        if "pg_collation" in sql:
            # The lookup carries the two names as literals — no bound array.
            assert "ANY" not in sql and ":names" not in sql, sql
            assert all(f"'{c}'" in sql for c in case_folding.FOLD_COLLATIONS), sql
            return _FakeResult(rows=[(c,) for c in self._collations])
        raise AssertionError(f"the probe asked something unexpected: {sql!r}")


class TestProbe:
    def setup_method(self):
        case_folding.reset_for_tests()

    def teardown_method(self):
        case_folding.reset_for_tests()

    @pytest.mark.asyncio
    async def test_a_folding_database_is_left_alone(self):
        engine = _FakeEngine(folds=True, collations=("pg_c_utf8",))

        await case_folding.probe_postgres_case_folding(engine)

        assert (case_folding.pg_native_folds, case_folding.pg_fold_collation) == (True, None)
        assert len(engine.statements) == 1, "one question is enough when the answer is yes"

    @pytest.mark.asyncio
    async def test_a_c_locale_database_picks_the_builtin_collation(self):
        engine = _FakeEngine(folds=False, collations=("pg_c_utf8", "und-x-icu"))

        await case_folding.probe_postgres_case_folding(engine)

        assert (case_folding.pg_native_folds, case_folding.pg_fold_collation) == (False, "pg_c_utf8")

    @pytest.mark.asyncio
    async def test_only_icu_available(self):
        engine = _FakeEngine(folds=False, collations=("und-x-icu",))

        await case_folding.probe_postgres_case_folding(engine)

        assert (case_folding.pg_native_folds, case_folding.pg_fold_collation) == (False, "und-x-icu")

    @pytest.mark.asyncio
    async def test_a_collation_that_does_not_actually_fold_is_rejected(self, caplog):
        """The collation is verified, not just looked up — an ICU collation can
        exist on a build whose ICU is broken, and rendering it would be worse
        than leaving ILIKE alone."""
        engine = _FakeEngine(folds=False, collations=("und-x-icu",), collation_folds=False)

        with caplog.at_level(logging.WARNING, logger="backend.app.core.case_folding"):
            await case_folding.probe_postgres_case_folding(engine)

        assert (case_folding.pg_native_folds, case_folding.pg_fold_collation) == (False, None)
        assert "no Unicode collation" in caplog.text

    @pytest.mark.asyncio
    async def test_no_collation_at_all_names_the_cure(self, caplog):
        engine = _FakeEngine(folds=False)

        with caplog.at_level(logging.WARNING, logger="backend.app.core.case_folding"):
            await case_folding.probe_postgres_case_folding(engine)

        assert (case_folding.pg_native_folds, case_folding.pg_fold_collation) == (False, None)
        assert "Recreate the database with a UTF-8" in caplog.text

    @pytest.mark.asyncio
    async def test_a_candidate_that_raises_costs_only_its_own_turn(self, caplog):
        """A broken ICU collation errors instead of answering. That is one
        candidate's problem, not the probe's: the next one still gets asked, and
        because PostgreSQL aborts the transaction on a failed statement, the
        rollback in between is what makes the second question possible."""
        engine = _FakeEngine(folds=False, collations=("pg_c_utf8", "und-x-icu"), verify_raises=("pg_c_utf8",))

        with caplog.at_level(logging.INFO, logger="backend.app.core.case_folding"):
            await case_folding.probe_postgres_case_folding(engine)

        assert (case_folding.pg_native_folds, case_folding.pg_fold_collation) == (False, "und-x-icu")
        assert engine.rollbacks == 1
        assert "pg_c_utf8" in caplog.text and "trying the next" in caplog.text

    @pytest.mark.asyncio
    async def test_every_candidate_raising_leaves_no_collation_but_keeps_the_answer(self, caplog):
        engine = _FakeEngine(
            folds=False, collations=("pg_c_utf8", "und-x-icu"), verify_raises=("pg_c_utf8", "und-x-icu")
        )

        with caplog.at_level(logging.WARNING, logger="backend.app.core.case_folding"):
            await case_folding.probe_postgres_case_folding(engine)

        assert (case_folding.pg_native_folds, case_folding.pg_fold_collation) == (False, None)
        assert "Recreate the database with a UTF-8" in caplog.text

    @pytest.mark.asyncio
    async def test_a_failure_after_the_answer_never_claims_the_database_folds(self, caplog):
        """Measured non-folding stands. Collapsing to the native defaults here
        would re-open the FTS gate on a database whose tsvectors hold unfolded
        tokens — searching wrongly and silently."""
        engine = _FakeEngine(folds=False, collations=("pg_c_utf8",), fail_on="datctype")

        with caplog.at_level(logging.WARNING, logger="backend.app.core.case_folding"):
            await case_folding.probe_postgres_case_folding(engine)

        assert (case_folding.pg_native_folds, case_folding.pg_fold_collation) == (False, None)
        assert "could not finish" in caplog.text
        assert "folds natively" not in caplog.text

    @pytest.mark.asyncio
    async def test_a_failing_probe_never_prevents_boot(self, caplog):
        """Whatever the server says — an old version, a permission error, a
        dropped connection — the app boots with the native defaults. Only the
        first question may end here: it never got an answer at all."""
        engine = _FakeEngine(folds=False, fail=RuntimeError("terminating connection due to administrator command"))

        with caplog.at_level(logging.WARNING, logger="backend.app.core.case_folding"):
            await case_folding.probe_postgres_case_folding(engine)

        assert (case_folding.pg_native_folds, case_folding.pg_fold_collation) == (True, None)
        assert "probe failed" in caplog.text

    @pytest.mark.asyncio
    async def test_a_reprobe_that_cannot_ask_inherits_nothing(self):
        """``reinitialize_database`` probes again after a restore. A call that
        never gets its first answer must land on the defaults, not keep the
        previous database's collation."""
        case_folding.pg_native_folds, case_folding.pg_fold_collation = False, "pg_c_utf8"
        engine = _FakeEngine(folds=False, fail=RuntimeError("server closed the connection unexpectedly"))

        await case_folding.probe_postgres_case_folding(engine)

        assert (case_folding.pg_native_folds, case_folding.pg_fold_collation) == (True, None)


def _pg_dialect():
    d = postgresql.asyncpg.dialect()
    d.statement_compiler = case_folding.BamDudePGCompiler
    return d


def _compile(stmt) -> str:
    return str(stmt.compile(dialect=_pg_dialect(), compile_kwargs={"literal_binds": True}))


_t = Table("t", MetaData(), Column("name", String), Column("notes", String))


class TestCompiler:
    def setup_method(self):
        case_folding.reset_for_tests()

    def teardown_method(self):
        case_folding.reset_for_tests()

    def test_native_database_compiles_as_stock(self):
        case_folding.pg_native_folds, case_folding.pg_fold_collation = True, None
        sql = _compile(select(_t.c.name).where(_t.c.name.ilike("%лампа%")))
        assert "ILIKE" in sql and "COLLATE" not in sql
        sql = _compile(select(func.lower(_t.c.name)))
        assert sql.strip().startswith("SELECT lower(t.name)")

    def test_the_native_form_is_byte_identical_to_the_stock_compiler(self):
        """``_fold_func`` renders the stock one-argument form by hand (calling
        ``visit_function`` from inside ``visit_lower_func`` would recurse), so
        drift from what stock PostgreSQL emits has to be caught by comparison,
        not by eye."""
        case_folding.pg_native_folds, case_folding.pg_fold_collation = True, None
        stock = postgresql.asyncpg.dialect()
        for stmt in (
            select(func.lower(_t.c.name)),
            select(func.upper(_t.c.name)),
            select(func.lower(_t.c.name, _t.c.name)),
            select(func.lower(_t.c.name + _t.c.notes)),
            select(_t.c.name).where(_t.c.name.ilike("%лампа%")),
            select(_t.c.name).where(_t.c.name.not_ilike("50!%", escape="!")),
        ):
            assert _compile(stmt) == str(stmt.compile(dialect=stock, compile_kwargs={"literal_binds": True}))

    def test_ilike_renders_the_collation(self):
        case_folding.pg_native_folds, case_folding.pg_fold_collation = False, "pg_c_utf8"
        sql = _compile(select(_t.c.name).where(_t.c.name.ilike("%лампа%")))
        assert 'lower((t.name) COLLATE "pg_c_utf8") LIKE lower((\'%лампа%\') COLLATE "pg_c_utf8")' in sql

    def test_the_collated_operand_is_parenthesised(self):
        """COLLATE binds tighter than every operator: without the parentheses
        ``lower(t.name || t.notes COLLATE "c")`` collates ``t.notes`` alone and
        folds half the expression."""
        case_folding.pg_native_folds, case_folding.pg_fold_collation = False, "pg_c_utf8"
        assert 'lower((t.name || t.notes) COLLATE "pg_c_utf8")' in _compile(select(func.lower(_t.c.name + _t.c.notes)))

    def test_the_parameterised_shape_casts_before_collating(self):
        """Without ``literal_binds`` — the shape the app actually sends. asyncpg's
        dialect renders the parameter as ``$1::VARCHAR``, and that cast is what
        gives COLLATE a typed expression to apply to."""
        case_folding.pg_native_folds, case_folding.pg_fold_collation = False, "pg_c_utf8"
        sql = str(select(_t.c.name).where(_t.c.name.ilike("%лампа%")).compile(dialect=_pg_dialect()))
        assert 'lower((t.name) COLLATE "pg_c_utf8") LIKE lower(($1::VARCHAR) COLLATE "pg_c_utf8")' in sql

    def test_not_ilike_keeps_escape(self):
        case_folding.pg_native_folds, case_folding.pg_fold_collation = False, "pg_c_utf8"
        sql = _compile(select(_t.c.name).where(_t.c.name.not_ilike("50!%", escape="!")))
        assert "NOT LIKE" in sql and "ESCAPE '!'" in sql and 'COLLATE "pg_c_utf8"' in sql

    def test_lower_and_upper_render_the_collation(self):
        case_folding.pg_native_folds, case_folding.pg_fold_collation = False, "und-x-icu"
        assert 'lower((t.name) COLLATE "und-x-icu")' in _compile(select(func.lower(_t.c.name)))
        assert 'upper((t.name) COLLATE "und-x-icu")' in _compile(select(func.upper(_t.c.name)))

    def test_other_arities_are_untouched(self):
        case_folding.pg_native_folds, case_folding.pg_fold_collation = False, "pg_c_utf8"
        sql = _compile(select(func.lower(_t.c.name, _t.c.name)))
        assert "COLLATE" not in sql


@pytest.mark.asyncio
async def test_archives_fts_branch_needs_native_folding(monkeypatch):
    # routes/archives.py takes the tsvector branch only when PostgreSQL folds
    # natively; a C-locale database uses the ilike branch the compiler fixes.
    from backend.app.api.routes import archives as archives_route

    monkeypatch.setattr(archives_route, "is_postgres", lambda: True)
    monkeypatch.setattr(case_folding, "pg_native_folds", False)
    assert archives_route._use_fts_search() is False
    monkeypatch.setattr(case_folding, "pg_native_folds", True)
    assert archives_route._use_fts_search() is True


class _RecordingDB:
    """Records the SQL a route executes; every result is empty."""

    def __init__(self):
        self.statements: list[str] = []

    async def execute(self, stmt, params=None):
        self.statements.append(str(stmt))
        return _EmptyResult()


class _EmptyResult:
    def fetchall(self):
        return []

    def scalars(self):
        return self

    def all(self):
        return []


@pytest.mark.asyncio
async def test_a_non_folding_postgres_search_never_asks_an_index(monkeypatch):
    """With the FTS gate shut there is no index to ask: the tsvector holds
    unfolded tokens and ``archive_fts`` is SQLite's table. Asking anyway would
    not just waste a round trip — a failing statement aborts the PostgreSQL
    transaction, so the ilike fallback in the same handler would fail too."""
    from backend.app.api.routes import archives as archives_route

    monkeypatch.setattr(archives_route, "is_postgres", lambda: True)
    monkeypatch.setattr(case_folding, "pg_native_folds", False)
    db = _RecordingDB()

    assert await archives_route.search_archives(q="лампа", db=db, auth_result=(None, True)) == []

    assert len(db.statements) == 1, db.statements
    sql = db.statements[0]
    assert "archive_fts" not in sql and "to_tsquery" not in sql
    assert "FROM print_archives" in sql and "LIKE" in sql.upper()


@pytest.mark.asyncio
async def test_the_sqlite_search_still_goes_through_fts5(monkeypatch):
    """The symmetric case, so the gate cannot quietly divert the default backend:
    SQLite has a real ``archive_fts`` index and its own folded ``lower``, so it
    keeps using it."""
    from backend.app.api.routes import archives as archives_route

    monkeypatch.setattr(archives_route, "is_postgres", lambda: False)
    db = _RecordingDB()

    assert await archives_route.search_archives(q="лампа", db=db, auth_result=(None, True)) == []

    assert len(db.statements) == 1, db.statements
    sql = db.statements[0]
    assert "archive_fts" in sql and "to_tsquery" not in sql
