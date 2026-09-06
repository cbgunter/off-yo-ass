"""Bedtime nudge at 21:00. Default lights-out is 23:00 ET; it moves
earlier only for a concrete reason -- an early start tomorrow, or recovery
data saying you need the extra sleep. Deliberately not an LLM call: a
template built from real numbers is cheaper and more predictable than
asking a model to do arithmetic on a clock.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

from oya.clock import EASTERN, eastern_date
from oya.domain.recovery import get_recovery_snapshot
from oya.integrations.calendar import get_snapshot
from oya.integrations.webpush import send_push
from oya.store.table import Entity, put_item, query_all

TITLE = "Off yo ass"

DEFAULT_LIGHTS_OUT = time(23, 0)  # normal bedtime
TARGET_SLEEP_HOURS = 8.5
EARLY_START_BEFORE = time(11, 0)  # tomorrow's first event only counts if before this
WIND_DOWN_EARLY = timedelta(minutes=45)  # how much recovery data pulls it forward
EARLIEST_LIGHTS_OUT = time(20, 0)  # never suggest earlier than this
SLEEP_DEBT_MIN = 45  # minutes under baseline last night that count as a deficit
HRV_DEFICIT_PCT = 10.0  # percent under baseline that counts as suppressed


def _hm(dt: datetime) -> str:
    # Not strftime("%-H:%M") -- that flag is a glibc extension and raises
    # on Windows, which matters for running this locally, not just on the
    # Linux Lambda runtime it ships to.
    return f"{dt.hour}:{dt.minute:02d}"


def _recovery_reason() -> str | None:
    """A vitals-based reason to wind down early, or None. The honesty rule
    applies: no signal is reported while a baseline is still building. A
    bad Garmin day must not take the nudge down, so failure degrades to
    None."""
    try:
        snap = get_recovery_snapshot()
    except Exception:
        return None

    sleep, hrv = snap.sleep, snap.hrv
    if not sleep.building and sleep.delta is not None and sleep.delta <= -SLEEP_DEBT_MIN:
        return f"Slept {abs(sleep.delta):.0f} min under your baseline last night."
    if not hrv.building and hrv.delta_pct is not None and hrv.delta_pct <= -HRV_DEFICIT_PCT:
        return f"HRV is {abs(hrv.delta_pct):.0f}% under baseline."
    return None


def build_nudge() -> str:
    now_et = datetime.now(EASTERN)
    tonight = now_et.date()
    default_dt = datetime.combine(tonight, DEFAULT_LIGHTS_OUT, tzinfo=EASTERN)
    floor_dt = datetime.combine(tonight, EARLIEST_LIGHTS_OUT, tzinfo=EASTERN)

    lights_out = default_dt
    wake_line: str | None = None

    first = get_snapshot().tomorrow_first
    if first is not None and first.start.tzinfo is not None:
        wake_et = first.start.astimezone(EASTERN)
        if wake_et.time() < EARLY_START_BEFORE:
            constrained = wake_et - timedelta(hours=TARGET_SLEEP_HOURS)
            if constrained < lights_out:
                lights_out = constrained
                wake_line = f"First thing tomorrow is at {_hm(wake_et)}."

    reason = _recovery_reason()
    if reason is not None:
        lights_out = min(lights_out, default_dt - WIND_DOWN_EARLY)

    lights_out = max(lights_out, floor_dt)

    parts = [p for p in (wake_line, reason) if p]
    parts.append(f"Lights out by {_hm(lights_out)}.")
    return " ".join(parts)


def handler(event: dict, context: object) -> dict:
    body = build_nudge()
    # One row per Eastern day, so it stays on The Call screen until the
    # next night's nudge replaces it.
    put_item(Entity.BEDTIME, eastern_date(), {"body": body})
    sent = sum(
        1
        for sub in query_all(Entity.SUB)
        if send_push(sub["subscription"], TITLE, body, url="/call")
    )
    return {"status": "ok", "body": body, "sent": sent}
