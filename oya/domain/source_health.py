"""Freshness budgets and the breach/recovery state machine that decides
whether a stale-source push should fire — once per breach, reset on
recovery, never a daily nag. Pure logic, no I/O: the caller supplies the
last-success timestamp and whatever `notified_at` the stored SOURCE_HEALTH
record currently has, and gets back what the new state should be.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

# Only Garmin exists in phase 1. Calendar/weather/Concept2/Peloton get
# entries here when their syncs land in later phases.
FRESHNESS_BUDGETS: dict[str, timedelta] = {
    "garmin": timedelta(hours=36),
}


@dataclass(frozen=True)
class HealthCheck:
    source: str
    status: str  # "fresh" | "stale"
    last_success: datetime | None
    should_notify: bool
    message: str | None = None


def evaluate(
    source: str,
    *,
    last_success: datetime | None,
    already_notified: bool,
    now: datetime | None = None,
) -> HealthCheck:
    """`already_notified` is whatever the stored record's `notified_at`
    currently says. Staleness detection here is deliberately generic — it
    doesn't try to diagnose *why* a source went quiet (expired token vs.
    an outage vs. a bug), just that it did, and pushes exactly once per
    breach until the caller records a fresh success and clears the flag.
    """
    now = now or datetime.now(UTC)
    budget = FRESHNESS_BUDGETS[source]

    is_stale = last_success is None or (now - last_success) > budget

    if not is_stale:
        return HealthCheck(
            source=source, status="fresh", last_success=last_success, should_notify=False
        )

    hours = budget.total_seconds() / 3600
    return HealthCheck(
        source=source,
        status="stale",
        last_success=last_success,
        should_notify=not already_notified,
        message=f"{source.capitalize()} hasn't synced in over {hours:.0f} hours.",
    )
