"""Fixed-copy check-in reminder at 20:30. No LLM involved -- the actual
check-in happens through POST /api/call/checkin when you tap it.
"""

from __future__ import annotations

from oya.integrations.webpush import send_push
from oya.store.table import Entity, query_all

TITLE = "Off yo ass"
BODY = "Check in on tonight."


def handler(event: dict, context: object) -> dict:
    sent = sum(
        1
        for sub in query_all(Entity.SUB)
        if send_push(sub["subscription"], TITLE, BODY, url="/call")
    )
    return {"status": "ok", "sent": sent}
