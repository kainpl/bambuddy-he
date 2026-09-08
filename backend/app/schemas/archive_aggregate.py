"""Response shape for ``GET /archives/aggregate``.

Sized by the date range rather than by the number of prints: a two-year «all
time» on a 48-printer farm is about a thousand rows here, against ten thousand
truncated archive rows before.
"""

from pydantic import BaseModel


class BucketMetrics(BaseModel):
    prints: int = 0
    completed: int = 0
    failed: int = 0
    grams: float = 0.0
    cost: float = 0.0
    energy_cost: float = 0.0
    quantity: int = 0
    seconds: float = 0.0


class Bucket(BaseModel):
    """One local day (``2026-09-08``) or hour (``2026-09-08T14``).

    Two metric groups because the page has two axes: ``started`` is keyed on
    ``created_at`` (the activity calendar, the heat-map, the weekday habits) and
    ``ended`` on ``COALESCE(completed_at, created_at)`` (the archive calendar,
    the filament timeline, the records).
    """

    at: str
    started: BucketMetrics
    ended: BucketMetrics


class HourCell(BaseModel):
    hour: int
    prints: int = 0
    failures: int = 0


class PrinterRow(BaseModel):
    printer_id: int | None = None
    prints: int = 0
    grams: float = 0.0
    seconds: float = 0.0
    completed: int = 0
    failed: int = 0


class MaterialRow(BaseModel):
    material: str
    prints: int = 0
    grams: float = 0.0
    seconds: float = 0.0
    completed: int = 0
    failed: int = 0


class ColorRow(BaseModel):
    color: str
    prints: int = 0
    grams: float = 0.0


class DurationRow(BaseModel):
    bucket: str
    prints: int = 0


class Totals(BaseModel):
    prints: int = 0
    completed: int = 0
    failed: int = 0
    grams: float = 0.0
    cost: float = 0.0
    energy_kwh: float = 0.0
    energy_cost: float = 0.0
    quantity: int = 0
    seconds: float = 0.0
    printers: int = 0


class LongestRecord(BaseModel):
    archive_id: int
    print_name: str | None = None
    seconds: float = 0.0


class HeaviestRecord(BaseModel):
    archive_id: int
    print_name: str | None = None
    grams: float = 0.0


class CostliestRecord(BaseModel):
    archive_id: int
    print_name: str | None = None
    cost: float = 0.0


class Records(BaseModel):
    longest: LongestRecord | None = None
    heaviest: HeaviestRecord | None = None
    costliest: CostliestRecord | None = None
    success_streak: int = 0


class ArchiveAggregate(BaseModel):
    timezone: str
    granularity: str
    buckets: list[Bucket]
    by_hour_of_day: list[HourCell]
    by_printer: list[PrinterRow]
    by_material: list[MaterialRow]
    by_color: list[ColorRow]
    by_duration: list[DurationRow]
    totals: Totals
    records: Records
