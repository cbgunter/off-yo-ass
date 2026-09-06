"""The app's one wall clock. Every scheduled worker runs on
America/New_York (see infra/stacks/workers_stack.py), so the day a call or
a bedtime nudge belongs to is the Eastern calendar day, not UTC. Keying
those rows by a UTC date meant the daily call vanished from the screen at
20:00 ET, when UTC had already rolled to tomorrow -- exactly when the
evening check-in and bedtime notifications send you there.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")


def eastern_date() -> str:
    """Today's date in America/New_York as an ISO string, for use as a
    per-day DynamoDB sort key."""
    return datetime.now(EASTERN).date().isoformat()
