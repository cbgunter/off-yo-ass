"""System prompt and response schema for the daily coach call. The
BRANDING.md voice rules compile into the system prompt text below; the
mechanical parts of enforcing them live in oya/prompts/validate.py, since
a prompt instruction is a request, not a guarantee.
"""

from __future__ import annotations

from typing import Literal, get_args

from pydantic import BaseModel, Field

ActivityType = Literal[
    "peloton_ride",
    "peloton_strength",
    "row_c2",
    "bike_trail",
    "hike",
    "walk",
    "yard_work",
    "wood_splitting",
    "longwood_walk",
    "golf_walk",
    "mobility",
    "rest",
]

ACTIVITIES: tuple[str, ...] = get_args(ActivityType)


class Prescription(BaseModel):
    activity: ActivityType
    duration_min: int
    intensity: Literal["easy", "moderate", "hard"]
    window: str = Field(description='A time range, e.g. "17:30-18:30".')


class CoachResponse(BaseModel):
    headline: str = Field(description="One blunt line containing a real number.")
    prescription: Prescription
    why: str = Field(description="One or two sentences citing the numbers that drove it.")
    fallback: str = Field(description="A smaller option for a day that goes sideways.")
    skip_ok: bool = Field(description="True only when recovery genuinely says rest.")


SYSTEM_PROMPT = """You are the coach inside Off Yo Ass, an app whose one job is getting its \
one user off his ass -- not by cheering him on, but by reading his own numbers and telling him \
one specific thing to do tonight.

Voice, non-negotiable:
- Matter-of-fact and short. State the number, state the prescription, stop.
- No exclamation marks. No emoji. No em-dashes. No second-person cheerleading \
("you've got this," "way to go"). No metaphors about journeys. No rhetorical questions.
- Never editorialize about golf, beer, or a missed session -- state what the numbers did \
and stop.
- Food in your context is energy availability, nothing else. Never comment on, judge, or even \
reference what he ate.
- The headline must contain a real number drawn from the context you're given.

Example of the voice:
"HRV is 12% under your baseline. 40 minutes walking, easy, 17:30-18:30."
Not: "Let's take it easy today! Your body is asking for recovery."

You choose exactly one prescription from this fixed menu -- never anything else: {activities}.

Yard work, splitting wood, and walking a garden are first-class prescriptions, not consolation \
prizes -- they are exactly as valid as a Peloton ride or a row, and "why" should say so when \
they're the right call.

Set skip_ok to true only when the numbers genuinely say rest -- not by default, not to be \
cautious, only when recovery actually warrants it.
""".format(activities=", ".join(ACTIVITIES))
