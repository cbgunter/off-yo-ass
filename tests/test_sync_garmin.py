from datetime import UTC, date, datetime
from unittest.mock import patch

from oya.integrations.garmin import DayMetrics, GarminActivity
from oya.store.table import Entity, query_all, query_range
from oya.workers.sync_garmin import _write_activities, handler

RIDE = GarminActivity(
    activity_id=1,
    type_key="cycling",
    start_gmt=datetime(2026, 9, 3, 19, 41, 12, tzinfo=UTC),
    duration_min=45.5,
    distance_m=18452.3,
    calories=612.0,
    name="Afternoon Ride",
)

METRICS = DayMetrics(day=date(2026, 9, 3), resting_heart_rate=58.0)


def test_write_activities_overwrites_on_rerun_instead_of_duplicating(dynamodb_table):
    """sk is the activity's own start time, not datetime.now() -- re-running
    the same day (e.g. a retried Lambda invocation) must land on the same
    row, not append a second one. There's no dedup machinery in
    oya/store/table.py beyond natural key overwrite, so this is the one
    thing that actually has to be true for idempotency to hold."""
    _write_activities([RIDE])
    _write_activities([RIDE])

    items = query_all(Entity.ACTIVITY)
    assert len(items) == 1
    assert items[0]["activity_type"] == "cycling"
    assert items[0]["source"] == "garmin"


def test_write_activities_converts_seconds_to_minutes_for_the_shared_reader(dynamodb_table):
    """coach.py and weekly_question.py both read duration_min directly and
    print it -- a row in seconds instead of minutes would silently claim
    a 45-minute ride took 2730 minutes."""
    _write_activities([RIDE])
    items = query_range(Entity.ACTIVITY, "2026-09-03", "2026-09-04")
    assert items[0]["duration_min"] == 45.5


def test_handler_keeps_the_metrics_write_when_activity_sync_fails(dynamodb_table):
    """Activity sync is new and unverified against a real account; a
    parsing surprise in it must not take down the metrics sync every
    other worker already depends on."""
    with (
        patch("oya.workers.sync_garmin.fetch_day", return_value=METRICS),
        patch("oya.workers.sync_garmin.fetch_activities", side_effect=RuntimeError("bad shape")),
    ):
        result = handler({}, None)

    assert result["status"] == "ok"
    assert query_all(Entity.RHR) != []  # the metrics write still happened

    runs = query_all(Entity.SYNC_RUN)
    statuses = {r["status"] for r in runs}
    assert "ok" in statuses
    assert "activities_error" in statuses


def test_handler_writes_real_garmin_activities_on_success(dynamodb_table):
    with (
        patch("oya.workers.sync_garmin.fetch_day", return_value=METRICS),
        patch("oya.workers.sync_garmin.fetch_activities", return_value=[RIDE]),
    ):
        result = handler({}, None)

    assert result["status"] == "ok"
    items = query_all(Entity.ACTIVITY)
    assert len(items) == 1
    assert items[0]["source"] == "garmin"
    assert items[0]["activity_type"] == "cycling"
