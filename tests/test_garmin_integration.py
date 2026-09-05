import json
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import patch

from oya.integrations.garmin import fetch_activities, fetch_day

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "garmin_day.json").read_text())
ACTIVITIES_FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "garmin_activities.json").read_text()
)


class _FakeClient:
    """Stands in for garminconnect.Garmin, returning the recorded fixture
    regardless of the date argument — fetch_day always calls each method
    with the same ISO date string, so there's nothing to branch on."""

    def get_sleep_data(self, _iso):
        return FIXTURE["sleep"]

    def get_heart_rates(self, _iso):
        return FIXTURE["heart_rates"]

    def get_hrv_data(self, _iso):
        return FIXTURE["hrv"]

    def get_stress_data(self, _iso):
        return FIXTURE["stress"]

    def get_body_battery(self, _iso):
        return FIXTURE["body_battery"]

    def get_stats(self, _iso):
        return FIXTURE["stats"]

    def get_body_composition(self, _start, _end):
        return FIXTURE["weight"]

    def get_activities_by_date(self, _start, _end):
        return ACTIVITIES_FIXTURE["activities"]


def test_fetch_day_against_a_recorded_real_response():
    """This fixture is a trimmed real response from a live account, not
    invented data — the null-prefixed bodyBatteryValuesArray in it is
    exactly the shape that caused a real bug (see the regression test
    below), and sleep/HRV really were null that night, which fetch_day
    must handle without crashing.
    """
    with patch("oya.integrations.garmin._client", return_value=_FakeClient()):
        metrics = fetch_day(date(2026, 9, 3))

    assert metrics.resting_heart_rate == 62
    assert metrics.stress_avg == 40
    assert metrics.steps == 1591

    # Genuinely absent that night in the real account — not a parsing bug.
    assert metrics.sleep_minutes is None
    assert metrics.hrv_overnight_avg is None
    assert metrics.weight_lbs is None


def test_body_battery_at_wake_skips_leading_null_placeholders():
    """The real bug: bodyBatteryValuesArray's first entries are often
    [timestamp, null] placeholders before the watch takes its first
    actual reading. Blindly taking index 0 silently wrote null forever;
    this has to walk forward to the first real value (49 in the fixture,
    not the null at index 0).
    """
    with patch("oya.integrations.garmin._client", return_value=_FakeClient()):
        metrics = fetch_day(date(2026, 9, 3))

    assert metrics.body_battery_at_wake == 49


def test_fetch_activities_maps_the_raw_garmin_shape():
    with patch("oya.integrations.garmin._client", return_value=_FakeClient()):
        activities = fetch_activities(date(2026, 9, 3))

    assert len(activities) == 2

    ride = activities[0]
    assert ride.activity_id == 987654321
    assert ride.type_key == "cycling"
    assert ride.start_gmt == datetime(2026, 9, 3, 19, 41, 12, tzinfo=UTC)
    # duration comes back from Garmin in seconds -- this must be minutes.
    assert ride.duration_min == 45.5
    assert ride.distance_m == 18452.3
    assert ride.calories == 612.0


def test_fetch_activities_defaults_type_key_when_garmin_omits_activity_type():
    client = _FakeClient()
    with patch("oya.integrations.garmin._client", return_value=client):
        with patch.object(
            client,
            "get_activities_by_date",
            return_value=[
                {
                    "activityId": 1,
                    "activityType": None,
                    "startTimeGMT": "2026-09-03 12:00:00",
                    "duration": 600.0,
                }
            ],
        ):
            activities = fetch_activities(date(2026, 9, 3))

    assert activities[0].type_key == "other"


def test_fetch_activities_skips_entries_missing_an_id_or_start_time():
    """activity_id + start_gmt together are the idempotency key
    sync_garmin.py's writer relies on -- an entry missing either can't be
    written safely, so it's dropped rather than guessed at."""
    client = _FakeClient()
    with patch("oya.integrations.garmin._client", return_value=client):
        with patch.object(
            client,
            "get_activities_by_date",
            return_value=[
                {"activityId": None, "startTimeGMT": "2026-09-03 12:00:00", "duration": 600.0},
                {"activityId": 2, "startTimeGMT": None, "duration": 600.0},
            ],
        ):
            activities = fetch_activities(date(2026, 9, 3))

    assert activities == []
