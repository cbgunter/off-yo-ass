"""Today's value, 30-day baseline, and delta for each synced metric. A
metric with fewer than 30 days of history reports `building=True` instead
of a fabricated delta — the same honesty rule as everywhere else in this
app.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from oya.api.auth import User, get_current_user
from oya.domain.baselines import Baseline, compute_baseline
from oya.store.table import Entity, get_latest, query_range

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

BASELINE_WINDOW_DAYS = 31  # 30 days of history plus today


class MetricPoint(BaseModel):
    label: str
    unit: str | None = None
    today: float | None
    average: float | None = None
    delta: float | None = None
    delta_pct: float | None = None
    days: int
    building: bool


class BloodPressureReading(BaseModel):
    systolic: int
    diastolic: int
    when: str
    delta_systolic: int | None = None
    delta_diastolic: int | None = None


class DashboardResponse(BaseModel):
    sleep: MetricPoint
    resting_heart_rate: MetricPoint
    hrv: MetricPoint
    stress: MetricPoint
    body_battery: MetricPoint
    steps: MetricPoint
    weight: MetricPoint
    blood_pressure: BloodPressureReading | None = None


def _metric_point(entity: str, field_name: str, label: str, unit: str | None = None) -> MetricPoint:
    end = date.today().isoformat()
    start = (date.today() - timedelta(days=BASELINE_WINDOW_DAYS)).isoformat()
    items = query_range(entity, start, end)  # ascending by sk (date)

    if not items:
        return MetricPoint(label=label, unit=unit, today=None, days=0, building=True)

    *history_items, today_item = items
    today_value = today_item.get(field_name)
    history_values = [
        float(item[field_name]) for item in history_items if item.get(field_name) is not None
    ]

    result = compute_baseline(
        float(today_value) if today_value is not None else None, history_values
    )

    if isinstance(result, Baseline):
        return MetricPoint(
            label=label,
            unit=unit,
            today=result.today,
            average=result.average,
            delta=result.delta,
            delta_pct=result.delta_pct,
            days=result.days,
            building=False,
        )
    return MetricPoint(label=label, unit=unit, today=result.today, days=result.days, building=True)


def _latest_blood_pressure() -> BloodPressureReading | None:
    items = get_latest(Entity.BP, limit=2)
    if not items:
        return None

    latest, previous = items[0], items[1] if len(items) > 1 else None
    delta_systolic = int(latest["systolic"]) - int(previous["systolic"]) if previous else None
    delta_diastolic = int(latest["diastolic"]) - int(previous["diastolic"]) if previous else None

    return BloodPressureReading(
        systolic=int(latest["systolic"]),
        diastolic=int(latest["diastolic"]),
        when=latest["sk"],
        delta_systolic=delta_systolic,
        delta_diastolic=delta_diastolic,
    )


@router.get("")
def get_dashboard(user: User = Depends(get_current_user)) -> DashboardResponse:
    return DashboardResponse(
        sleep=_metric_point(Entity.SLEEP, "minutes", "Sleep", unit="min"),
        resting_heart_rate=_metric_point(Entity.RHR, "bpm", "Resting heart rate", unit="bpm"),
        hrv=_metric_point(Entity.HRV, "overnight_avg_ms", "HRV", unit="ms"),
        stress=_metric_point(Entity.STRESS, "avg", "Stress"),
        body_battery=_metric_point(Entity.BODYBATT, "at_wake", "Body battery"),
        steps=_metric_point(Entity.STEPS, "count", "Steps"),
        weight=_metric_point(Entity.WEIGHT, "lbs", "Weight", unit="lbs"),
        blood_pressure=_latest_blood_pressure(),
    )
