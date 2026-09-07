"""DATABASE_URL has three states; the bundled-PostgreSQL state derives a fixed
local URL from files under DATA_DIR/postgres so the engine can be created at
import time (core/config.py)."""

import os
import stat
import sys

import pytest

from backend.app.core import config


class TestClassifyDatabaseUrl:
    def test_empty_or_missing_means_sqlite(self):
        assert config.classify_database_url(None) == (False, None)
        assert config.classify_database_url("") == (False, None)
        assert config.classify_database_url("   ") == (False, None)

    @pytest.mark.parametrize("raw", ["embedded", "EMBEDDED", " embedded ", "embedded://"])
    def test_embedded_in_any_spelling(self, raw):
        assert config.classify_database_url(raw) == (True, None)

    def test_a_postgresql_url_is_external(self):
        url = "postgresql+asyncpg://u:p@h:5432/db"
        assert config.classify_database_url(url) == (False, url)

    def test_anything_else_is_refused_with_a_readable_message(self):
        with pytest.raises(RuntimeError) as exc:
            config.classify_database_url("mysql://x")
        assert "DATABASE_URL must be empty" in str(exc.value)
        assert "'mysql'" in str(exc.value)

    def test_the_message_never_echoes_credentials(self):
        with pytest.raises(RuntimeError) as exc:
            config.classify_database_url("garbage://user:secret@host/db")
        assert "secret" not in str(exc.value)


class TestEmbeddedPaths:
    def test_data_directory_is_versioned_by_the_bundled_major(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "_embedded_pg_major", lambda: "18")
        pgdata, password_file = config._embedded_pg_paths(tmp_path)
        assert pgdata == tmp_path / "postgres" / "18"
        assert password_file == tmp_path / "postgres" / "password"

    def test_password_is_created_once_and_reused(self, tmp_path):
        pw_file = tmp_path / "postgres" / "password"
        first = config._ensure_embedded_password(pw_file)
        second = config._ensure_embedded_password(pw_file)
        assert first == second
        assert pw_file.read_text(encoding="utf-8").strip() == first
        assert len(first) >= 24
        # URL-safe: it is embedded in the SQLAlchemy URL verbatim
        assert all(c.isalnum() or c in "-_" for c in first)

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes")
    def test_password_file_is_owner_only(self, tmp_path):
        pw_file = tmp_path / "postgres" / "password"
        config._ensure_embedded_password(pw_file)
        assert stat.S_IMODE(pw_file.stat().st_mode) == 0o600

    def test_url_carries_user_password_host_port_and_database(self, tmp_path):
        url = config._embedded_pg_url(tmp_path, 6432)
        password = (tmp_path / "postgres" / "password").read_text(encoding="utf-8").strip()
        assert url == f"postgresql+asyncpg://bamdude:{password}@127.0.0.1:6432/bamdude"


class TestEmbeddedPort:
    def test_env_pins_the_port(self, tmp_path, monkeypatch):
        monkeypatch.setenv("EMBEDDED_PG_PORT", "6432")
        assert config._embedded_pg_port_for(tmp_path) == 6432
        assert not (tmp_path / "postgres" / "port").exists()

    def test_without_env_a_free_port_is_chosen_once_and_remembered(self, tmp_path, monkeypatch):
        monkeypatch.delenv("EMBEDDED_PG_PORT", raising=False)
        first = config._embedded_pg_port_for(tmp_path)
        assert 1024 < first < 65536
        assert (tmp_path / "postgres" / "port").read_text(encoding="utf-8").strip() == str(first)
        assert config._embedded_pg_port_for(tmp_path) == first

    def test_a_remembered_port_wins_over_a_new_choice_but_not_over_env(self, tmp_path, monkeypatch):
        (tmp_path / "postgres").mkdir()
        (tmp_path / "postgres" / "port").write_text("55555" + os.linesep, encoding="utf-8")
        monkeypatch.delenv("EMBEDDED_PG_PORT", raising=False)
        assert config._embedded_pg_port_for(tmp_path) == 55555
        monkeypatch.setenv("EMBEDDED_PG_PORT", "6432")
        assert config._embedded_pg_port_for(tmp_path) == 6432
