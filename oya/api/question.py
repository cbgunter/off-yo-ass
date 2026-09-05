"""The weekly question: fetch the current one, submit an answer. The
answer becomes a standing NOTE too (via oya/api/notes.py's
parse_and_store_note), the same way any other note enters the coach's
context -- per the master plan, "the answer becomes a standing context."
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from oya.api.auth import User, get_current_user
from oya.api.notes import parse_and_store_note
from oya.store.table import Entity, get_latest, put_item

router = APIRouter(prefix="/api/question", tags=["question"])


class QuestionOut(BaseModel):
    question: str
    week_ending: str
    answered: bool


class AnswerIn(BaseModel):
    text: str


@router.get("/latest", response_model=None)
def get_latest_question(user: User = Depends(get_current_user)) -> QuestionOut | None:
    items = get_latest(Entity.QUESTION, limit=1)
    if not items:
        return None

    week_ending = items[0]["sk"]
    answered = bool(get_latest(Entity.ANSWER, sk=week_ending))
    return QuestionOut(question=items[0]["question"], week_ending=week_ending, answered=answered)


@router.post("/answer", status_code=204, response_model=None)
def answer_question(body: AnswerIn, user: User = Depends(get_current_user)) -> None:
    items = get_latest(Entity.QUESTION, limit=1)
    week_ending = items[0]["sk"] if items else datetime.now(UTC).date().isoformat()

    put_item(Entity.ANSWER, week_ending, {"text": body.text})
    parse_and_store_note(body.text)
