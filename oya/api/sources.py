"""Real per-source freshness, replacing the phase-0 hardcoded list.
Calendar/weather/Concept2/Peloton still report "not connected" — those
sync in later phases."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from oya.api.auth import User, get_current_user
from oya.store.table import Entity, get_latest

router = APIRouter(prefix="/api/sources", tags=["sources"])


class SourceStatus(BaseModel):
    name: str
    note: str
    status: str  # "connected" | "stale" | "not_connected"
    last_synced: str | None = None


NOT_YET_BUILT = [
    SourceStatus(
        name="Google Calendar", note="tonight, tomorrow, travel", status="not_connected"
    ),
    SourceStatus(
        name="Weather",
        note="National Weather Service, no key needed",
        status="not_connected",
    ),
    SourceStatus(name="Concept2", note="rowing, including ErgData", status="not_connected"),
    SourceStatus(name="Peloton", note="ride and strength detail", status="not_connected"),
]


def _garmin_status() -> SourceStatus:
    note = "sleep, HRV, resting heart rate, weight"
    records = get_latest(Entity.SOURCE_HEALTH, sk="garmin")
    if not records:
        return SourceStatus(name="Garmin", note=note, status="not_connected")

    record = records[0]
    status = "connected" if record.get("status") == "fresh" else "stale"
    return SourceStatus(
        name="Garmin", note=note, status=status, last_synced=record.get("last_success")
    )


@router.get("")
def get_sources(user: User = Depends(get_current_user)) -> list[SourceStatus]:
    return [_garmin_status(), *NOT_YET_BUILT]
