import json
from datetime import date
from pathlib import Path
from unittest.mock import patch

from oya.integrations.garmin import fetch_day

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "garmin_day.json").read_text())


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
