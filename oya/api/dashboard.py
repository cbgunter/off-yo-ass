"""Today's value, 30-day baseline, and delta for each synced metric. A
metric with fewer than 30 days of history reports `building=True` instead
of a fabricated delta — the same honesty rule as everywhere else in this
app.

The actual query-and-baseline logic lives in oya/domain/recovery.py,
shared with the coach worker (oya/workers/coach.py) so both see exactly
the same numbers — this module is just the API shape on top of it.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from oya.api.auth import User, get_current_user
from oya.domain.recovery import BloodPressureSnapshot, MetricSnapshot, get_recovery_snapshot

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


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


def _to_point(s: MetricSnapshot) -> MetricPoint:
    return MetricPoint(
        label=s.label,
        unit=s.unit,
        today=s.today,
        average=s.average,
        delta=s.delta,
        delta_pct=s.delta_pct,
        days=s.days,
        building=s.building,
    )


def _to_reading(bp: BloodPressureSnapshot) -> BloodPressureReading:
    return BloodPressureReading(
        systolic=bp.systolic,
        diastolic=bp.diastolic,
        when=bp.when,
        delta_systolic=bp.delta_systolic,
        delta_diastolic=bp.delta_diastolic,
    )


@router.get("")
def get_dashboard(user: User = Depends(get_current_user)) -> DashboardResponse:
    snap = get_recovery_snapshot()
    return DashboardResponse(
        sleep=_to_point(snap.sleep),
        resting_heart_rate=_to_point(snap.resting_heart_rate),
        hrv=_to_point(snap.hrv),
        stress=_to_point(snap.stress),
        body_battery=_to_point(snap.body_battery),
        steps=_to_point(snap.steps),
        weight=_to_point(snap.weight),
        blood_pressure=_to_reading(snap.blood_pressure) if snap.blood_pressure else None,
    )
