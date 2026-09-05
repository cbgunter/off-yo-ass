"""Nightly Garmin sync. Pulls yesterday's recovery data and discrete
activities, writes the daily entities, records a SYNC_RUN, evaluates
source health, and sends one push if Garmin just went stale. One worker
doing sync-then-healthcheck-then-alert, not three separate jobs — invoked
by the EventBridge Scheduler rule in infra/stacks/workers_stack.py at
04:30 America/New_York, every day, DST included.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from oya.domain.source_health import evaluate
from oya.integrations.garmin import (
    DayMetrics,
    GarminActivity,
    GarminNotBootstrapped,
    fetch_activities,
    fetch_day,
)
from oya.integrations.webpush import send_push
from oya.store.table import Entity, get_latest, put_item, query_all

SOURCE = "garmin"


def _now() -> datetime:
    return datetime.now(UTC)


def _record_sync_run(status: str, *, rows: int = 0, error: str | None = None) -> None:
    now = _now()
    put_item(
        Entity.SYNC_RUN,
        now.isoformat(),
        {"source": SOURCE, "status": status, "rows": rows, "error": error},
    )


def _notify_all_subscriptions(title: str, body: str) -> None:
    for sub in query_all(Entity.SUB):
        send_push(sub["subscription"], title, body, url="/sources")


def _write_metrics(metrics: DayMetrics) -> int:
    day = metrics.day.isoformat()
    rows = 0

    def write(entity: str, attrs: dict[str, Any]) -> None:
        nonlocal rows
        put_item(entity, day, attrs)
        rows += 1

    if metrics.sleep_minutes is not None:
        write(Entity.SLEEP, {"minutes": metrics.sleep_minutes, "score": metrics.sleep_score})
    if metrics.resting_heart_rate is not None:
        write(Entity.RHR, {"bpm": metrics.resting_heart_rate})
    if metrics.hrv_overnight_avg is not None:
        write(Entity.HRV, {"overnight_avg_ms": metrics.hrv_overnight_avg})
    if metrics.stress_avg is not None:
        write(Entity.STRESS, {"avg": metrics.stress_avg})
    if metrics.body_battery_at_wake is not None:
        write(Entity.BODYBATT, {"at_wake": metrics.body_battery_at_wake})
    if metrics.steps is not None:
        write(Entity.STEPS, {"count": metrics.steps})
    if metrics.weight_lbs is not None:
        write(Entity.WEIGHT, {"lbs": metrics.weight_lbs})

    return rows


def _write_activities(activities: list[GarminActivity]) -> int:
    """sk is the activity's own start time, not datetime.now() -- unlike
    Entity.SYNC_RUN's append-only log, re-running the same day has to
    overwrite the same rows rather than duplicate them, and there's no
    dedup machinery in oya/store/table.py beyond natural key overwrite.
    """
    rows = 0
    for activity in activities:
        put_item(
            Entity.ACTIVITY,
            activity.start_gmt.isoformat(),
            {
                "activity_type": activity.type_key,
                "duration_min": activity.duration_min,
                "source": "garmin",
                "activity_id": activity.activity_id,
                "activity_name": activity.name,
                "calories": activity.calories,
                "distance_m": activity.distance_m,
            },
        )
        rows += 1
    return rows


def _check_and_notify_health(success: bool) -> None:
    existing = get_latest(Entity.SOURCE_HEALTH, sk=SOURCE)
    record = existing[0] if existing else {}

    last_success_str = record.get("last_success")
    last_success = datetime.fromisoformat(last_success_str) if last_success_str else None
    already_notified = bool(record.get("notified_at"))

    now = _now()
    if success:
        last_success = now

    check = evaluate(SOURCE, last_success=last_success, already_notified=already_notified, now=now)

    notified_at = record.get("notified_at")
    if check.status == "fresh":
        notified_at = None
    elif check.should_notify:
        _notify_all_subscriptions("Off yo ass", check.message or f"{SOURCE} hasn't synced.")
        notified_at = now.isoformat()

    put_item(
        Entity.SOURCE_HEALTH,
        SOURCE,
        {
            "status": check.status,
            "last_success": last_success.isoformat() if last_success else None,
            "notified_at": notified_at,
        },
    )


def handler(event: dict, context: object) -> dict:
    yesterday = (_now() - timedelta(days=1)).date()

    try:
        metrics = fetch_day(yesterday)
    except GarminNotBootstrapped as exc:
        _record_sync_run("error", error=str(exc))
        _check_and_notify_health(success=False)
        return {"status": "error", "error": str(exc)}
    except Exception as exc:
        # A sync run must never fail silently — record it, alert on it,
        # then still raise so CloudWatch/Lambda's own error metrics catch
        # it too. Broad on purpose: any unhandled exception here is a
        # source going dark, which is exactly what this worker exists to
        # detect.
        _record_sync_run("error", error=str(exc))
        _check_and_notify_health(success=False)
        raise

    rows = _write_metrics(metrics)

    # Real activity sync -- new and unverified against a real account, in
    # a way fetch_day's field paths already have been. A parsing surprise
    # here must not take down the metrics sync every other worker depends
    # on, so it gets its own isolated failure path (logged as its own
    # SYNC_RUN row) instead of joining the block above and failing the
    # whole run.
    try:
        activities = fetch_activities(yesterday)
        rows += _write_activities(activities)
    except Exception as exc:
        _record_sync_run("activities_error", error=str(exc))

    _record_sync_run("ok", rows=rows)
    _check_and_notify_health(success=True)
    return {"status": "ok", "rows": rows}
