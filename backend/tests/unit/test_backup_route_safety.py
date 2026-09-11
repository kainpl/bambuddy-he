"""A rejected/failed restore must keep the previous database's key and identity."""

import asyncio
import io
import sqlite3
import zipfile
from contextlib import closing
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException, UploadFile

from backend.app.api.routes import settings as route


def upload(tmp_path, *, damaged=False):
    source = tmp_path / "source.db"
    if damaged:
        source.write_bytes(b"corrupt")
    else:
        with closing(sqlite3.connect(source)) as db:
            db.executescript("CREATE TABLE printers(id INTEGER PRIMARY KEY); CREATE TABLE settings(key TEXT);")
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.write(source, "bamdude.db")
        archive.writestr(".mfa_encryption_key", b"backup-key")
        archive.writestr(".install_id", b"backup-identity")
        archive.writestr("zigbee/zigbee.db", b"backup-network")
    payload.seek(0)
    return UploadFile(file=payload, filename="backup.zip")


@pytest.mark.asyncio
async def test_corrupt_backup_is_rejected_before_service_or_database_changes(tmp_path, monkeypatch):
    stop = AsyncMock()
    monkeypatch.setattr(
        "backend.app.services.virtual_printer.virtual_printer_manager", SimpleNamespace(is_enabled=True, configure=stop)
    )
    close = AsyncMock()
    monkeypatch.setattr("backend.app.core.database.close_all_connections", close)
    with pytest.raises(HTTPException) as caught:
        await route.restore_backup(file=upload(tmp_path, damaged=True), db=AsyncMock(), _=None)
    assert caught.value.status_code == 400
    stop.assert_not_awaited()
    close.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("previous", [None, b"previous-key"])
@pytest.mark.parametrize("cancel", [False, True])
async def test_failed_database_swap_restores_previous_key_and_keeps_identity(tmp_path, monkeypatch, previous, cancel):
    live = tmp_path / "live"
    (live / "zigbee").mkdir(parents=True)
    key = live / ".mfa_encryption_key"
    if previous is not None:
        key.write_bytes(previous)
    (live / ".install_id").write_bytes(b"previous-identity")
    (live / "zigbee/zigbee.db").write_bytes(b"previous-network")
    monkeypatch.setenv("DATA_DIR", str(live))
    monkeypatch.setattr(route.app_settings, "base_dir", live)
    monkeypatch.setattr("backend.app.core.db_dialect.is_sqlite", lambda: False)
    monkeypatch.setattr(
        "backend.app.services.virtual_printer.virtual_printer_manager", SimpleNamespace(is_enabled=False)
    )
    monkeypatch.setattr("backend.app.services.print_scheduler.scheduler", SimpleNamespace(stop=Mock()))
    monkeypatch.setattr(
        "backend.app.services.smart_plug_manager.smart_plug_manager", SimpleNamespace(stop_scheduler=Mock())
    )
    monkeypatch.setattr(
        "backend.app.services.notification_service.notification_service", SimpleNamespace(stop_digest_scheduler=Mock())
    )
    monkeypatch.setattr(
        "backend.app.services.background_dispatch.background_dispatch", SimpleNamespace(stop=AsyncMock())
    )
    monkeypatch.setattr("backend.app.core.database.close_all_connections", AsyncMock())

    async def failed_import(*args):
        assert key.read_bytes() == b"backup-key"
        raise asyncio.CancelledError if cancel else RuntimeError("injected database failure")

    monkeypatch.setattr("backend.app.core.db_portable.import_sqlite_to_postgres", failed_import)
    session = AsyncMock()
    if cancel:
        with pytest.raises(asyncio.CancelledError):
            await route.restore_backup(file=upload(tmp_path), db=session, _=None)
    else:
        response = await route.restore_backup(file=upload(tmp_path), db=session, _=None)
        assert response.status_code == 500
    session.close.assert_awaited_once()
    assert (key.read_bytes() if key.exists() else None) == previous
    assert (live / ".install_id").read_bytes() == b"previous-identity"
    assert (live / "zigbee/zigbee.db").read_bytes() == b"previous-network"
    assert not list(live.glob(".mfa-restore-*"))


@pytest.mark.asyncio
async def test_zip_write_failure_preserves_previous_backup(tmp_path, monkeypatch):
    live, output = tmp_path / "live", tmp_path / "backups"
    live.mkdir()
    output.mkdir()
    monkeypatch.setenv("DATA_DIR", str(live))
    monkeypatch.setattr(route.app_settings, "base_dir", live)
    monkeypatch.setattr(route.app_settings, "plate_calibration_dir", live / "plate_calibration")
    monkeypatch.setattr(route, "datetime", SimpleNamespace(now=lambda: datetime(2026, 9, 11)))

    async def dump(engine, metadata, destination):
        destination.write_bytes(b"synthetic database payload")

    monkeypatch.setattr("backend.app.core.db_portable.dump_to_sqlite", dump)
    path, _ = await route.create_backup_zip(output)
    previous = path.read_bytes()

    def fail(*args, **kwargs):
        raise OSError("injected ZIP write failure")

    monkeypatch.setattr(zipfile.ZipFile, "write", fail)
    with pytest.raises(OSError, match="injected"):
        await route.create_backup_zip(output)
    assert path.read_bytes() == previous
    assert list(output.iterdir()) == [path]
