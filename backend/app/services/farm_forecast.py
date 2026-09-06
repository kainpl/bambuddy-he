"""Farm forecast — when an order is ready, and how a line splits across models.

Spec: docs/superpowers/specs/2026-09-06-farm-forecast-design.md. An ADVISORY
layer above the plan engine and the queues: it reads the plan's rows and the
database's picture of the farm, runs the textbook list-scheduling makespan, and
answers with dates and counts. It gates nothing and writes nothing, and it never
reads a printer beyond its model and what its queue already holds — routing is
not dispatching, and the plan engine stays ignorant of printers.

Two ETAs travel together (Decision 2): ``now`` — this order's plan sent on top of
what the queues hold today; ``after`` — after the plans of every active order
ranked ahead of it. Unknown estimates are counted, never defaulted (Decision 6).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from backend.app.services.plan_engine import OrderPlan
from backend.app.utils.printer_models import normalize_model_name

#: What the simulation does NOT model in this version; every surface shows it.
ASSUMPTIONS: tuple[str, ...] = ("stagger", "plate_clear", "drying", "prep")


def model_key(model: str | None) -> str | None:
    """The auto-queue's comparison key — both sides through the same normaliser."""
    normalised = normalize_model_name(model) if model else None
    if not normalised:
        return None
    return normalised.strip().lower() or None


# ---------- inputs ----------


@dataclass
class QueuedRow:
    order_id: int | None
    seconds: int | None


@dataclass
class MachineState:
    printer_id: int
    model: str | None
    running_seconds: float = 0.0
    queued: list[QueuedRow] = field(default_factory=list)  # position order


@dataclass
class StagedJob:
    order_id: int | None
    target_model: str | None
    seconds: int | None


@dataclass
class FarmSnapshot:
    printers: list[MachineState]
    staged: list[StagedJob]


@dataclass
class PlateOption:
    plate_id: int
    model: str | None
    seconds: int | None


@dataclass
class PrintJob:
    order_id: int
    line_id: int
    row_plate_id: int
    options: list[PlateOption]  # the row's own plate first, then its alternatives


# ---------- outputs ----------


@dataclass
class RowForecast:
    plate_id: int
    proposed_split: (
        dict[int, int] | None
    )  # ProductPlate.id → prints, summing to the row's count; None for a row without alternatives or one the farm could not place


@dataclass
class LineForecast:
    line_id: int
    now_eta: datetime | None
    now_seconds: int | None
    after_eta: datetime | None
    after_seconds: int | None
    unknown_prints: int
    unroutable_prints: int
    rows: list[RowForecast] = field(default_factory=list)


@dataclass
class OrderForecast:
    project_id: int
    now_eta: datetime | None
    now_seconds: int | None
    after_eta: datetime | None
    after_seconds: int | None
    machine_seconds: int | None
    unknown_prints: int
    unroutable_prints: int
    ahead_count: int
    lines: list[LineForecast] = field(default_factory=list)


@dataclass
class FarmForecast:
    free_seconds: int


# ---------- the simulation ----------


@dataclass
class _Machine:
    printer_id: int
    key: str | None
    free_at: float


@dataclass
class _Placement:
    finish: float
    row_plate_id: int
    plate_id: int


@dataclass
class _State:
    machines: list[_Machine]
    order_finish: dict[int, float] = field(default_factory=dict)  # order → finish of its already queued/staged work
    unknown: Counter = field(default_factory=Counter)  # order_id → prints without an estimate
    unroutable: Counter = field(default_factory=Counter)  # order_id → prints with no printer for their model
    line_unknown: Counter = field(default_factory=Counter)  # the same two, per line
    line_unroutable: Counter = field(default_factory=Counter)

    def farm_finish(self) -> float:
        return max((m.free_at for m in self.machines), default=0.0)


def _bump(finish: dict[int, float], order_id: int | None, at: float) -> None:
    if order_id is not None:
        finish[order_id] = max(finish.get(order_id, 0.0), at)


