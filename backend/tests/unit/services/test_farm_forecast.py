"""The forecast core on in-memory rows — pure, ``now`` injected, no session.

Routing is not dispatching: nothing here knows a printer beyond its model and
its load. The engine is the textbook list-scheduling makespan the queue page
used to compute in the browser; these tests pin the rules the spec names.
"""

from datetime import datetime, timedelta

from backend.app.services.farm_forecast import (
    FarmSnapshot,
    MachineState,
    QueuedRow,
    StagedJob,
    forecast_orders,
    simulate_farm,
)
from backend.app.services.plan_engine import LinePlan, OrderPlan, PlanAlternative, PlanRow

NOW = datetime(2026, 9, 6, 12, 0, 0)
H = 3600


def _machine(pid, model="P1S", running=0, queued=()):
    return MachineState(printer_id=pid, model=model, running_seconds=running, queued=[QueuedRow(*q) for q in queued])


def _plan(order_id, rows):
    """One line whose rows are ``(plate_id, count, seconds, model, alternatives)``,
    an alternative being ``(plate_id, model, seconds)``."""
    plan_rows = []
    for plate_id, count, seconds, model, alts in rows:
        plan_rows.append(
            PlanRow(
                plate_id=plate_id,
                library_file_id=plate_id,
                plate_index=0,
                filename=f"f{plate_id}",
                count=count,
                print_time_seconds=seconds,
                time_unknown=seconds is None,
                printer_model=model,
                alternatives=[
                    PlanAlternative(
                        plate_id=a_id,
                        library_file_id=a_id,
                        plate_index=0,
                        filename=f"f{a_id}",
                        printer_model=a_model,
                        print_time_seconds=a_secs,
                        time_unknown=a_secs is None,
                    )
                    for a_id, a_model, a_secs in alts
                ],
            )
        )
    return OrderPlan(lines=[LinePlan(line_id=order_id * 10, product_id=1, material=None, rows=plan_rows)])


def _one(snapshot, plan, order_id=7, ordered=None):
    return forecast_orders(snapshot, {order_id: plan}, ordered or [order_id], {order_id}, NOW)[order_id]


def test_one_printer_runs_the_jobs_serially():
    f = _one(FarmSnapshot(printers=[_machine(1)], staged=[]), _plan(7, [(100, 3, H, "P1S", [])]))
    assert f.now_seconds == 3 * H and f.now_eta == NOW + timedelta(hours=3)
    assert f.machine_seconds == 3 * H and f.unknown_prints == 0 and f.unroutable_prints == 0
    assert f.lines[0].now_seconds == 3 * H and f.lines[0].line_id == 70


def test_two_printers_of_the_model_halve_the_finish():
    f = _one(FarmSnapshot(printers=[_machine(1), _machine(2)], staged=[]), _plan(7, [(100, 4, H, "P1S", [])]))
    assert f.now_seconds == 2 * H


def test_a_busy_printer_and_its_queue_delay_the_start():
    snap = FarmSnapshot(printers=[_machine(1, running=H, queued=[(None, H)])], staged=[])
    assert _one(snap, _plan(7, [(100, 1, H, "P1S", [])])).now_seconds == 3 * H


def test_alternatives_spread_the_line_across_models_and_propose_the_split():
    """Four idle P1S, one idle X1C, 100 one-hour prints: 80 land on the P1S file, 20 on the X1C file."""
    printers = [_machine(i, "P1S") for i in range(1, 5)] + [_machine(9, "X1C")]
    f = _one(FarmSnapshot(printers=printers, staged=[]), _plan(7, [(100, 100, H, "P1S", [(200, "X1C", H)])]))
    row = f.lines[0].rows[0]
    assert row.plate_id == 100 and row.proposed_split == {100: 80, 200: 20}
    assert f.now_seconds == 20 * H


def test_a_busy_machine_shifts_the_split():
    printers = [_machine(1, "P1S", running=10 * H), _machine(9, "X1C")]
    f = _one(FarmSnapshot(printers=printers, staged=[]), _plan(7, [(100, 10, H, "P1S", [(200, "X1C", H)])]))
    assert f.lines[0].rows[0].proposed_split == {100: 0, 200: 10}


def test_a_row_without_alternatives_proposes_nothing():
    f = _one(FarmSnapshot(printers=[_machine(1)], staged=[]), _plan(7, [(100, 2, H, "P1S", [])]))
    assert f.lines[0].rows[0].proposed_split is None


