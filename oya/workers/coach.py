"""The daily call. Scheduled at 15:45 America/New_York (see
_scheduled_function in infra/stacks/workers_stack.py) -- reads recovery,
calendar, and weather, and writes one prescription in BRANDING.md's voice,
enforced by a mechanical validator, not just a system-prompt request.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from anthropic import Anthropic

from oya.domain.recovery import RecoverySnapshot, get_recovery_snapshot
from oya.integrations.calendar import CalendarSnapshot
from oya.integrations.calendar import get_snapshot as get_calendar_snapshot
from oya.integrations.weather import WeatherWindow, get_evening_window
from oya.integrations.webpush import send_push
from oya.prompts.coach import SYSTEM_PROMPT, CoachResponse
from oya.prompts.validate import validate_call_text
from oya.settings import get_settings
from oya.store.table import Entity, get_latest, put_item, query_all, query_range

MODEL = "claude-opus-5"
MAX_RETRIES = 1  # one regeneration attempt before falling back to a template


def _format_recovery(snap: RecoverySnapshot) -> str:
    lines = []
    for metric in (
        snap.sleep,
        snap.resting_heart_rate,
        snap.hrv,
        snap.stress,
        snap.body_battery,
        snap.steps,
        snap.weight,
    ):
        if metric.building or metric.today is None:
            lines.append(f"{metric.label}: building baseline ({metric.days} of 30 nights)")
        else:
            sign = "+" if metric.delta >= 0 else ""
            unit = metric.unit or ""
            lines.append(
                f"{metric.label}: {metric.today:.0f}{unit} "
                f"({sign}{metric.delta:.0f} vs 30d avg {metric.average:.0f})"
            )
    if snap.blood_pressure:
        bp = snap.blood_pressure
        lines.append(f"Blood pressure: {bp.systolic}/{bp.diastolic}")
    return "\n".join(lines)


def _format_calendar(cal: CalendarSnapshot) -> str:
    lines = []
    if cal.remaining_today:
        lines.append("Tonight:")
        lines.extend(f"  {e.start.strftime('%H:%M')} {e.summary}" for e in cal.remaining_today)
    else:
        lines.append("Nothing left on the calendar today.")
    if cal.tomorrow_first:
        first = cal.tomorrow_first
        lines.append(f"Tomorrow's first event: {first.start.strftime('%H:%M')} {first.summary}")
    if cal.travelling:
        lines.append("Looks like travel is involved.")
    return "\n".join(lines)


def _format_weather(weather: WeatherWindow | None) -> str:
    if not weather:
        return "Weather unavailable."
    parts = [weather.short_forecast or "unknown conditions"]
    if weather.temperature_f is not None:
        parts.append(f"{weather.temperature_f:.0f}F")
    if weather.precipitation_chance is not None:
        parts.append(f"{weather.precipitation_chance}% chance of precipitation")
    return "17:00-20:00: " + ", ".join(parts)


def _format_week(days: int = 7) -> str:
    now = datetime.now(UTC)
    start = (now - timedelta(days=days)).date().isoformat()
    end = now.date().isoformat()
    activities = query_range(Entity.ACTIVITY, start, end)
    if not activities:
        return "No logged activity in the last 7 days."
    lines = [
        f"  {a.get('activity_type', 'activity')}: {a.get('duration_min', '?')} min"
        for a in activities
    ]
    return "This week:\n" + "\n".join(lines)


def _format_history(limit: int = 10) -> str:
    calls = get_latest(Entity.CALL, limit=limit)
    outcomes = get_latest(Entity.OUTCOME, limit=limit)
    if not calls and not outcomes:
        return "No prior calls yet."

    lines = ["Recent calls:"]
    lines.extend(f"  {c.get('sk')}: {c.get('headline', '')}" for c in calls)
    lines.append("Recent outcomes:")
    for o in outcomes:
        reason = f" ({o['skip_reason']})" if o.get("skip_reason") else ""
        lines.append(f"  {str(o.get('sk', ''))[:10]}: {o.get('result', '?')}{reason}")
    return "\n".join(lines)


def _format_notes() -> str:
    notes = query_all(Entity.NOTE)
    now = datetime.now(UTC).isoformat()
    active = [n for n in notes if not n.get("expires_at") or n["expires_at"] > now]
    if not active:
        return "No standing notes."
    return "Standing notes:\n" + "\n".join(f"  {n.get('text', '')}" for n in active)


def build_context(*, exclude_activity: str | None = None) -> str:
    recovery = get_recovery_snapshot()

    # Recovery comes from this app's own DynamoDB data, so a failure there
    # is a real bug worth crashing on. Calendar and weather are both
    # external and both optional in spirit -- not yet bootstrapped, or
    # having a bad day, shouldn't take the whole call down with them, the
    # same way a stale source never blocks anything else in this app.
    try:
        calendar_text = _format_calendar(get_calendar_snapshot())
    except Exception:
        calendar_text = "Calendar unavailable."

    try:
        weather_text = _format_weather(get_evening_window())
    except Exception:
        weather_text = "Weather unavailable."

    sections = [
        "Recovery:\n" + _format_recovery(recovery),
        calendar_text,
        weather_text,
        _format_week(),
        _format_history(),
        _format_notes(),
    ]
    if exclude_activity:
        sections.append(
            f"Do not prescribe {exclude_activity} -- already suggested and declined tonight."
        )
    return "\n\n".join(sections)


def _client() -> Anthropic:
    return Anthropic(api_key=get_settings().resolved_anthropic_api_key())


def _generate(client: Anthropic, context: str, *, retry_note: str | None = None) -> CoachResponse:
    user_content = context
    if retry_note:
        user_content += (
            f"\n\nYour previous attempt was rejected: {retry_note}. "
            "Try again, following the voice rules exactly."
        )

    response = client.messages.parse(
        model=MODEL,
        max_tokens=1024,
        system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_content}],
        output_format=CoachResponse,
    )
    return response.parsed_output


def _fallback_response(recovery: RecoverySnapshot) -> CoachResponse:
    """A bad model day must never become a bad push. Built directly from
    the numbers, no LLM involved."""
    rhr = recovery.resting_heart_rate
    if not rhr.building and rhr.delta is not None and rhr.delta > 5:
        headline = f"Resting heart rate is {rhr.delta:+.0f} vs your 30-day average."
        skip_ok = True
        activity, duration, intensity = "rest", 0, "easy"
    else:
        headline = "Numbers are unremarkable tonight."
        skip_ok = False
        activity, duration, intensity = "walk", 30, "easy"

    return CoachResponse(
        headline=headline,
        prescription={
            "activity": activity,
            "duration_min": duration,
            "intensity": intensity,
            "window": "17:30-19:00",
        },
        why="Built from recovery numbers directly after the coach's own output failed validation.",
        fallback="A short walk covers most of what tonight needs.",
        skip_ok=skip_ok,
    )


def generate_call(*, exclude_activity: str | None = None) -> CoachResponse:
    client = _client()
    context = build_context(exclude_activity=exclude_activity)

    result = _generate(client, context)
    violations = validate_call_text(result.headline, result.why, result.fallback)

    attempts = 0
    while violations and attempts < MAX_RETRIES:
        result = _generate(client, context, retry_note="; ".join(violations))
        violations = validate_call_text(result.headline, result.why, result.fallback)
        attempts += 1

    if violations:
        return _fallback_response(get_recovery_snapshot())
    return result


def store_call(result: CoachResponse, *, overridden: bool = False) -> None:
    today = datetime.now(UTC).date().isoformat()
    existing = get_latest(Entity.CALL, sk=today)
    override_count = int(existing[0].get("override_count", 0)) + 1 if overridden and existing else 0

    put_item(
        Entity.CALL,
        today,
        {
            "headline": result.headline,
            "prescription": result.prescription.model_dump(),
            "why": result.why,
            "fallback": result.fallback,
            "skip_ok": result.skip_ok,
            "overridden": overridden,
            "override_count": override_count,
        },
    )


def _notify_all_subscriptions(title: str, body: str) -> None:
    for sub in query_all(Entity.SUB):
        send_push(sub["subscription"], title, body, url="/call")


def handler(event: dict, context: object) -> dict:
    result = generate_call()
    store_call(result)
    _notify_all_subscriptions("Off yo ass", result.headline)
    return {"status": "ok", "headline": result.headline}
