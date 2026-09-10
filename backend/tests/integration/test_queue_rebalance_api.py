"""The two manual doors to rebalancing: an order line's button and the panel's per-item action.

Both run the same procedure with the setting OFF and the cooldown ignored; the
per-item one answers, for every id it was given, either a move or the reason.
"""

import json

import pytest
from sqlalchemy import select

from backend.app.core.auth import create_access_token, get_password_hash
from backend.app.models.auto_queue import AutoQueueItem
from backend.app.models.group import Group
from backend.app.models.user import User
from backend.app.services.farm_forecast import model_key
from backend.tests.integration.test_auto_queue_scheduler import (
    _make_printer_with_queue,
    _patch_printer_manager,
    rebalance_farm,
)
from backend.tests.integration.test_orders_api import _the_dialogs_saved_preference

pytestmark = pytest.mark.integration


async def _pending(db):
    return list((await db.execute(select(AutoQueueItem).where(AutoQueueItem.status == "pending"))).scalars().all())


async def _as_viewer(client, db):
    """Re-point the client at a Viewers-group user — read permissions only."""
    viewer = User(username="viewer", password_hash=get_password_hash("Viewer_Pass1!"), role="user", is_active=True)
    group = (await db.execute(select(Group).where(Group.name == "Viewers"))).scalar_one()
    viewer.groups.append(group)
    db.add(viewer)
    await db.commit()
    client.headers["Authorization"] = f"Bearer {create_access_token(data={'sub': 'viewer'})}"


@pytest.mark.asyncio
async def test_line_button_moves_with_the_setting_off_and_reports_the_counts(
    committing_client, db_session, printer_factory, tmp_path
):
    farm = await rebalance_farm(db_session, printer_factory, tmp_path)
    await _the_dialogs_saved_preference(db_session, printer_model="A1MINI")
    p_elig, p_sched, p_ams = _patch_printer_manager({farm.p1s.id, farm.mini.id})
    with p_elig, p_sched, p_ams:
        r = await committing_client.post(f"/api/v1/projects/{farm.project.id}/lines/{farm.line.id}/rebalance")
    assert r.status_code == 200, r.text
    assert r.json() == {"converted": 1, "created": 2, "cancelled": 0, "moved_parts": 6, "skipped": []}

    # ``committing_client`` writes through its own session, not ``db_session`` —
    # with expire_on_commit=False, farm.item stays cached at its pre-request
    # values unless expired (the established pattern in test_orders_api.py).
    db_session.expire_all()
    rows = await _pending(db_session)
    assert len(rows) == 3 and {model_key(row.target_model) for row in rows} == {model_key("A1MINI")}
    created = [row for row in rows if row.id != farm.item.id]
    # The created rows carry the operator's saved profile for the receiving model
    # (``_PROFILE_TOGGLES``: timelapse on, external storage), the converted one keeps its own options.
    assert all(row.timelapse is True and row.timelapse_storage == "external" for row in created)
    converted = next(row for row in rows if row.id == farm.item.id)
    assert converted.timelapse is False and converted.position == 1
    assert {row.batch_id for row in rows} == {converted.batch_id} and converted.batch_id


@pytest.mark.asyncio
async def test_the_companions_inherit_the_source_rows_job_flags(
    committing_client, db_session, printer_factory, tmp_path
):
    """The profile decides the TOGGLES, the source row decides the JOB.

    One external-only print that switches the printer off after it must not
    become one external-only print plus two AMS prints that leave it on: the
    saved profile carries none of those four fields, so without the row they
    would be the writer's defaults.
    """
    farm = await rebalance_farm(db_session, printer_factory, tmp_path)
    await _the_dialogs_saved_preference(db_session, printer_model="A1MINI")
    farm.item.use_ams = False
    farm.item.feed_policy = "external_only"
    farm.item.auto_off_after = True
    farm.item.require_previous_success = True
    await db_session.commit()

    p_elig, p_sched, p_ams = _patch_printer_manager({farm.p1s.id, farm.mini.id})
    with p_elig, p_sched, p_ams:
        r = await committing_client.post(f"/api/v1/projects/{farm.project.id}/lines/{farm.line.id}/rebalance")
    assert r.status_code == 200, r.text
    assert (r.json()["converted"], r.json()["created"]) == (1, 2)

    db_session.expire_all()
    rows = await _pending(db_session)
    assert len(rows) == 3
    for row in rows:
        assert (row.use_ams, row.feed_policy, row.auto_off_after, row.require_previous_success) == (
            False,
            "external_only",
            True,
            True,
        ), f"row {row.id} did not inherit the job flags"