def _earliest(machines: list[_Machine], key: str | None) -> _Machine | None:
    if key is None:
        return None
    candidates = [m for m in machines if m.key == key]
    return min(candidates, key=lambda m: (m.free_at, m.printer_id)) if candidates else None


def _initial_state(snapshot: FarmSnapshot) -> _State:
    """What every printer already owes, then the staging area dealt out longest-first."""
    state = _State(machines=[])
    for machine in snapshot.printers:
        t = max(0.0, float(machine.running_seconds))
        for row in machine.queued:
            if not row.seconds or row.seconds <= 0:
                if row.order_id is not None:
                    state.unknown[row.order_id] += 1
                continue
            t += row.seconds
            _bump(state.order_finish, row.order_id, t)
        state.machines.append(_Machine(printer_id=machine.printer_id, key=model_key(machine.model), free_at=t))
    for job in sorted(snapshot.staged, key=lambda j: -(j.seconds or 0)):
        if not job.seconds or job.seconds <= 0:
            if job.order_id is not None:
                state.unknown[job.order_id] += 1
            continue
        target = _earliest(state.machines, model_key(job.target_model))
        if target is None:
            if job.order_id is not None:
                state.unroutable[job.order_id] += 1
            continue
        target.free_at += job.seconds
        _bump(state.order_finish, job.order_id, target.free_at)
    return state


def _place(state: _State, jobs: list[PrintJob]) -> dict[int, list[_Placement]]:
    """Deal the jobs out longest-first (a job's length is its shortest option);
    each goes to the option whose earliest-free printer finishes it first.
    Returns ``line_id → placements``; the unknown / unroutable ones are counted
    on their order and their line."""
    placed: dict[int, list[_Placement]] = {}

    def length(job: PrintJob) -> int:
        return min((o.seconds for o in job.options if o.seconds and o.seconds > 0), default=0)

    for job in sorted(jobs, key=lambda j: -length(j)):
        timed = [o for o in job.options if o.seconds and o.seconds > 0]
        if not timed:
            state.unknown[job.order_id] += 1
            state.line_unknown[job.line_id] += 1
            continue
        best: tuple[float, int, _Machine, PlateOption] | None = None
        for option in timed:
            machine = _earliest(state.machines, model_key(option.model))
            if machine is None:
                continue
            candidate = (machine.free_at + option.seconds, option.seconds, machine, option)
            if best is None or candidate[:2] < best[:2]:
                best = candidate
        if best is None:
            state.unroutable[job.order_id] += 1
            state.line_unroutable[job.line_id] += 1
            continue
        finish, _secs, machine, option = best
        machine.free_at = finish
        placed.setdefault(job.line_id, []).append(_Placement(finish, job.row_plate_id, option.plate_id))
    return placed


def jobs_from_plan(order_id: int, plan: OrderPlan | None) -> list[PrintJob]:
    """One job per print the plan asks for; a row's options are its own plate
    then its alternatives — the same list the plan block's split offers."""
    jobs: list[PrintJob] = []
    for line in plan.lines if plan else []:
        for row in line.rows:
            options = [PlateOption(row.plate_id, row.printer_model, row.print_time_seconds)] + [
                PlateOption(a.plate_id, a.printer_model, a.print_time_seconds) for a in row.alternatives
            ]
            jobs.extend(PrintJob(order_id, line.line_id, row.plate_id, options) for _ in range(row.count))
    return jobs


def machine_seconds_of(plan: OrderPlan | None) -> int | None:
    """Σ count × estimate over rows with one; None when rows exist but none has
    an estimate; 0 for an order with nothing left to plan."""
    rows = [r for line in (plan.lines if plan else []) for r in line.rows]
    if not rows:
        return 0
    timed = [r for r in rows if r.print_time_seconds and r.print_time_seconds > 0]
    return sum(r.count * r.print_time_seconds for r in timed) if timed else None


