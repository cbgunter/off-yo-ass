"""Bedtime nudge at 21:00, timed off tomorrow's first calendar event.
Deliberately not an LLM call -- a template built from a real timestamp is
both cheaper and more predictable than asking a model to do arithmetic on
a clock.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from oya.integrations.calendar import get_snapshot
from oya.integrations.webpush import send_push
from oya.store.table import Entity, query_all

TITLE = "Off yo ass"
TARGET_SLEEP_HOURS = 8.5


def _format_time(dt: datetime) -> str:
    # Not strftime("%-H:%M") -- that flag is a glibc extension and raises
    # on Windows, which matters for running this locally, not just on the
    # Linux Lambda runtime it actually ships to.
    return f"{dt.hour}:{dt.minute:02d}"


def build_nudge() -> str:
    snapshot = get_snapshot()
    if not snapshot.tomorrow_first:
        return "Nothing on the calendar first thing tomorrow. Lights out on your own call."

    wake_by = snapshot.tomorrow_first.start
    lights_out = wake_by - timedelta(hours=TARGET_SLEEP_HOURS)
    return (
        f"First thing tomorrow is at {_format_time(wake_by)}. "
        f"Lights out by {_format_time(lights_out)}."
    )


def handler(event: dict, context: object) -> dict:
    body = build_nudge()
    sent = sum(
        1
        for sub in query_all(Entity.SUB)
        if send_push(sub["subscription"], TITLE, body, url="/call")
    )
    return {"status": "ok", "body": body, "sent": sent}
