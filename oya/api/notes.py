"""Free-text notes, always available. Parsed by a small Claude call into
{type, expires_at, pinned} rather than stored as raw text, so a sore back
naturally stops mattering after its window instead of forever.

parse_and_store_note is exported for oya/api/question.py to reuse: an
answer to the weekly question becomes a standing note the same way any
other note does, per the master plan.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from anthropic import Anthropic
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from oya.api.auth import User, get_current_user
from oya.settings import get_settings
from oya.store.table import Entity, put_item, query_all

router = APIRouter(prefix="/api/notes", tags=["notes"])

MODEL = "claude-haiku-4-5"

SYSTEM_PROMPT = """You turn a short free-text note into structured standing context for a \
fitness coach. Classify its type and, unless it should be pinned indefinitely, estimate how \
many days it should remain relevant -- a sore back might matter for two weeks, a work deadline \
until its date, a one-off comment maybe not at all (in which case pin=false and \
expires_in_days=0)."""


class NoteIn(BaseModel):
    text: str


class NoteParse(BaseModel):
    type: str = Field(description='A short category, e.g. "injury", "schedule", "preference".')
    expires_in_days: int = Field(
        description="0 if this shouldn't become standing context at all."
    )
    pinned: bool = Field(description="True if this should never expire on its own.")


class NoteOut(BaseModel):
    text: str
    type: str
    expires_at: str | None
    pinned: bool
    when: str


def parse_and_store_note(text: str) -> NoteOut:
    client = Anthropic(api_key=get_settings().resolved_anthropic_api_key())
    response = client.messages.parse(
        model=MODEL,
        max_tokens=256,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": text}],
        output_format=NoteParse,
    )
    parsed = response.parsed_output

    when = datetime.now(UTC)
    expires_at = (
        None
        if parsed.pinned or parsed.expires_in_days <= 0
        else (when + timedelta(days=parsed.expires_in_days)).isoformat()
    )

    put_item(
        Entity.NOTE,
        when.isoformat(),
        {"text": text, "type": parsed.type, "expires_at": expires_at, "pinned": parsed.pinned},
    )
    return NoteOut(
        text=text, type=parsed.type, expires_at=expires_at, pinned=parsed.pinned,
        when=when.isoformat(),
    )


@router.get("")
def list_notes(user: User = Depends(get_current_user)) -> list[NoteOut]:
    notes = query_all(Entity.NOTE)
    now = datetime.now(UTC).isoformat()
    active = [
        n for n in notes if n.get("pinned") or not n.get("expires_at") or n["expires_at"] > now
    ]
    return [
        NoteOut(
            text=n["text"],
            type=n.get("type", ""),
            expires_at=n.get("expires_at"),
            pinned=bool(n.get("pinned", False)),
            when=n["sk"],
        )
        for n in active
    ]


@router.post("", status_code=201)
def add_note(body: NoteIn, user: User = Depends(get_current_user)) -> NoteOut:
    return parse_and_store_note(body.text)
