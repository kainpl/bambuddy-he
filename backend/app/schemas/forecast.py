"""Response schemas for the server-computed forecast endpoints (Task 3,
2026-08-29 forecast-server-side).

``SkuForecastRowResponse`` mirrors ``forecast_engine.SkuForecastRow`` field for
field — every Optional stays Optional (the T2 handoff: ``subtype``/``brand``/
``color_name``/``rgba`` are freely None, the rate and every derived value can
be None on a tier-none row; a None must serialize as JSON null, never 500).
The pagination envelope reuses the archives ``PaginationMeta`` shape so the
client renders both lists with one idiom.
"""

from datetime import date

from pydantic import BaseModel

from backend.app.schemas.archive import PaginationMeta
from backend.app.schemas.print_queue import UTCDatetime


class SkuForecastRowResponse(BaseModel):
    """One finished SKU row — ``forecast_engine.SkuForecastRow``, serialized."""

    material: str | None
    subtype: str | None
    brand: str | None
    color_name: str | None
    rgba: str | None
    total_spools: int
    total_remaining_g: float
    total_label_g: float
    avg_spool_label_g: float | None
    total_used_g: float
    rate_g_day: float | None
    rate_tier: str  # "history" | "delta" | "none"
    std_dev: float | None
    eff_lead_time_days: int
    safety_stock_g: float | None
    reorder_point_g: float | None
    days_remaining: int | None
    projected_empty_date: date | None
    days_until_rop: int | None
    reorder_trigger_date: date | None
    stock_break_alert: bool
    reorder_alert: bool
    alerts_snoozed: bool
    spool_ids: list[int]

    class Config:
        from_attributes = True


class ForecastListPage(BaseModel):
    """``GET /inventory/forecast`` — one server-sorted, server-filtered page.

    ``alert_count`` counts un-snoozed alert rows across the WHOLE farm (the
    client's badge reads the unfiltered set); ``meta.total`` counts the
    filtered set.
    """

    items: list[SkuForecastRowResponse]
    meta: PaginationMeta
    alert_count: int
    global_lead_time_days: int


class ForecastChartSku(BaseModel):
    """The 4-part SKU identity of one chart series, as stored (None preserved)."""

    material: str | None
    subtype: str | None
    brand: str | None
    color_name: str | None


class ForecastChartSeries(BaseModel):
    """One of the top-5 SKUs: burned grams per day + the depletion projection.

    ``usage`` entries are ``[iso_date, grams]`` (day-bucketed, reset spools
    included — the record of what was burned); ``projection`` entries are
    ``[iso_date, grams]`` with the client's Math.round applied, ending at the
    first zero.
    """

    sku: ForecastChartSku
    rgba: str | None
    rop_g: float
    usage: list[tuple[date, float]]
    projection: list[tuple[date, int]]


class ForecastChartResponse(BaseModel):
    series: list[ForecastChartSeries]


class ForecastLogisticsRow(BaseModel):
    """``CartLogisticsRow``'s computation for one shopping-list item.

    ``series`` is None when the SKU has no forecast row or no positive rate
    (the client renders its "no usage data" placeholder); otherwise it is the
    depletion-bump-depletion timeline with the arrival date present TWICE
    (pre-bump, post-bump — the client's vertical-step trick, kept so the chart
    renders an instant jump).

    ``stock_break_day`` is the banner's headline number — the client's
    ``stockBreaksAt`` memo verbatim: ``floor(remaining / rate)`` when that
    lands before the lead time, else None. Deliberately NOT the series' first
    zero (rounding puts that a day later in general), and the flag is exactly
    its non-nullness (the client's ``hasBreak = stockBreaksAt !== null``).
    """

    item_id: int
    series: list[tuple[date, int]] | None
    arrival_day: int | None
    rop_g: float | None
    safety_stock_g: float | None
    stock_break_day: int | None
    stock_break_before_arrival: bool


# ---------- farm forecast (spec 2026-09-06, Slice B) ----------
#
# A second, unrelated forecast: when the farm's machines and queues empty out,
# not the inventory's SKUs. Kept in this module because the brief's routes
# import it as ``backend.app.schemas.forecast`` — the name is shared, the
# concerns are not; nothing below refers to anything above.


class FarmForecastOut(BaseModel):
    free_at: UTCDatetime
    free_seconds: int


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
