"""Weekly question, Sunday evening: one Claude call that looks at the
week's outcomes and picks the single most informative gap to ask about.
The answer becomes a standing NOTE. This is the "ask one real question"
half of the master plan's Sunday slot -- the receipts (the trend analysis
around it) are phase 4.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from anthropic import Anthropic
from pydantic import BaseModel, Field

from oya.integrations.webpush import send_push
from oya.settings import get_settings
from oya.store.table import Entity, get_latest, put_item, query_all, query_range

MODEL = "claude-opus-5"
TITLE = "Off yo ass"

SYSTEM_PROMPT = """You pick one question to ask about a week of exercise data, chosen to fill \
the single biggest gap in what's known about what actually gets this person moving. Not a \
survey question -- something specific to the patterns in the data you're given. Same voice as \
everywhere in this app: matter-of-fact, no exclamation marks, no cheerleading, cite a real \
number from the data when you can.

Example: "You've done four of five rowing prescriptions and one of four Peloton. Is that the \
machine or the time of day?" """


class WeeklyQuestion(BaseModel):
    question: str = Field(description="One question, citing a real number from the week's data.")


def _week_summary() -> str:
    now = datetime.now(UTC)
    start = (now - timedelta(days=7)).date().isoformat()
    end = now.date().isoformat()

    calls = query_range(Entity.CALL, start, end)
    outcomes = get_latest(Entity.OUTCOME, limit=20)
    activities = query_range(Entity.ACTIVITY, start, end)

    lines = ["Calls this week:"]
    lines.extend(f"  {c.get('sk')}: {c.get('headline', '')}" for c in calls)

    lines.append("Outcomes:")
    for o in outcomes:
        reason = f" ({o['skip_reason']})" if o.get("skip_reason") else ""
        lines.append(f"  {str(o.get('sk', ''))[:10]}: {o.get('result', '?')}{reason}")

    lines.append("Logged activity:")
    lines.extend(
        f"  {a.get('activity_type', 'activity')}: {a.get('duration_min', '?')} min"
        for a in activities
    )
    return "\n".join(lines)


def _notify_all_subscriptions(title: str, body: str) -> None:
    for sub in query_all(Entity.SUB):
        send_push(sub["subscription"], title, body, url="/question")


def handler(event: dict, context: object) -> dict:
    client = Anthropic(api_key=get_settings().resolved_anthropic_api_key())
    summary = _week_summary()

    response = client.messages.parse(
        model=MODEL,
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": summary}],
        output_format=WeeklyQuestion,
    )
    question = response.parsed_output.question

    week_ending = datetime.now(UTC).date().isoformat()
    put_item(Entity.QUESTION, week_ending, {"question": question})
    _notify_all_subscriptions(TITLE, question)

    return {"status": "ok", "question": question}
