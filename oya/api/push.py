"""Web Push subscription storage. Sending happens from the sync worker
(oya/integrations/webpush.py) on a staleness breach — this router only
records what to send to."""

from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from oya.api.auth import User, get_current_user
from oya.store.table import Entity, put_item

router = APIRouter(prefix="/api/push", tags=["push"])


class SubscribeIn(BaseModel):
    subscription: dict


@router.post("/subscribe", status_code=204, response_model=None)
# response_model=None is required, not decorative: `from __future__ import
# annotations` turns `-> None` into the string "None", which defeats
# FastAPI's usual fast path for inferring "no response body" from the
# return annotation and asserts instead ("status code 204 must not have a
# response body"). Every 204 route in a module with deferred annotations
# needs this explicitly.
def subscribe(body: SubscribeIn, user: User = Depends(get_current_user)) -> None:
    endpoint = body.subscription.get("endpoint", "")
    sk = hashlib.sha256(endpoint.encode()).hexdigest()
    put_item(Entity.SUB, sk, {"subscription": body.subscription})
