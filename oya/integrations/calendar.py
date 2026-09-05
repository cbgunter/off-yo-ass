"""Google Calendar (read-only), used for the coach's evening context and
the bedtime nudge's "tomorrow's first event." A separate OAuth flow from
phase 0's Sign-In -- that one never stores a refresh token. This one needs
offline access, set up once by scripts/bootstrap_calendar.py via a real
authorization-code exchange, not the ID-token flow Sign-In uses.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta

import requests

from oya.settings import get_settings

TOKEN_URL = "https://oauth2.googleapis.com/token"
EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"

# Best-effort "is this travel" signal for the coach's context -- not a
# dedicated travel mode (that's phase 4), just enough for the prescription
# to avoid suggesting a hike while you're at an airport.
TRAVEL_KEYWORDS = ("flight", "airport", "departs", "arrives", "layover", "tsa")


@dataclass(frozen=True)
class CalendarEvent:
    summary: str
    start: datetime
    end: datetime
    location: str | None


@dataclass(frozen=True)
class CalendarSnapshot:
    remaining_today: list[CalendarEvent]
    tomorrow_first: CalendarEvent | None
    travelling: bool


def _access_token() -> str:
    settings = get_settings()
    response = requests.post(
        TOKEN_URL,
        data={
            "client_id": settings.google_client_id,
            "client_secret": settings.resolved_google_client_secret(),
            "refresh_token": settings.resolved_google_refresh_token(),
            "grant_type": "refresh_token",
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def _parse_event(item: dict) -> CalendarEvent | None:
    start_raw = item.get("start", {}).get("dateTime") or item.get("start", {}).get("date")
    end_raw = item.get("end", {}).get("dateTime") or item.get("end", {}).get("date")
    if not start_raw or not end_raw:
        return None
    return CalendarEvent(
        summary=item.get("summary") or "(no title)",
        start=datetime.fromisoformat(start_raw),
        end=datetime.fromisoformat(end_raw),
        location=item.get("location"),
    )


def _list_events(token: str, start: datetime, end: datetime) -> list[CalendarEvent]:
    response = requests.get(
        EVENTS_URL,
        headers={"Authorization": f"Bearer {token}"},
        params={
            "timeMin": start.isoformat(),
            "timeMax": end.isoformat(),
            "singleEvents": "true",
            "orderBy": "startTime",
        },
        timeout=10,
    )
    response.raise_for_status()
    events = [_parse_event(item) for item in response.json().get("items", [])]
    return [e for e in events if e is not None]


def _looks_like_travel(events: list[CalendarEvent]) -> bool:
    for event in events:
        text = f"{event.summary} {event.location or ''}".lower()
        if any(keyword in text for keyword in TRAVEL_KEYWORDS):
            return True
    return False


def get_snapshot(now: datetime | None = None) -> CalendarSnapshot:
    now = now or datetime.now(UTC)
    token = _access_token()

    today_end = datetime.combine(now.date(), time(23, 59, 59), tzinfo=now.tzinfo)
    tomorrow = now.date() + timedelta(days=1)
    tomorrow_start = datetime.combine(tomorrow, time(0, 0), tzinfo=now.tzinfo)
    tomorrow_end = datetime.combine(tomorrow, time(23, 59, 59), tzinfo=now.tzinfo)

    remaining_today = _list_events(token, now, today_end)
    tomorrow_events = _list_events(token, tomorrow_start, tomorrow_end)

    return CalendarSnapshot(
        remaining_today=remaining_today,
        tomorrow_first=tomorrow_events[0] if tomorrow_events else None,
        travelling=_looks_like_travel(remaining_today + tomorrow_events),
    )
