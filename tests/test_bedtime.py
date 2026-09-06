from datetime import UTC, datetime
from unittest.mock import patch

from oya.integrations.calendar import CalendarEvent, CalendarSnapshot
from oya.workers.bedtime import handler

SNAPSHOT = CalendarSnapshot(
    remaining_today=[],
    tomorrow_first=CalendarEvent(
        summary="Standup",
        start=datetime(2026, 9, 6, 9, 0, tzinfo=UTC),
        end=datetime(2026, 9, 6, 9, 30, tzinfo=UTC),
        location=None,
    ),
    travelling=False,
)


def test_bedtime_push_deep_links_to_the_call():
    """The 21:00 nudge has to open The Call on tap, not the home page --
    it's the same evening screen the 20:30 check-in points at. A missing
    url= silently falls back to "/" in send_push."""
    with (
        patch("oya.workers.bedtime.get_snapshot", return_value=SNAPSHOT),
        patch("oya.workers.bedtime.query_all", return_value=[{"subscription": {"endpoint": "x"}}]),
        patch("oya.workers.bedtime.send_push", return_value=True) as send_push,
    ):
        result = handler({}, None)

    assert result["status"] == "ok"
    assert result["sent"] == 1
    _, kwargs = send_push.call_args
    assert kwargs["url"] == "/call"
