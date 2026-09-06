"""Single-table DynamoDB access. `pk = "U#cbg#<ENTITY>"`, `sk` is an ISO
date or timestamp string, so "this entity, this date range" — every read
pattern this app has — is a native query. Every other module reads and
writes through the functions here; nothing else touches boto3's DynamoDB
API directly.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

from oya.settings import get_settings

USER = "cbg"


def _to_dynamodb_value(value: Any) -> Any:
    """boto3's DynamoDB resource API rejects native Python `float`
    outright (`Decimal types instead`) — every other module in this app
    just writes ordinary floats, so the conversion happens once, here,
    rather than asking every caller to remember it. `str(value)` avoids
    the binary-float precision artifacts a direct `Decimal(value)` would
    bake in (e.g. `Decimal(0.1)` vs `Decimal("0.1")`)."""
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _to_dynamodb_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_dynamodb_value(v) for v in value]
    return value


class Entity:
    """String constants for the DynamoDB partition-key entities, so a typo
    is a NameError at import time instead of a silent empty query."""

    SLEEP = "SLEEP"
    HRV = "HRV"
    RHR = "RHR"
    STRESS = "STRESS"
    BODYBATT = "BODYBATT"
    STEPS = "STEPS"
    WEIGHT = "WEIGHT"
    ACTIVITY = "ACTIVITY"
    SOURCE_HEALTH = "SOURCE_HEALTH"
    SYNC_RUN = "SYNC_RUN"
    SUB = "SUB"
    CALL = "CALL"
    BEDTIME = "BEDTIME"
    OUTCOME = "OUTCOME"
    FEEL = "FEEL"
    NOTE = "NOTE"
    QUESTION = "QUESTION"
    ANSWER = "ANSWER"
    MEAL = "MEAL"


def _table():
    settings = get_settings()
    resource = boto3.resource("dynamodb")
    return resource.Table(settings.table_name)


def _pk(entity: str) -> str:
    return f"U#{USER}#{entity}"


def put_item(entity: str, sk: str, attrs: dict) -> None:
    item = {"pk": _pk(entity), "sk": sk, **_to_dynamodb_value(attrs)}
    _table().put_item(Item=item)


def query_range(entity: str, start: str, end: str) -> list[dict]:
    """Inclusive range query on `sk`, ascending order."""
    response = _table().query(
        KeyConditionExpression=Key("pk").eq(_pk(entity)) & Key("sk").between(start, end),
    )
    return response.get("Items", [])


def query_all(entity: str) -> list[dict]:
    """Every item for an entity, regardless of `sk` — for entities like
    SUB where there's no meaningful date range, just "all of them." Fine
    without pagination handling at this app's single-user scale."""
    response = _table().query(KeyConditionExpression=Key("pk").eq(_pk(entity)))
    return response.get("Items", [])


def get_latest(entity: str, *, sk: str | None = None, limit: int = 1) -> list[dict]:
    """Most recent items for an entity, descending by `sk`. Pass `sk` to
    fetch one specific item (e.g. a SOURCE_HEALTH row keyed by source
    name) — that returns at most one item regardless of `limit`."""
    if sk is not None:
        response = _table().get_item(Key={"pk": _pk(entity), "sk": sk})
        item = response.get("Item")
        return [item] if item else []

    response = _table().query(
        KeyConditionExpression=Key("pk").eq(_pk(entity)),
        ScanIndexForward=False,
        Limit=limit,
    )
    return response.get("Items", [])
