"""Quick-log for what Garmin can't see: yard work, wood splitting, the
Longwood walk, and blood pressure. Per BRANDING.md these get identical
treatment to Peloton and rowing — no "other" bucket, so the activity
types are a fixed, named set rather than a free-text field."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from oya.api.auth import User, get_current_user
from oya.store.table import Entity, put_item

router = APIRouter(prefix="/api/quicklog", tags=["quicklog"])

ACTIVITY_TYPES = {"yard_work", "wood_splitting", "longwood_walk"}


class ActivityIn(BaseModel):
    activity_type: str
    duration_min: float
    when: datetime | None = None


class BloodPressureIn(BaseModel):
    systolic: int
    diastolic: int
    when: datetime | None = None


@router.post("/activity", status_code=204, response_model=None)
# response_model=None is required: `from __future__ import annotations`
# turns `-> None` into the string "None", which defeats FastAPI's usual
# fast path for inferring "no response body" and raises an assertion
# instead. See oya/api/push.py for the full explanation.
def log_activity(body: ActivityIn, user: User = Depends(get_current_user)) -> None:
    if body.activity_type not in ACTIVITY_TYPES:
        raise HTTPException(400, f"Unknown activity type: {body.activity_type}")

    when = body.when or datetime.now(UTC)
    put_item(
        Entity.ACTIVITY,
        when.isoformat(),
        {
            "activity_type": body.activity_type,
            "duration_min": body.duration_min,
            "source": "manual",
        },
    )


@router.post("/bp", status_code=204, response_model=None)
def log_blood_pressure(body: BloodPressureIn, user: User = Depends(get_current_user)) -> None:
    when = body.when or datetime.now(UTC)
    put_item(Entity.BP, when.isoformat(), {"systolic": body.systolic, "diastolic": body.diastolic})
