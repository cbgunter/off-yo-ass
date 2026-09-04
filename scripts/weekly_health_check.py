#!/usr/bin/env python3
"""Weekly sync-health review. Reads the past week's SYNC_RUN records and
the current SOURCE_HEALTH state, asks Claude to flag anything worth a
human looking at, and files a GitHub issue if it finds something.

Deliberately outside the `oya` package: this only needs boto3 and the
Anthropic SDK, not the whole FastAPI/pydantic stack, so it runs via `uv
run --with anthropic,boto3` in CI rather than the project's own venv —
see .github/workflows/weekly-agent.yml.

Usage:
    OYA_TABLE_NAME=... GITHUB_REPOSITORY=owner/repo \\
      uv run --with anthropic,boto3 python scripts/weekly_health_check.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import boto3
from anthropic import Anthropic
from boto3.dynamodb.conditions import Key

USER_PK_PREFIX = "U#cbg#"

PROMPT = """You review the health of a personal fitness app's data syncs for the \
past week. You're given the week's sync run records and the current \
source-health state. Flag anything worth a human looking at: a source \
that went stale, a rising error rate, or a gap that would block a \
feature the app wants to build later. Stay quiet if nothing needs \
attention — most weeks should report nothing.

Respond with ONLY a JSON object, no markdown fences, no other text: \
{{"needs_attention": bool, "title": str, "body": str}}. title and body \
should follow this app's voice: matter-of-fact, no exclamation marks, no \
emoji, state the number and the fact, nothing else. title and body may \
be empty strings when needs_attention is false.

Sync runs (past 7 days):
{sync_runs}

Source health (current):
{source_health}
"""


def _decimal_default(value: object) -> float:
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError(f"not JSON serializable: {value!r}")


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]
    return text.strip()


def fetch_week(table, entity: str) -> list[dict]:
    now = datetime.now(UTC)
    start = (now - timedelta(days=7)).isoformat()
    end = now.isoformat()
    response = table.query(
        KeyConditionExpression=Key("pk").eq(f"{USER_PK_PREFIX}{entity}")
        & Key("sk").between(start, end)
    )
    return response.get("Items", [])


def fetch_source_health(table) -> list[dict]:
    response = table.query(KeyConditionExpression=Key("pk").eq(f"{USER_PK_PREFIX}SOURCE_HEALTH"))
    return response.get("Items", [])


def main() -> None:
    table_name = os.environ["OYA_TABLE_NAME"]
    repo = os.environ["GITHUB_REPOSITORY"]

    table = boto3.resource("dynamodb").Table(table_name)
    sync_runs = fetch_week(table, "SYNC_RUN")
    source_health = fetch_source_health(table)

    client = Anthropic()
    response = client.messages.create(
        model="claude-opus-5",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": PROMPT.format(
                    sync_runs=json.dumps(sync_runs, default=_decimal_default, indent=2),
                    source_health=json.dumps(source_health, default=_decimal_default, indent=2),
                ),
            }
        ],
    )

    text = "".join(block.text for block in response.content if block.type == "text")
    result = json.loads(_strip_code_fence(text))

    if not result.get("needs_attention"):
        print("No issues found this week.")
        return

    title, body = result["title"], result["body"]
    print(f"Filing issue: {title}")
    subprocess.run(
        ["gh", "issue", "create", "--repo", repo, "--title", title, "--body", body],
        check=True,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"weekly_health_check failed: {exc}", file=sys.stderr)
        raise