def test_two_rows_of_one_line_keep_their_own_proposals():
    """Row A (plate 100, alt 200) and row B (plate 200, alt 100) on the same line:
    each proposal is counted from ITS prints, not from the line's."""
    printers = [_machine(1, "P1S"), _machine(9, "X1C")]
    plan = _plan(7, [(100, 2, H, "P1S", [(200, "X1C", H)]), (200, 2, H, "X1C", [(100, "P1S", H)])])
    f = _one(FarmSnapshot(printers=printers, staged=[]), plan)
    a, b = f.lines[0].rows
    assert sum(a.proposed_split.values()) == 2 and sum(b.proposed_split.values()) == 2


def test_staged_auto_queue_work_occupies_its_model_first():
    snap = FarmSnapshot(printers=[_machine(1)], staged=[StagedJob(order_id=None, target_model="P1S", seconds=2 * H)])
    assert _one(snap, _plan(7, [(100, 1, H, "P1S", [])])).now_seconds == 3 * H


def test_after_places_the_order_ahead_first_and_now_does_not():
    snap = FarmSnapshot(printers=[_machine(1)], staged=[])
    plans = {1: _plan(1, [(100, 2, H, "P1S", [])]), 7: _plan(7, [(300, 1, H, "P1S", [])])}
    out = forecast_orders(snap, plans, [1, 7], {7}, NOW)
    assert list(out) == [7]
    f = out[7]
    assert f.now_seconds == H and f.after_seconds == 3 * H and f.ahead_count == 1
    assert f.lines[0].after_seconds == 3 * H


def test_an_order_ahead_without_a_plan_advances_nothing():
    f = _one(FarmSnapshot(printers=[_machine(1)], staged=[]), _plan(7, [(100, 1, H, "P1S", [])]), ordered=[1, 7])
    assert f.after_seconds == H and f.ahead_count == 1


def test_unknown_estimates_are_counted_not_defaulted():
    f = _one(FarmSnapshot(printers=[_machine(1)], staged=[]), _plan(7, [(100, 3, None, "P1S", [])]))
    assert f.unknown_prints == 3 and f.now_eta is None and f.now_seconds is None and f.machine_seconds is None
    assert f.lines[0].unknown_prints == 3


def test_a_model_with_no_printer_is_unroutable():
    f = _one(FarmSnapshot(printers=[_machine(1, "A1MINI")], staged=[]), _plan(7, [(100, 2, H, "P1S", [])]))
    assert f.unroutable_prints == 2 and f.now_eta is None and f.lines[0].unroutable_prints == 2
    # No model on the file at all is unroutable too — the auto-queue would not route it either.
    f = _one(FarmSnapshot(printers=[_machine(1)], staged=[]), _plan(7, [(100, 1, H, None, [])]))
    assert f.unroutable_prints == 1


def test_queued_rows_of_the_order_give_an_eta_without_a_plan():
    snap = FarmSnapshot(printers=[_machine(1, queued=[(7, H), (7, None)])], staged=[])
    f = forecast_orders(snap, {}, [7], {7}, NOW)[7]
    assert f.now_seconds == H and f.machine_seconds == 0 and f.unknown_prints == 1 and f.lines == []


def test_the_farm_free_at_is_the_last_printer():
    snap = FarmSnapshot(
        printers=[_machine(1, running=H), _machine(2, "X1C", queued=[(None, 2 * H)])],
        staged=[StagedJob(order_id=None, target_model="X1C", seconds=H)],
    )
    assert simulate_farm(snap).free_seconds == 3 * H


def test_models_match_after_normalisation():
    snap = FarmSnapshot(printers=[_machine(1, "Bambu Lab P1S")], staged=[])
    f = _one(snap, _plan(7, [(100, 1, H, "P1S", [])]))
    assert f.unroutable_prints == 0 and f.now_seconds == H


def test_a_row_the_farm_cannot_place_proposes_nothing():
    """No printer of either model: the counters say why, and there is no split to apply."""
    f = _one(
        FarmSnapshot(printers=[_machine(1, "A1MINI")], staged=[]), _plan(7, [(100, 3, H, "P1S", [(200, "X1C", H)])])
    )
    assert f.unroutable_prints == 3 and f.lines[0].rows[0].proposed_split is None


def test_an_overrun_print_advances_nothing_and_is_not_unknown():
    snap = FarmSnapshot(printers=[_machine(1, queued=[(7, 0), (7, H)])], staged=[])
    f = forecast_orders(snap, {}, [7], {7}, NOW)[7]
    assert f.unknown_prints == 0 and f.now_seconds == H
