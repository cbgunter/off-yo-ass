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
from oya.domain.recovery import MetricSnapshot, get_recovery_snapshot

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


class DashboardResponse(BaseModel):
    sleep: MetricPoint
    resting_heart_rate: MetricPoint
    hrv: MetricPoint
    stress: MetricPoint
    body_battery: MetricPoint
    steps: MetricPoint
    weight: MetricPoint


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
    )
