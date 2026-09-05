"""Mechanical enforcement of BRANDING.md's copy rules -- the checks that
can actually be verified by code (exclamation marks, emoji, em/en-dashes,
a denylist of cheerleading phrases), not the ones that need editorial
judgment (a metaphor about a journey, whether a question reads as
rhetorical) -- those stay system-prompt instructions, the same as they
would for a human editor. This is deliberately the most heavily tested
module the coach touches, the same way phase 1 over-tested baselines.
"""

from __future__ import annotations

import re

EMOJI_PATTERN = re.compile(
    "["
    "\U0001f300-\U0001faff"
    "\U00002600-\U000027bf"
    "\U0001f1e6-\U0001f1ff"
    "]"
)

CHEERLEADING_PHRASES = (
    "you've got this",
    "you got this",
    "way to go",
    "great job",
    "keep it up",
    "you can do it",
    "let's go",
    "proud of you",
    "amazing job",
    "crushing it",
    "you're crushing",
    "keep pushing",
    "believe in yourself",
)


def find_violations(text: str) -> list[str]:
    violations = []

    if "!" in text:
        violations.append("contains an exclamation mark")
    if EMOJI_PATTERN.search(text):
        violations.append("contains an emoji")
    if "—" in text or "–" in text:
        violations.append("contains an em-dash or en-dash")

    lowered = text.lower()
    for phrase in CHEERLEADING_PHRASES:
        if phrase in lowered:
            violations.append(f'contains the cheerleading phrase "{phrase}"')

    return violations


def validate_call_text(headline: str, why: str, fallback: str) -> list[str]:
    violations = []
    for field_name, text in (("headline", headline), ("why", why), ("fallback", fallback)):
        violations.extend(f"{field_name} {v}" for v in find_violations(text))
    return violations


def is_clean(text: str) -> bool:
    return not find_violations(text)