def simulate_farm(snapshot: FarmSnapshot) -> FarmForecast:
    """When the last printer is free, given what the queues already hold."""
    return FarmForecast(free_seconds=int(round(_initial_state(snapshot).farm_finish())))


def _eta(now: datetime, seconds: float | None) -> tuple[datetime | None, int | None]:
    if seconds is None:
        return None, None
    whole = int(round(seconds))
    return now + timedelta(seconds=whole), whole


def _order_result(
    order_id: int,
    plan: OrderPlan | None,
    state: _State,
    placed: dict[int, list[_Placement]],
    now: datetime,
    ahead: int,
) -> OrderForecast:
    """Read one run's outcome for ``order_id`` off the state it left: the order
    finishes when its last planned print AND its already-queued work finish."""
    finishes: list[float] = []
    if order_id in state.order_finish:
        finishes.append(state.order_finish[order_id])
    lines: list[LineForecast] = []
    for line in plan.lines if plan else []:
        line_placements = placed.get(line.line_id, [])
        line_finish = max((p.finish for p in line_placements), default=None)
        if line_finish is not None:
            finishes.append(line_finish)
        eta, secs = _eta(now, line_finish)
        rows: list[RowForecast] = []
        for row in line.rows:
            if not row.alternatives:
                rows.append(RowForecast(plate_id=row.plate_id, proposed_split=None))
                continue
            split = {row.plate_id: 0, **{a.plate_id: 0 for a in row.alternatives}}
            for p in line_placements:
                if p.row_plate_id == row.plate_id:
                    split[p.plate_id] = split.get(p.plate_id, 0) + 1
            proposed_split = split if sum(split.values()) == row.count else None
            rows.append(RowForecast(plate_id=row.plate_id, proposed_split=proposed_split))
        lines.append(
            LineForecast(
                line_id=line.line_id,
                now_eta=eta,
                now_seconds=secs,
                after_eta=None,
                after_seconds=None,
                unknown_prints=state.line_unknown[line.line_id],
                unroutable_prints=state.line_unroutable[line.line_id],
                rows=rows,
            )
        )
    eta, secs = _eta(now, max(finishes) if finishes else None)
    return OrderForecast(
        project_id=order_id,
        now_eta=eta,
        now_seconds=secs,
        after_eta=None,
        after_seconds=None,
        machine_seconds=machine_seconds_of(plan),
        unknown_prints=state.unknown[order_id],
        unroutable_prints=state.unroutable[order_id],
        ahead_count=ahead,
        lines=lines,
    )


def forecast_orders(
    snapshot: FarmSnapshot,
    plans: dict[int, OrderPlan],
    ordered_ids: list[int],
    targets: set[int],
    now: datetime,
) -> dict[int, OrderForecast]:
    """``now`` and ``after`` for every target, walking ``ordered_ids`` in rank order.

    ``after`` is read off ONE running state that every order's plan advances in
    turn; ``now`` is read off a fresh initial state per target. The proposed
    split comes from the ``now`` run — it is what the button enqueues.
    """
    ahead_state = _initial_state(snapshot)
    out: dict[int, OrderForecast] = {}
    for index, order_id in enumerate(ordered_ids):
        plan = plans.get(order_id)
        jobs = jobs_from_plan(order_id, plan)
        if order_id not in targets:
            _place(ahead_state, jobs)
            continue
        fresh = _initial_state(snapshot)
        result = _order_result(order_id, plan, fresh, _place(fresh, jobs), now, ahead=index)
        after = _order_result(order_id, plan, ahead_state, _place(ahead_state, jobs), now, ahead=index)
        result.after_eta, result.after_seconds = after.now_eta, after.now_seconds
        for line, after_line in zip(result.lines, after.lines, strict=True):
            line.after_eta, line.after_seconds = after_line.now_eta, after_line.now_seconds
        out[order_id] = result
    return out
