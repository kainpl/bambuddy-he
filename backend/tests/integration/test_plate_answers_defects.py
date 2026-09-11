"""The two answers to a full plate carry what came out bad on it.

The finished row waits for the operator (services/plate_hold); at that moment
the card and Telegram know exactly WHICH print is on the plate, so the defects
travel with the answer under the same permission and are written only to that
print. A body-less answer is the old behaviour, untouched.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from backend.app.models.archive import PrintArchive
from backend.app.models.archive_part import PrintArchivePart
from backend.app.models.print_queue import PrintQueueItem
from backend.app.models.printer_queue import PrinterQueue

pytestmark = pytest.mark.integration

ROUTES_PM = "backend.app.api.routes.printers.printer_manager"


async def _finished_on(db_session, printer, parts: dict[str, int]) -> tuple[PrintArchive, PrintQueueItem]:
    archive = PrintArchive(
        printer_id=printer.id,
        filename="done.3mf",
        print_name="Done",
        file_path="x/done.3mf",
        file_size=1,
        status="completed",
        quantity=sum(parts.values()),
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add(archive)
    await db_session.flush()
    for name, qty in parts.items():
        db_session.add(PrintArchivePart(archive_id=archive.id, name=name, name_key=name.lower(), quantity=qty))
    queue = PrinterQueue(id=printer.id, printer_id=printer.id, status="idle")
    db_session.add(queue)
    await db_session.flush()
    row = PrintQueueItem(
        queue_id=queue.id,
        archive_id=archive.id,
        status="completed",
        completed_at=datetime.now(timezone.utc),
        # A library-backed source: Repeat's own file-existence guard
        # (services/plate_hold.answer_by_repeating) only applies to a row whose
        # ONLY source is its archive — not what this fixture is about.
        library_file_id=1,
    )
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(archive)
    return archive, row


async def _finished_flat(db_session, printer, quantity: int) -> tuple[PrintArchive, PrintQueueItem]:
    """Same as ``_finished_on`` but with NO part rows — the print that exercises
    ``record_defects``'s flat ``defective_count`` path (a print WITH part rows
    ignores a flat write by design; see archive_defects.py)."""
    archive = PrintArchive(
        printer_id=printer.id,
        filename="done.3mf",
        print_name="Done",
        file_path="x/done.3mf",
        file_size=1,
        status="completed",
        quantity=quantity,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add(archive)
    await db_session.flush()
    queue = PrinterQueue(id=printer.id, printer_id=printer.id, status="idle")
    db_session.add(queue)
    await db_session.flush()
    row = PrintQueueItem(
        queue_id=queue.id,
        archive_id=archive.id,
        status="completed",
        completed_at=datetime.now(timezone.utc),
        library_file_id=1,
    )
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(archive)
    return archive, row


def _finished_printer():
    """The route's own readiness reads: connected, at FINISH, gate armed."""
    return patch.multiple(
        ROUTES_PM,
        ensure_fresh_connection_for_printer=AsyncMock(return_value=True),
        is_connected=MagicMock(return_value=True),
        get_status=MagicMock(return_value=SimpleNamespace(state="FINISH")),
        set_awaiting_plate_clear=MagicMock(),
        is_awaiting_plate_clear=MagicMock(return_value=True),
    )


@pytest.mark.asyncio
async def test_the_waiting_print_is_readable_with_its_parts(async_client, printer_factory, db_session):
    printer = await printer_factory()
    archive, _row = await _finished_on(db_session, printer, {"lid": 2, "base": 4})

    resp = await async_client.get(f"/api/v1/printers/{printer.id}/waiting-print")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["archive_id"] == archive.id and body["status"] == "completed" and body["quantity"] == 6
    assert {p["name_key"]: p["quantity"] for p in body["parts"]} == {"lid": 2, "base": 4}


@pytest.mark.asyncio
async def test_nothing_waiting_is_a_404(async_client, printer_factory):
    printer = await printer_factory()
    resp = await async_client.get(f"/api/v1/printers/{printer.id}/waiting-print")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "No finished print is waiting on this printer"


@pytest.mark.asyncio
async def test_clear_plate_with_defects_writes_them_and_then_clears(async_client, printer_factory, db_session):
    printer = await printer_factory()
    archive, row = await _finished_on(db_session, printer, {"lid": 2, "base": 4})
    lid = (await db_session.execute(select(PrintArchivePart).where(PrintArchivePart.name_key == "lid"))).scalar_one()

    with _finished_printer():
        resp = await async_client.post(
            f"/api/v1/printers/{printer.id}/clear-plate",
            json={"defects": {"parts": [{"id": lid.id, "defective": 1}]}},
        )

    assert resp.status_code == 200, resp.text
    # Read the ids BEFORE expiring: an expired attribute reloads itself, and a
    # lazy load from plain async code is a MissingGreenlet, not a query.
    archive_id, row_id = archive.id, row.id
    db_session.expire_all()
    assert (await db_session.get(PrintArchive, archive_id)).defective_count == 1
    assert await db_session.get(PrintQueueItem, row_id) is None, "the row was answered — cleared — after the write"


@pytest.mark.asyncio
async def test_repeat_print_with_defects_writes_them_and_then_re_arms(async_client, printer_factory, db_session):
    printer = await printer_factory()
    archive, row = await _finished_flat(db_session, printer, 2)

    with _finished_printer():
        resp = await async_client.post(
            f"/api/v1/printers/{printer.id}/repeat-print", json={"defects": {"defective_count": 2}}
        )

    assert resp.status_code == 200, resp.text
    archive_id, row_id = archive.id, row.id
    db_session.expire_all()
    assert (await db_session.get(PrintArchive, archive_id)).defective_count == 2
    assert (await db_session.get(PrintQueueItem, row_id)).status == "pending", "re-armed"


@pytest.mark.asyncio
async def test_defects_with_nothing_waiting_are_refused_and_nothing_is_cleared(async_client, printer_factory):
    printer = await printer_factory()
    with _finished_printer():
        resp = await async_client.post(
            f"/api/v1/printers/{printer.id}/clear-plate", json={"defects": {"defective_count": 1}}
        )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "No finished print is waiting on this printer"


@pytest.mark.asyncio
async def test_a_body_less_answer_behaves_as_before(async_client, printer_factory, db_session):
    printer = await printer_factory()
    archive, row = await _finished_on(db_session, printer, {"lid": 2})
    with _finished_printer():
        resp = await async_client.post(f"/api/v1/printers/{printer.id}/clear-plate")
    assert resp.status_code == 200, resp.text
    archive_id, row_id = archive.id, row.id
    db_session.expire_all()
    assert (await db_session.get(PrintArchive, archive_id)).defective_count == 0
    assert await db_session.get(PrintQueueItem, row_id) is None
