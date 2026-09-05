from unittest.mock import MagicMock, patch

from oya.integrations.calendar import CalendarSnapshot
from oya.integrations.weather import WeatherWindow
from oya.prompts.coach import CoachResponse, Prescription
from oya.prompts.validate import is_clean
from oya.store.table import Entity, put_item
from oya.workers.coach import build_context, generate_call

CLEAN = CoachResponse(
    headline="Resting heart rate is 6 bpm under your 30-day average.",
    prescription=Prescription(
        activity="row_c2", duration_min=25, intensity="moderate", window="17:30-18:00"
    ),
    why="Recovery is good and nothing's on the calendar tonight.",
    fallback="A short walk if the erg's not happening.",
    skip_ok=False,
)

DIRTY = CoachResponse(
    headline="Great job on that ride!",
    prescription=CLEAN.prescription,
    why="You've got this.",
    fallback="Keep it up.",
    skip_ok=False,
)

EMPTY_CALENDAR = CalendarSnapshot(remaining_today=[], tomorrow_first=None, travelling=False)
CLEAR_WEATHER = WeatherWindow(short_forecast="Clear", temperature_f=68, precipitation_chance=10)


def _mock_client(*parsed_outputs):
    client = MagicMock()
    client.messages.parse.side_effect = [MagicMock(parsed_output=p) for p in parsed_outputs]
    return client


def _patched(*parsed_outputs):
    """Patches the coach's Anthropic client plus its calendar/weather
    calls with a quiet evening, so tests exercise only the
    generate-validate-retry-fallback logic, not the integrations."""
    return (
        patch("oya.workers.coach._client", return_value=_mock_client(*parsed_outputs)),
        patch("oya.workers.coach.get_calendar_snapshot", return_value=EMPTY_CALENDAR),
        patch("oya.workers.coach.get_evening_window", return_value=CLEAR_WEATHER),
    )


def test_generate_call_accepts_a_clean_first_attempt(dynamodb_table):
    client_patch, cal_patch, weather_patch = _patched(CLEAN)
    with client_patch as mock_client, cal_patch, weather_patch:
        result = generate_call()

    assert result.headline == CLEAN.headline
    # Only one call -- a clean first attempt must not trigger a retry.
    assert mock_client.return_value.messages.parse.call_count == 1


def test_generate_call_regenerates_once_then_uses_the_new_clean_result(dynamodb_table):
    client_patch, cal_patch, weather_patch = _patched(DIRTY, CLEAN)
    with client_patch, cal_patch, weather_patch:
        result = generate_call()

    assert result.headline == CLEAN.headline


def test_generate_call_falls_back_to_a_template_after_two_dirty_attempts(dynamodb_table):
    # A real recovery number so the fallback's own logic has something to
    # branch on -- an elevated resting heart rate should trigger rest.
    put_item(Entity.RHR, "2026-06-14", {"bpm": 60.0})
    put_item(Entity.RHR, "2026-06-15", {"bpm": 68.0})

    client_patch, cal_patch, weather_patch = _patched(DIRTY, DIRTY)
    with client_patch, cal_patch, weather_patch:
        result = generate_call()

    # Never the dirty model output, no matter what -- a bad model day must
    # never become a bad push.
    assert result.headline != DIRTY.headline
    assert is_clean(result.headline)
    assert is_clean(result.why)
    assert is_clean(result.fallback)


def test_build_context_survives_calendar_and_weather_being_unavailable(dynamodb_table):
    """Calendar (not yet bootstrapped, or Google having a bad day) and
    weather (missing grid config, or NWS being down) are both external
    and optional in spirit -- a failure in either must not take the whole
    call down with it, the same way a stale source never blocks anything
    else in this app. Recovery comes from this app's own data, so that
    one path is allowed to raise for real.
    """
    with (
        patch("oya.workers.coach.get_calendar_snapshot", side_effect=RuntimeError("no token yet")),
        patch("oya.workers.coach.get_evening_window", side_effect=RuntimeError("NWS is down")),
    ):
        context = build_context()

    assert "Calendar unavailable." in context
    assert "Weather unavailable." in context
    assert "Recovery:" in context  # the rest of the context still built normally