@pytest.mark.asyncio
async def test_line_button_ignores_the_cooldown(committing_client, db_session, printer_factory, tmp_path):
    farm = await rebalance_farm(db_session, printer_factory, tmp_path)
    p_elig, p_sched, p_ams = _patch_printer_manager({farm.p1s.id, farm.mini.id})
    with p_elig, p_sched, p_ams:
        first = await committing_client.post(f"/api/v1/projects/{farm.project.id}/lines/{farm.line.id}/rebalance")
    assert first.json()["converted"] == 1
    mini2, _q = await _make_printer_with_queue(db_session, printer_factory, name="Mini-2", model="A1MINI")
    db_session.add(
        AutoQueueItem(
            library_file_id=farm.big.id,
            plate_id=1,
            project_id=farm.project.id,
            project_line_id=farm.line.id,
            target_model="P1S",
            required_filament_types='["PLA"]',
            print_time_seconds=3600,
            status="pending",
            position=9,
        )
    )
    await db_session.commit()
    p_elig, p_sched, p_ams = _patch_printer_manager({farm.p1s.id, farm.mini.id, mini2.id})
    with p_elig, p_sched, p_ams:
        second = await committing_client.post(f"/api/v1/projects/{farm.project.id}/lines/{farm.line.id}/rebalance")
    assert second.status_code == 200, second.text
    assert second.json()["converted"] == 1, "force: the five-minute pause does not apply to the button"


@pytest.mark.asyncio
async def test_line_button_refuses_a_line_of_another_order(committing_client, db_session, printer_factory, tmp_path):
    farm = await rebalance_farm(db_session, printer_factory, tmp_path)
    other = await committing_client.post("/api/v1/projects/", json={"name": "Other"})
    assert other.status_code in (200, 201), other.text
    r = await committing_client.post(f"/api/v1/projects/{other.json()['id']}/lines/{farm.line.id}/rebalance")
    assert r.status_code == 404
    assert r.json()["detail"] == "Order line not found in this project"
    assert (await committing_client.post(f"/api/v1/projects/9999/lines/{farm.line.id}/rebalance")).status_code == 404


@pytest.mark.asyncio
async def test_line_button_needs_projects_update_and_queue_update_all(
    committing_client, db_session, printer_factory, tmp_path
):
    farm = await rebalance_farm(db_session, printer_factory, tmp_path)
    await _as_viewer(committing_client, db_session)
    r = await committing_client.post(f"/api/v1/projects/{farm.project.id}/lines/{farm.line.id}/rebalance")
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_panel_action_moves_the_named_items_and_names_why_the_others_stay(
    async_client, db_session, printer_factory, tmp_path
):
    farm = await rebalance_farm(db_session, printer_factory, tmp_path)
    staged = AutoQueueItem(
        library_file_id=farm.big.id,
        plate_id=1,
        project_id=farm.project.id,
        project_line_id=farm.line.id,
        target_model="P1S",
        print_time_seconds=3600,
        status="pending",
        position=2,
        manual_start=True,
    )
    unfiled = AutoQueueItem(library_file_id=farm.big.id, plate_id=1, target_model="P1S", status="pending", position=3)
    pinned = AutoQueueItem(
        library_file_id=farm.big.id,
        plate_id=1,
        project_id=farm.project.id,
        project_line_id=farm.line.id,
        target_model="P1S",
        status="pending",
        position=4,
        filament_overrides=json.dumps([{"slot_id": 1, "type": "PLA", "color": "#FFFFFF", "force_color_match": True}]),
    )
    db_session.add_all([staged, unfiled, pinned])
    await db_session.commit()

    p_elig, p_sched, p_ams = _patch_printer_manager({farm.p1s.id, farm.mini.id})
    with p_elig, p_sched, p_ams:
        r = await async_client.post(
            "/api/v1/auto-queue/rebalance",
            json={"item_ids": [farm.item.id, staged.id, unfiled.id, pinned.id, 999_999]},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["converted"], body["created"], body["moved_parts"]) == (1, 2, 6)
    assert sorted(body["skipped"], key=lambda s: s["item_id"]) == sorted(
        [
            {"item_id": staged.id, "reason": "staged"},
            {"item_id": unfiled.id, "reason": "not_filed"},
            {"item_id": pinned.id, "reason": "pinned"},
            {"item_id": 999_999, "reason": "not_found"},
        ],
        key=lambda s: s["item_id"],
    )
    await db_session.refresh(farm.item)
    assert model_key(farm.item.target_model) == model_key("A1MINI") and farm.item.rebalanced_from_model == "P1S"


@pytest.mark.asyncio
async def test_panel_action_validates_the_id_list(async_client):
    assert (await async_client.post("/api/v1/auto-queue/rebalance", json={"item_ids": []})).status_code == 422
    assert (
        await async_client.post("/api/v1/auto-queue/rebalance", json={"item_ids": list(range(65))})
    ).status_code == 422


@pytest.mark.asyncio
async def test_panel_action_needs_queue_update_all(async_client, db_session, printer_factory, tmp_path):
    farm = await rebalance_farm(db_session, printer_factory, tmp_path)
    await _as_viewer(async_client, db_session)
    r = await async_client.post("/api/v1/auto-queue/rebalance", json={"item_ids": [farm.item.id]})
    assert r.status_code == 403, r.text
