"""Filament needs — what the plan still asks for against what is on the shelf.

Spec: docs/superpowers/specs/2026-09-07-filament-needs-design.md. An ADVISORY
layer above the plan engine and the inventory: it reads the plan's rows and
the plate's slicer filaments, adds the order's pending queue rows, and puts
the sum per (material, line colour) next to the spools of either backend. It
reserves nothing and gates nothing; the plan engine stays ignorant of spools.

Unknown grams are counted, never defaulted (Decision 5): a plate without
filaments, or a filament without a type, is an unknown PRINT; a typed filament
without grams is an unknown print OF ITS KEY. Zero grams is an answer.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from backend.app.services.plan_engine import OrderPlan

ASSUMPTIONS: tuple[str, ...] = ("slicer_estimate",)


@dataclass(frozen=True)
class NeedKey:
    material: str
    colour: str | None


def key_of(material: str | None, colour: str | None) -> NeedKey | None:
    """``(TYPE, colour)`` — type upper-cased, colour casefolded and trimmed, ``None`` when blank."""
    mat = (material or "").strip().upper()
    if not mat:
        return None
    col = (colour or "").strip().casefold()
    return NeedKey(mat, col or None)


@dataclass
class FilamentLine:
    material: str | None
    grams: float | None


@dataclass
class QueuedNeed:
    line_colour: str | None
    filaments: list[FilamentLine] | None  # None = the row has no readable plate


@dataclass
class SpoolStock:
    material: str
    colour_name: str | None
    colour_hex: str | None  # RRGGBB, lower-case, no '#'
    remaining_g: float


@dataclass
class Needs:
    grams: dict[NeedKey, float] = field(default_factory=dict)
    unknown_by_key: Counter = field(default_factory=Counter)
    unknown_prints: int = 0

    def add(self, filaments: list[FilamentLine] | None, colour: str | None, prints: int) -> None:
        if not filaments:
            self.unknown_prints += prints
            return
        untyped = False
        for f in filaments:
            key = key_of(f.material, colour)
            if key is None:
                untyped = True
                continue
            if f.grams is None:
                self.unknown_by_key[key] += prints
            else:
                self.grams[key] = self.grams.get(key, 0.0) + prints * float(f.grams)
        if untyped:
            self.unknown_prints += prints

    def merge(self, other: Needs) -> Needs:
        out = Needs(dict(self.grams), Counter(self.unknown_by_key), self.unknown_prints)
        for key, g in other.grams.items():
            out.grams[key] = out.grams.get(key, 0.0) + g
        out.unknown_by_key.update(other.unknown_by_key)
        out.unknown_prints += other.unknown_prints
        return out

    def keys(self) -> set[NeedKey]:
        """Every key a row will be made for — the grams AND the gramless-but-typed ones."""
        return set(self.grams) | set(self.unknown_by_key)


def need_of_plan(
    plan: OrderPlan | None, line_colours: dict[int, str | None], plate_filaments: dict[int, list[FilamentLine]]
) -> Needs:
    """Σ count × grams per key over the plan's rows; ``plate_filaments`` is keyed by ``ProductPlate.id``."""
    needs = Needs()
    for line in plan.lines if plan else []:
        colour = line_colours.get(line.line_id)
        for row in line.rows:
            if row.count <= 0:
                continue
            needs.add(plate_filaments.get(row.plate_id), colour, row.count)
    return needs


def need_of_queue(rows: Iterable[QueuedNeed]) -> Needs:
    """Σ count × grams per key over the queue rows; each row counts as 1 print."""
    needs = Needs()
    for row in rows:
        needs.add(row.filaments, row.line_colour, 1)
    return needs


def _matches_colour(spool: SpoolStock, colour: str, names_of_hex: Callable[[str], set[str]]) -> bool:
    if spool.colour_name and spool.colour_name.strip().casefold() == colour:
        return True
    return bool(spool.colour_hex) and colour in names_of_hex(spool.colour_hex)


def stock_by_key(
    spools: list[SpoolStock], keys: Iterable[NeedKey], names_of_hex: Callable[[str], set[str]]
) -> dict[NeedKey, tuple[float, float]]:
    """``key → (have_g, have_type_g)``: the type total always, the colour figure when the key has one. Pass ``needs.keys()`` to ensure coverage."""
    out: dict[NeedKey, tuple[float, float]] = {}
    for key in keys:
        of_type = [s for s in spools if s.material.strip().upper() == key.material]
        type_total = sum(s.remaining_g for s in of_type)
        have = (
            type_total
            if key.colour is None
            else sum(s.remaining_g for s in of_type if _matches_colour(s, key.colour, names_of_hex))
        )
        out[key] = (have, type_total)
    return out


@dataclass
class NeedRow:
    material: str
    colour: str | None
    need_g: float
    have_g: float | None
    have_type_g: float | None
    short_g: float | None
    unknown_prints: int


def rows_of(needs: Needs, stock: dict[NeedKey, tuple[float, float]] | None) -> list[NeedRow]:
    """One row per key (grams and gramless-but-typed).

    ``stock`` comes from ``stock_by_key(spools, needs.keys(), …)``;
    a key it does not carry is reported as an unknown shelf (``None``),
    never as zero — a caller that forgets a key sees dashes, not a silent 0.
    """
    rows: list[NeedRow] = []
    for key in sorted(needs.keys(), key=lambda k: (k.material, k.colour or "")):
        need = round(needs.grams.get(key, 0.0), 1)
        have = have_type = short = None
        if stock is not None and key in stock:
            have, have_type = stock[key]
            have, have_type = round(have, 1), round(have_type, 1)
            short = round(max(0.0, need - have), 1)
        rows.append(NeedRow(key.material, key.colour, need, have, have_type, short, needs.unknown_by_key.get(key, 0)))
    return rows


@dataclass
class OrderNeeds:
    project_id: int
    rows: list[NeedRow]
    unknown_prints: int
    stock_unavailable: bool


@dataclass
class FarmRow(NeedRow):
    orders_count: int = 0


@dataclass
class FarmNeeds:
    rows: list[FarmRow]
    orders_count: int
    unknown_prints: int
    stock_unavailable: bool


def farm_of(per_order: dict[int, list[NeedRow]], *, unknown_prints: int, stock_unavailable: bool) -> FarmNeeds:
    """One row per key across every order: needs summed, the shelf figures taken once (same shelf for all)."""
    acc: dict[NeedKey, FarmRow] = {}
    for rows in per_order.values():
        for r in rows:
            key = NeedKey(r.material, r.colour)
            row = acc.get(key)
            if row is None:
                acc[key] = FarmRow(r.material, r.colour, r.need_g, r.have_g, r.have_type_g, None, r.unknown_prints, 1)
            else:
                row.need_g = round(row.need_g + r.need_g, 1)
                row.unknown_prints += r.unknown_prints
                row.orders_count += 1
    for row in acc.values():
        row.short_g = None if row.have_g is None else round(max(0.0, row.need_g - row.have_g), 1)
    ordered = sorted(acc.values(), key=lambda k: (k.material, k.colour or ""))
    return FarmNeeds(ordered, len(per_order), unknown_prints, stock_unavailable)
