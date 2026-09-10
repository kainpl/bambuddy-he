"""Move an order line's still-pending auto-queue work to idle printers of another model.

Spec: docs/superpowers/specs/2026-09-10-model-rebalancing-design.md.

The unit is PARTS of a line, not prints: a pending item is a claim on covering
``y_m`` parts, and moving it may replace one print of yield 6 by three prints
of yield 2 on a smaller bed, or by one print of a bigger plate with a surplus
of less than one plate's worth. :func:`plan_moves` is the pure decision —
dataclasses in, moves out — and :func:`rebalance` is the only thing here that
touches the database: it loads what the decision needs, calls it, and applies
each move through the writer every enqueue uses.

⚠️ **Routing is not dispatching, and this is routing.** Nothing here starts a
print, gates the ROUTER on readiness, or touches ``find_eligible_printer`` /
``_assign``. "Idle" is asked only to decide who may RECEIVE moved work: a
printer with an empty queue that still waits for a plate clear only looks
free, and moving work to it would move it nowhere — so the receiver test is
the busy set AND ``PrintScheduler._is_printer_idle``, both readiness signals
the router's ranking already uses.

⚠️ **Never moved:** assigned, scheduled for a time, staged (``manual_start``),
pinned (slot-bound ``filament_overrides``), aimed at a location, sourced from
an archive, or not filed under an order line — see :func:`refusal`. Those
either belong to a printer already, carry an operator's explicit decision, or
have nothing to move to.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from backend.app.services.farm_forecast import FarmSnapshot, model_key
from backend.app.services.plan_engine import _pick_key

logger = logging.getLogger(__name__)

REBALANCE_COOLDOWN_SECONDS = 300
REBALANCE_SETTING_KEY = "auto_queue_rebalance_models"

#: The closed list of reasons an item is left where it is. The frontend
#: translates them under ``autoQueue.rebalance.skipped.<code>`` — adding one
#: here means adding it there, in both locales.
SKIP_REASONS = (
    "not_found",
    "already_assigned",
    "not_filed",
    "pinned",
    "scheduled",
    "staged",
    "located",
    "no_yield",
    "source_unreadable",
    "home_model_idle",
    "no_faster_model",
    "cooldown",
)


# ---------- what the decision sees ----------


@dataclass(frozen=True)
class PlateOption:
    """One sliced candidate plate of a line, as the decision sees it."""

    plate_id: int  # ProductPlate.id
    library_file_id: int
    plate_index: int  # the recipe's index; 0 = the whole file
    model: str  # ``farm_forecast.model_key`` spelling — what idle capacity is keyed by
    model_label: str  # the file's own spelling (``P1S``) — what target_model and the profile lookup want
    yield_parts: int  # the plate's ``line_yield`` summed over the line's counted parts
    seconds: int | None  # ``estimate_seconds(recipe)``; None = no estimate, never a target


@dataclass(frozen=True)
class MovableItem:
    item_id: int
    line_id: int
    home_model: str  # ``model_key`` of the item's target_model
    yield_parts: int  # y_m — what this item covers for its line
    seconds: int | None  # t_m


@dataclass
class FarmView:
    """The farm as the decision sees it: who may receive, and when each model is next free.

    A model absent from ``free_at_by_model`` has no machine that accepts new
    work — an item whose home that is moves whenever anything can take it.
    """

    idle_by_model: dict[str, int]
    free_at_by_model: dict[str, float]  # seconds from now


@dataclass(frozen=True)
class Move:
    item_id: int
    line_id: int
    from_model: str
    to_model: str
    plate: PlateOption
    k: int  # prints of ``plate`` that cover what the item covered
    home_finish: float | None
    finish: float
    surplus: int  # k × plate yield − item yield, always < plate yield
    moved_parts: int  # the item's yield — what the move is for


@dataclass
class MovePlan:
    moves: list[Move] = field(default_factory=list)
    skipped: list[tuple[int, str]] = field(default_factory=list)  # (item_id, reason)


# ---------- the decision ----------


def _best_plate(options, model: str, wanted: int) -> PlateOption | None:
    """The line's best plate of ``model`` for covering ``wanted`` parts — by the plan engine's own key.

    Most useful parts per hour first, then least waste, then the shorter print,
    then the lower plate id. A plate without an estimate is never chosen: its
    finish could not be compared with waiting at home.
    """
    candidates = [o for o in options if o.model == model and o.yield_parts > 0 and o.seconds is not None]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda o: _pick_key(min(o.yield_parts, wanted), max(0, o.yield_parts - wanted), o.seconds, o.plate_id),
    )


def plan_moves(
    items: list[MovableItem],
    options_by_line: dict[int, list[PlateOption]],
    farm: FarmView,
    *,
    cooling: frozenset[int] | set[int] = frozenset(),
) -> MovePlan:
    """The decision, item by item, in the order ``items`` arrive (spec §3.2).

    Pure. The caller sorts the items — order rank, then queue order — and hands
    in the farm as it is now; this walks them once, consuming capacity as it
    goes, so an urgent order takes idle printers first and one pass never
    floods a model. Per item: skip if its line is cooling or its own model has
    an idle printer (the normal pass is about to place it); otherwise find,
    for every other model with capacity, the best plate, ``k = ceil(y_m / y_X)``
    prints of it and their finish ``ceil(k / c_X) × t_X``; move to the earliest
    finish that is not later than ``free_at(home) + t_m``.

    ``t_m`` unknown compares as 0 (home looks instant, so the item moves only
    when the other model finishes before home is even free). When a receiver's
    capacity reaches zero its ``free_at`` becomes the shortest chain a machine
    of it now holds, ``(k // c_X) × t_X``, so a later item whose HOME is that
    model sees the farm as it will be.
    """
    idle = dict(farm.idle_by_model)
    free_at = dict(farm.free_at_by_model)
    plan = MovePlan()
    for item in items:
        if item.line_id in cooling:
            plan.skipped.append((item.item_id, "cooldown"))
            continue
        if idle.get(item.home_model, 0) > 0:
            plan.skipped.append((item.item_id, "home_model_idle"))
            continue
        home_free = free_at.get(item.home_model)
        home_finish = None if home_free is None else home_free + (item.seconds or 0)
        best: tuple[tuple[float, int, str], str, PlateOption, int, float, int] | None = None
        for model, capacity in idle.items():
            if capacity <= 0 or model == item.home_model:
                continue
            plate = _best_plate(options_by_line.get(item.line_id, ()), model, item.yield_parts)
            if plate is None:
                continue
            k = -(-item.yield_parts // plate.yield_parts)
            finish = float(-(-k // capacity) * (plate.seconds or 0))
            if home_finish is not None and finish > home_finish:
                continue
            surplus = k * plate.yield_parts - item.yield_parts
            key = (finish, surplus, model)
            if best is None or key < best[0]:
                best = (key, model, plate, k, finish, surplus)
        if best is None:
            plan.skipped.append((item.item_id, "no_faster_model"))
            continue
        _key, model, plate, k, finish, surplus = best
        plan.moves.append(
            Move(
                item_id=item.item_id,
                line_id=item.line_id,
                from_model=item.home_model,
                to_model=model,
                plate=plate,
                k=k,
                home_finish=home_finish,
                finish=finish,
                surplus=surplus,
                moved_parts=item.yield_parts,
            )
        )
        capacity = idle[model]
        idle[model] = max(0, capacity - k)
        if idle[model] == 0:
            free_at[model] = max(free_at.get(model, 0.0), float((k // capacity) * (plate.seconds or 0)))
    return plan


def home_wait_by_model(snapshot: FarmSnapshot) -> dict[str, float]:
    """``model_key → seconds until the earliest machine of that model that accepts work is free``.

    The same estimate the ETA uses (``farm_forecast.load_snapshot``): the head
    of the queue is the running print's remaining seconds, then the pending rows
    in position order; a row without an estimate counts nothing. A parked
    machine (``accepts_new_work=False``) never sets the figure — what it holds is
    not somewhere new work could go.
    """
    out: dict[str, float] = {}
    for machine in snapshot.printers:
        if not machine.accepts_new_work:
            continue
        key = model_key(machine.model)
        if key is None:
            continue
        busy_for = max(0.0, float(machine.running_seconds)) + float(
            sum(row.seconds for row in machine.queued if row.seconds and row.seconds > 0)
        )
        out[key] = min(out[key], busy_for) if key in out else busy_for
    return out
