from datetime import datetime, timedelta
from unittest.mock import patch

from oya.clock import EASTERN
from oya.domain.recovery import MetricSnapshot, RecoverySnapshot
from oya.integrations.calendar import CalendarEvent, CalendarSnapshot
from oya.store.table import Entity, get_latest
from oya.workers import bedtime
from oya.workers.bedtime import build_nudge, handler


def _tomorrow_at(hour: int, minute: int = 0) -> datetime:
    """build_nudge measures against datetime.now(), so a fixed calendar
    date would drift in and out of "tomorrow" as the suite runs."""
    d = (datetime.now(EASTERN) + timedelta(days=1)).date()
    return datetime(d.year, d.month, d.day, hour, minute, tzinfo=EASTERN)


def _metric(*, delta=None, delta_pct=None, building=False) -> MetricSnapshot:
    return MetricSnapshot(
        label="m",
        unit=None,
        today=0.0,
        average=0.0,
        delta=delta,
        delta_pct=delta_pct,
        days=30,
        building=building,
    )


def _recovery(*, sleep=None, hrv=None) -> RecoverySnapshot:
    baseline = _metric(delta=0.0, delta_pct=0.0)
    return RecoverySnapshot(
        sleep=sleep or baseline,
        resting_heart_rate=baseline,
        hrv=hrv or baseline,
        stress=baseline,
        body_battery=baseline,
        steps=baseline,
        weight=baseline,
    )


def _calendar(first_at: datetime | None) -> CalendarSnapshot:
    event = (
        None
        if first_at is None
        else CalendarEvent(summary="x", start=first_at, end=first_at, location=None)
    )
    return CalendarSnapshot(remaining_today=[], tomorrow_first=event, travelling=False)


def _run_build_nudge(*, calendar: CalendarSnapshot, recovery: RecoverySnapshot) -> str:
    with (
        patch.object(bedtime, "get_snapshot", return_value=calendar),
        patch.object(bedtime, "get_recovery_snapshot", return_value=recovery),
    ):
        return build_nudge()


def test_default_bedtime_is_eleven_pm_with_nothing_pulling_it_earlier():
    body = _run_build_nudge(calendar=_calendar(None), recovery=_recovery())
    assert body == "Lights out by 23:00."


def test_a_late_first_event_tomorrow_does_not_move_bedtime():
    body = _run_build_nudge(calendar=_calendar(_tomorrow_at(14, 0)), recovery=_recovery())
    assert body == "Lights out by 23:00."


def test_an_early_start_pulls_bedtime_back_by_target_sleep():
    body = _run_build_nudge(calendar=_calendar(_tomorrow_at(6, 30)), recovery=_recovery())
    assert body == "First thing tomorrow is at 6:30. Lights out by 22:00."


def test_low_hrv_winds_down_early_and_states_the_number():
    body = _run_build_nudge(
        calendar=_calendar(None), recovery=_recovery(hrv=_metric(delta_pct=-14.0))
    )
    assert body == "HRV is 14% under baseline. Lights out by 22:15."


def test_sleep_debt_winds_down_early_and_states_the_number():
    body = _run_build_nudge(
        calendar=_calendar(None), recovery=_recovery(sleep=_metric(delta=-72.0))
    )
    assert body == "Slept 72 min under your baseline last night. Lights out by 22:15."


def test_building_baseline_produces_no_vitals_reason():
    body = _run_build_nudge(
        calendar=_calendar(None),
        recovery=_recovery(hrv=_metric(delta_pct=-30.0, building=True)),
    )
    assert body == "Lights out by 23:00."


def test_bedtime_push_deep_links_to_the_call(dynamodb_table):
    """The nudge has to open The Call on tap, not the home page -- a
    missing url= silently falls back to "/" in send_push."""
    calendar = _calendar(_tomorrow_at(7, 0))
    with (
        patch.object(bedtime, "get_snapshot", return_value=calendar),
        patch.object(bedtime, "get_recovery_snapshot", return_value=_recovery()),
        patch.object(bedtime, "query_all", return_value=[{"subscription": {"endpoint": "x"}}]),
        patch.object(bedtime, "send_push", return_value=True) as send_push,
    ):
        result = handler({}, None)

    assert result["status"] == "ok"
    assert result["sent"] == 1
    _, kwargs = send_push.call_args
    assert kwargs["url"] == "/call"


def test_bedtime_persists_the_nudge_for_the_call_screen(dynamodb_table):
    with (
        patch.object(bedtime, "get_snapshot", return_value=_calendar(None)),
        patch.object(bedtime, "get_recovery_snapshot", return_value=_recovery()),
        patch.object(bedtime, "query_all", return_value=[]),
        patch.object(bedtime, "send_push", return_value=True),
    ):
        result = handler({}, None)

    stored = get_latest(Entity.BEDTIME)
    assert stored and stored[0]["body"] == result["body"] == "Lights out by 23:00."
