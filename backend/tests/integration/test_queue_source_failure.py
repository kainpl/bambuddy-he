"""A bad external source fails its own job; the next job keeps moving."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Event

import pytest
from sqlalchemy import select

from backend.app.models.auto_queue import AutoQueueItem
from backend.app.models.library import LibraryFile
from backend.app.models.print_queue import PrintQueueItem
from backend.app.services import source_io
from backend.app.services.auto_queue_scheduler import AutoQueueScheduler
from backend.app.services.filament_requirements import SourceIdentity
from backend.tests.integration.test_filament_routing_dispatch import setup_source

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("failure", ["missing", "host_down", "timeout", "assignment", "claimed"])
async def test_auto_queue_skips_bad_source_and_requires_explicit_retry(
    committing_client, db_session, tmp_path, printer_factory, monkeypatch, failure
):
    source, printer, queue, mqtt = await setup_source(db_session, tmp_path, printer_factory, monkeypatch)
    path = Path(source.file_path)
    data = path.read_bytes()
    good_path = tmp_path / "healthy.3mf"
    good_path.write_bytes(data)
    healthy = LibraryFile(filename=good_path.name, file_path=str(good_path), file_size=len(data), file_type="gcode")
    db_session.add(healthy)
    await db_session.flush()
    bad = AutoQueueItem(library_file_id=source.id, target_model="P1P", position=1, plate_id=15)
    good = AutoQueueItem(library_file_id=healthy.id, target_model="P1P", position=2, plate_id=15)
    db_session.add_all([bad, good])
    await db_session.commit()
    original = SourceIdentity.of
    source_checks = []
    release = Event()
    if failure == "missing":
        path.unlink()

    def stat(file):
        if file == path:
            source_checks.append(1)
            if failure in ("assignment", "claimed") and len(source_checks) >= (4 if failure == "assignment" else 5):
                raise OSError(112, "Host is down")
        if file == path and failure == "host_down":
            raise OSError(112, "Host is down")
        if file == path and failure == "timeout":
            release.wait(10)
        return original(file)

    monkeypatch.setattr(SourceIdentity, "of", stat)
    monkeypatch.setattr(source_io, "SOURCE_IO_TIMEOUT", 0.2 if failure == "timeout" else 5)

    @asynccontextmanager
    async def session():
        yield db_session

    monkeypatch.setattr("backend.app.services.auto_queue_scheduler.async_session", session)
    scheduler = AutoQueueScheduler()
    try:
        await asyncio.wait_for(scheduler.tick(), timeout=5)
        await db_session.refresh(bad)
        await db_session.refresh(good)
        assert bad.status == "failed"
        assert bad.waiting_reason
        assert bad.assigned_to_item_id is None
        assert good.status == "assigned"
        assert len((await db_session.execute(select(PrintQueueItem))).scalars().all()) == 1
        mqtt._client.publish.assert_not_called()

        response = await committing_client.get("/api/v1/auto-queue/?status=pending,failed")
        assert response.status_code == 200, response.text
        assert [row["id"] for row in response.json()] == [bad.id]
        retry = await committing_client.post(f"/api/v1/auto-queue/{bad.id}/retry")
        assert retry.status_code == 409
    finally:
        release.set()
        while ("identity", str(path)) in source_io._running:
            await asyncio.sleep(0.001)
        monkeypatch.setattr(SourceIdentity, "of", original)
        path.write_bytes(data)

    await scheduler.tick()
    await db_session.refresh(bad)
    assert bad.status == "failed"  # File recovery alone must not silently restart a failed job.
    retry = await committing_client.post(f"/api/v1/auto-queue/{bad.id}/retry")
    assert retry.status_code == 200, retry.text
    assert retry.json()["status"] == "pending"
    assert retry.json()["waiting_reason"] is None


async def test_printer_queue_marks_missing_file_failed_and_starts_next_item(
    db_session, tmp_path, printer_factory, monkeypatch
):
    from unittest.mock import AsyncMock

    from backend.app.services.filament_policy_write import prepare_routing
    from backend.app.services.print_scheduler import PrintScheduler

    source, printer, queue, mqtt = await setup_source(db_session, tmp_path, printer_factory, monkeypatch)
    missing = LibraryFile(filename="gone.3mf", file_path=str(tmp_path / "gone.3mf"), file_size=1, file_type="gcode")
    db_session.add(missing)
    await db_session.flush()
    bad = PrintQueueItem(queue_id=queue.id, library_file_id=missing.id, position=1, plate_id=15)
    routing, plate = await prepare_routing(
        db_session, printer_id=printer.id, library_file_id=source.id, options={"plate_id": 15}
    )
    good = PrintQueueItem(
        queue_id=queue.id,
        library_file_id=source.id,
        position=2,
        plate_id=plate,
        filament_routing=routing,
        require_previous_success=True,
    )
    db_session.add_all([bad, good])
    await db_session.commit()

    @asynccontextmanager
    async def session():
        yield db_session

    monkeypatch.setattr("backend.app.services.print_scheduler.async_session", session)
    scheduler = PrintScheduler()
    monkeypatch.setattr(scheduler, "_get_bool_setting", AsyncMock(return_value=False))
    monkeypatch.setattr(scheduler, "_check_auto_drying", AsyncMock())
    monkeypatch.setattr(scheduler, "_is_printer_idle", lambda *args, **kwargs: True)
    started = []

    async def start(db, item, **kwargs):
        started.append(item.id)
        item.status = "printing"
        await db.commit()

    monkeypatch.setattr(scheduler, "_start_print", start)
    dispatched = await scheduler.check_queue()
    assert dispatched is True, good.waiting_reason
    await db_session.refresh(bad)
    await db_session.refresh(queue)
    assert bad.status == "failed" and bad.error_message
    assert bad.waiting_reason is None
    assert bad.gate_acknowledged is True
    assert queue.status == "idle" and not queue.is_paused
    assert started == [good.id]


async def test_source_failure_after_claim_releases_only_its_attempt(db_session, tmp_path, printer_factory, monkeypatch):
    from datetime import datetime

    from backend.app.services.filament_deferred import defer_claim

    source, printer, queue, mqtt = await setup_source(db_session, tmp_path, printer_factory, monkeypatch)
    started = datetime.now()
    item = PrintQueueItem(queue_id=queue.id, library_file_id=source.id, status="printing", started_at=started)
    db_session.add(item)
    await db_session.flush()
    queue.status, queue.current_item_id = "printing", item.id
    await db_session.commit()
    assert await defer_claim(db_session, item_id=item.id, started_at=started, reason="source_timeout")
    await db_session.commit()
    await db_session.refresh(item)
    await db_session.refresh(queue)
    assert item.status == "failed" and item.error_message and item.gate_acknowledged
    assert item.waiting_reason_code is None
    assert queue.status == "idle" and queue.current_item_id is None
    assert not await defer_claim(db_session, item_id=item.id, started_at=started, reason="source_timeout")


@pytest.mark.parametrize("kind", ["print_library_file", "reprint_archive"])
async def test_source_lost_between_scheduler_and_dispatch_does_not_leave_printing_claim(
    db_session, test_engine, tmp_path, printer_factory, monkeypatch, kind
):
    from datetime import datetime
    from unittest.mock import AsyncMock

    from sqlalchemy.ext.asyncio import async_sessionmaker

    from backend.app.models.archive import PrintArchive
    from backend.app.services import background_dispatch as bd
    from backend.app.services.print_scheduler import PrintScheduler

    source, printer, queue, mqtt = await setup_source(db_session, tmp_path, printer_factory, monkeypatch)
    archive = None
    if kind == "reprint_archive":
        archive = PrintArchive(
            filename=source.filename,
            file_path=source.file_path,
            file_size=source.file_size,
            status="completed",
            plate_index=15,
        )
        db_session.add(archive)
        await db_session.flush()
    item = PrintQueueItem(
        queue_id=queue.id,
        library_file_id=None if archive else source.id,
        archive_id=archive.id if archive else None,
        status="printing",
        started_at=datetime.now(),
        plate_id=15,
    )
    db_session.add(item)
    await db_session.flush()
    queue.status, queue.current_item_id = "printing", item.id
    await db_session.commit()
    Path(source.file_path).unlink()
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    monkeypatch.setattr(bd, "async_session", factory)
    monkeypatch.setattr("backend.app.services.print_scheduler.async_session", factory)
    monkeypatch.setattr("backend.app.services.print_scheduler.scheduler.acquire_stagger_slot", AsyncMock())
    monkeypatch.setattr(bd.ws_manager, "broadcast", AsyncMock())
    service = bd.BackgroundDispatchService()
    monkeypatch.setattr(service, "_strict_stagger_refuses", AsyncMock(return_value=False))
    monkeypatch.setattr(bd, "background_dispatch", service)
    await PrintScheduler()._dispatch_and_finalize(
        queue_item_id=item.id,
        printer_id=printer.id,
        printer_name=printer.name,
        printer_serial=printer.serial_number,
        dispatch_kind=kind,
        dispatch_source_id=archive.id if archive else source.id,
        dispatch_source_name=source.filename,
        options={"plate_id": 15},
        requested_by_user_id=None,
        project_id=None,
        project_line_id=None,
        job_name_short="part",
        swap_events=[],
    )
    await db_session.refresh(item)
    await db_session.refresh(queue)
    assert item.status == "failed" and item.error_message
    assert item.library_file_id == (None if archive else source.id)
    assert item.archive_id == (archive.id if archive else None)
    assert queue.status == "idle" and queue.current_item_id is None
    mqtt._client.publish.assert_not_called()
