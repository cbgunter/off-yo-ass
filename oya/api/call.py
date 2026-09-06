"""The Call: today's prescription, check-in, feel tap, and override. The
generation logic itself lives in oya/workers/coach.py; this router is the
API surface on top of it, reused directly by /override rather than
duplicating the coach call.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from oya.api.auth import User, get_current_user
from oya.clock import eastern_date
from oya.store.table import Entity, get_latest, put_item
from oya.workers.coach import generate_call, store_call

router = APIRouter(prefix="/api/call", tags=["call"])

RESULTS = {"did_it", "partial", "no"}
SKIP_REASONS = {
    "too_tired",
    "no_time",
    "travelling",
    "weather",
    "didnt_feel_like_it",
    "something_hurt",
}
FEELINGS = {"easy", "about_right", "brutal"}


class CallOut(BaseModel):
    headline: str
    prescription: dict
    why: str
    fallback: str
    skip_ok: bool
    overridden: bool = False


class BedtimeOut(BaseModel):
    body: str


class CheckinIn(BaseModel):
    result: str
    skip_reason: str | None = None


class FeelIn(BaseModel):
    feel: str


def _to_call_out(item: dict) -> CallOut:
    return CallOut(
        headline=item["headline"],
        prescription=item["prescription"],
        why=item["why"],
        fallback=item["fallback"],
        skip_ok=bool(item.get("skip_ok", False)),
        overridden=bool(item.get("overridden", False)),
    )


@router.get("/today", response_model=None)
def get_today(user: User = Depends(get_current_user)) -> CallOut | None:
    """The call that currently stands. It's the afternoon's prescription
    until the coach writes the next one at 15:45 ET the following day --
    deliberately not filtered to the current date, so it stays on screen
    through the evening check-in and into the next morning."""
    items = get_latest(Entity.CALL)
    return _to_call_out(items[0]) if items else None


@router.get("/bedtime", response_model=None)
def get_bedtime(user: User = Depends(get_current_user)) -> BedtimeOut | None:
    """The bedtime nudge that currently stands -- shown on The Call screen
    until the next night's 21:00 run replaces it."""
    items = get_latest(Entity.BEDTIME)
    return BedtimeOut(body=items[0]["body"]) if items else None


@router.post("/checkin", status_code=204, response_model=None)
def checkin(body: CheckinIn, user: User = Depends(get_current_user)) -> None:
    if body.result not in RESULTS:
        raise HTTPException(400, f"Unknown result: {body.result}")
    if body.skip_reason and body.skip_reason not in SKIP_REASONS:
        raise HTTPException(400, f"Unknown skip reason: {body.skip_reason}")

    when = datetime.now(UTC).isoformat()
    put_item(Entity.OUTCOME, when, {"result": body.result, "skip_reason": body.skip_reason})


@router.post("/feel", status_code=204, response_model=None)
def feel(body: FeelIn, user: User = Depends(get_current_user)) -> None:
    if body.feel not in FEELINGS:
        raise HTTPException(400, f"Unknown feel: {body.feel}")
    when = datetime.now(UTC).isoformat()
    put_item(Entity.FEEL, when, {"feel": body.feel})


@router.post("/not-tonight", status_code=204, response_model=None)
def not_tonight(user: User = Depends(get_current_user)) -> None:
    """Recorded as an immediate override outcome -- no regeneration,
    unlike /override below."""
    when = datetime.now(UTC).isoformat()
    put_item(Entity.OUTCOME, when, {"result": "no", "skip_reason": "override"})


@router.post("/override")
def override(user: User = Depends(get_current_user)) -> CallOut:
    today = eastern_date()
    existing = get_latest(Entity.CALL, sk=today)
    exclude = existing[0]["prescription"]["activity"] if existing else None

    result = generate_call(exclude_activity=exclude)
    store_call(result, overridden=True)
    return CallOut(
        headline=result.headline,
        prescription=result.prescription.model_dump(),
        why=result.why,
        fallback=result.fallback,
        skip_ok=result.skip_ok,
        overridden=True,
    )
