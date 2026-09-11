"""Defects from Telegram: one tap per part, «other…» takes a typed number.

Real rows in the test database (the handlers open their own session), a fake
CallbackQuery / Message, permission and scope patched the way the plate-answer
tests do it.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.models.archive import PrintArchive
from backend.app.models.archive_part import PrintArchivePart

pytestmark = pytest.mark.unit

MOD = "backend.app.services.telegram_handlers.defects"


@pytest.fixture
def patched_session(test_engine):
    maker = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    with patch("backend.app.core.database.async_session", maker):
        yield maker


async def _print(db_session, parts: dict[str, int] | None, *, quantity: int | None = None) -> PrintArchive:
    archive = PrintArchive(
        printer_id=5,
        filename="p.3mf",
        print_name="Plate",
        file_path="x/p.3mf",
        file_size=1,
        status="completed",
        quantity=quantity if quantity is not None else sum((parts or {}).values()),
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add(archive)
    await db_session.flush()
    for name, qty in (parts or {}).items():
        db_session.add(PrintArchivePart(archive_id=archive.id, name=name, name_key=name.lower(), quantity=qty))
    await db_session.commit()
    await db_session.refresh(archive)
    return archive


def _callback(data: str) -> MagicMock:
    cb = MagicMock()
    cb.data = data
    cb.answer = AsyncMock()
    cb.message = MagicMock()
    cb.message.answer = AsyncMock()
    cb.message.edit_text = AsyncMock()
    return cb


def _allowed():
    return (
        patch(f"{MOD}.has_perm", MagicMock(return_value=True)),
        patch(f"{MOD}.chat_allows_printer", MagicMock(return_value=True)),
        patch(f"{MOD}.get_language", AsyncMock(return_value="en")),
    )


async def _rows(db_session, archive):
    return {
        r.name_key: r
        for r in (
            await db_session.execute(select(PrintArchivePart).where(PrintArchivePart.archive_id == archive.id))
        ).scalars()
    }


async def test_a_tap_writes_one_part_and_asks_the_next(patched_session, db_session):
    from backend.app.services.telegram_handlers.defects import cb_defects_set

    archive = await _print(db_session, {"lid": 2, "base": 4})
    rows = await _rows(db_session, archive)
    # Ids into plain ints BEFORE expire_all() below — an expired attribute read
    # outside an ``await`` is a MissingGreenlet, not a useful failure.
    archive_id, lid_id = archive.id, rows["lid"].id
    cb = _callback(f"defects:{archive_id}:{lid_id}:1")
    p1, p2, p3 = _allowed()
    with p1, p2, p3:
        await cb_defects_set(cb)

    db_session.expire_all()
    assert (await db_session.get(PrintArchivePart, lid_id)).defective == 1
    assert (await db_session.get(PrintArchive, archive_id)).defective_count == 1
    # The next part's prompt went out as a NEW message; the answered one was edited to say what was recorded.
    cb.message.edit_text.assert_awaited()
    cb.message.answer.assert_awaited()
    assert "base" in cb.message.answer.await_args.args[0]


async def test_the_last_tap_says_the_total(patched_session, db_session):
    from backend.app.services.telegram_handlers.defects import cb_defects_set

    archive = await _print(db_session, {"lid": 2})
    rows = await _rows(db_session, archive)
    cb = _callback(f"defects:{archive.id}:{rows['lid'].id}:2")
    p1, p2, p3 = _allowed()
    with p1, p2, p3:
        await cb_defects_set(cb)

    cb.message.answer.assert_not_awaited()
    assert "2" in cb.message.edit_text.await_args.args[0]


async def test_no_defects_done_zeroes_this_and_the_rest(patched_session, db_session):
    from backend.app.services.telegram_handlers.defects import cb_defects_none

    archive = await _print(db_session, {"lid": 2, "base": 4, "cap": 1})
    rows = await _rows(db_session, archive)
    for row in rows.values():
        row.defective = 1
    await db_session.commit()
    ids = {name: row.id for name, row in rows.items()}
    cb = _callback(f"defects_none:{archive.id}:{ids['base']}")
    p1, p2, p3 = _allowed()
    with p1, p2, p3:
        await cb_defects_none(cb)

    db_session.expire_all()
    assert {k: (await db_session.get(PrintArchivePart, row_id)).defective for k, row_id in ids.items()} == {
        "lid": 1,
        "base": 0,
        "cap": 0,
    }


async def test_a_flat_print_is_one_question(patched_session, db_session):
    from backend.app.services.telegram_handlers.defects import cb_defects_set

    archive = await _print(db_session, None, quantity=3)
    archive_id = archive.id
    cb = _callback(f"defects:{archive_id}:0:2")
    p1, p2, p3 = _allowed()
    with p1, p2, p3:
        await cb_defects_set(cb)

    db_session.expire_all()
    assert (await db_session.get(PrintArchive, archive_id)).defective_count == 2


async def test_other_takes_a_typed_number_clamped(patched_session, db_session):
    from backend.app.services.telegram_handlers.defects import cb_defects_other, msg_defects_count

    archive = await _print(db_session, {"lid": 2})
    rows = await _rows(db_session, archive)
    archive_id, lid_id = archive.id, rows["lid"].id
    state = MagicMock()
    state.set_state = AsyncMock()
    state.update_data = AsyncMock()
    state.get_data = AsyncMock(return_value={"archive_id": archive_id, "row_id": lid_id})
    state.clear = AsyncMock()
    cb = _callback(f"defects_other:{archive_id}:{lid_id}")
    p1, p2, p3 = _allowed()
    with p1, p2, p3:
        await cb_defects_other(cb, state)
    state.set_state.assert_awaited()

    message = MagicMock()
    message.text = "7"
    message.answer = AsyncMock()
    p1, p2, p3 = _allowed()
    with p1, p2, p3:
        await msg_defects_count(message, state)

    db_session.expire_all()
    assert (await db_session.get(PrintArchivePart, lid_id)).defective == 2, "clamped to the row's quantity"
    state.clear.assert_awaited()


async def test_permission_and_scope_refuse(patched_session, db_session):
    from backend.app.services.telegram_handlers.defects import cb_defects_set

    archive = await _print(db_session, {"lid": 2})
    rows = await _rows(db_session, archive)
    lid_id = rows["lid"].id
    cb = _callback(f"defects:{archive.id}:{lid_id}:1")
    with (
        patch(f"{MOD}.has_perm", MagicMock(return_value=False)),
        patch(f"{MOD}.get_language", AsyncMock(return_value="en")),
    ):
        await cb_defects_set(cb)
    db_session.expire_all()
    assert (await db_session.get(PrintArchivePart, lid_id)).defective == 0
    cb.answer.assert_awaited()


async def test_a_gone_print_answers_gone(patched_session):
    from backend.app.services.telegram_handlers.defects import cb_defects_set

    cb = _callback("defects:999999:0:1")
    p1, p2, p3 = _allowed()
    with p1, p2, p3:
        await cb_defects_set(cb)
    cb.answer.assert_awaited()
