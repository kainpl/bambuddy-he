"""Wire shapes of the farm forecast (spec 2026-09-06, Slice B)."""

from pydantic import BaseModel

from backend.app.schemas.print_queue import UTCDatetime


class FarmForecastOut(BaseModel):
    free_at: UTCDatetime
    free_seconds: int
    #: Rows of the snapshot with no estimate — why «free at» can read zero
    #: while printers are busy (ruling 2026-09-07, final review I2).
    unknown_prints: int = 0


class RowForecastOut(BaseModel):
    plate_id: int
    proposed_split: dict[int, int] | None = None


class LineForecastOut(BaseModel):
    line_id: int
    now_eta: UTCDatetime
    now_seconds: int | None
    after_eta: UTCDatetime
    after_seconds: int | None
    unknown_prints: int
    unroutable_prints: int
    rows: list[RowForecastOut] = []


class OrderForecastOut(BaseModel):
    project_id: int
    now_eta: UTCDatetime
    now_seconds: int | None
    after_eta: UTCDatetime
    after_seconds: int | None
    machine_seconds: int | None
    unknown_prints: int
    unroutable_prints: int
    ahead_count: int
    assumptions: list[str]


class OrderForecastDetailOut(OrderForecastOut):
    lines: list[LineForecastOut] = []


class ForecastBatchOut(BaseModel):
    farm: FarmForecastOut
    orders: list[OrderForecastOut]
