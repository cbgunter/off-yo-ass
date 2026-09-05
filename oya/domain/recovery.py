"""Today's value, 30-day baseline, and delta for each synced Garmin
metric, plus the latest blood pressure reading. Pulled out of
oya/api/dashboard.py in phase 2 so the coach worker sees exactly the same
numbers the Dashboard screen renders — one query-and-baseline path, two
consumers, instead of two copies that could quietly drift apart.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from oya.domain.baselines import Baseline, compute_baseline
from oya.store.table import Entity, get_latest, query_range

BASELINE_WINDOW_DAYS = 31  # 30 days of history plus today


@dataclass(frozen=True)
class MetricSnapshot:
    label: str
    unit: str | None
    today: float | None
    average: float | None
    delta: float | None
    delta_pct: float | None
    days: int
    building: bool


@dataclass(frozen=True)
class BloodPressureSnapshot:
    systolic: int
    diastolic: int
    when: str
    delta_systolic: int | None
    delta_diastolic: int | None


@dataclass(frozen=True)
class RecoverySnapshot:
    sleep: MetricSnapshot
    resting_heart_rate: MetricSnapshot
    hrv: MetricSnapshot
    stress: MetricSnapshot
    body_battery: MetricSnapshot
    steps: MetricSnapshot
    weight: MetricSnapshot
    blood_pressure: BloodPressureSnapshot | None


def _metric_snapshot(
    entity: str, field_name: str, label: str, unit: str | None = None
) -> MetricSnapshot:
    end = date.today().isoformat()
    start = (date.today() - timedelta(days=BASELINE_WINDOW_DAYS)).isoformat()
    items = query_range(entity, start, end)  # ascending by sk (date)

    if not items:
        return MetricSnapshot(
            label=label,
            unit=unit,
            today=None,
            average=None,
            delta=None,
            delta_pct=None,
            days=0,
            building=True,
        )

    *history_items, today_item = items
    today_value = today_item.get(field_name)
    history_values = [
        float(item[field_name]) for item in history_items if item.get(field_name) is not None
    ]

    result = compute_baseline(
        float(today_value) if today_value is not None else None, history_values
    )

    if isinstance(result, Baseline):
        return MetricSnapshot(
            label=label,
            unit=unit,
            today=result.today,
            average=result.average,
            delta=result.delta,
            delta_pct=result.delta_pct,
            days=result.days,
            building=False,
        )
    return MetricSnapshot(
        label=label,
        unit=unit,
        today=result.today,
        average=None,
        delta=None,
        delta_pct=None,
        days=result.days,
        building=True,
    )


def _blood_pressure_snapshot() -> BloodPressureSnapshot | None:
    items = get_latest(Entity.BP, limit=2)
    if not items:
        return None

    latest, previous = items[0], items[1] if len(items) > 1 else None
    delta_systolic = int(latest["systolic"]) - int(previous["systolic"]) if previous else None
    delta_diastolic = int(latest["diastolic"]) - int(previous["diastolic"]) if previous else None

    return BloodPressureSnapshot(
        systolic=int(latest["systolic"]),
        diastolic=int(latest["diastolic"]),
        when=latest["sk"],
        delta_systolic=delta_systolic,
        delta_diastolic=delta_diastolic,
    )


def get_recovery_snapshot() -> RecoverySnapshot:
    return RecoverySnapshot(
        sleep=_metric_snapshot(Entity.SLEEP, "minutes", "Sleep", unit="min"),
        resting_heart_rate=_metric_snapshot(Entity.RHR, "bpm", "Resting heart rate", unit="bpm"),
        hrv=_metric_snapshot(Entity.HRV, "overnight_avg_ms", "HRV", unit="ms"),
        stress=_metric_snapshot(Entity.STRESS, "avg", "Stress"),
        body_battery=_metric_snapshot(Entity.BODYBATT, "at_wake", "Body battery"),
        steps=_metric_snapshot(Entity.STEPS, "count", "Steps"),
        weight=_metric_snapshot(Entity.WEIGHT, "lbs", "Weight", unit="lbs"),
        blood_pressure=_blood_pressure_snapshot(),
    )
