"""Web Push sender. Wraps `pywebpush`; only `oya/workers/sync_garmin.py`
calls this in phase 1 (on a staleness breach) — the API Lambda never
needs the VAPID private key.
"""

from __future__ import annotations

import json

from pywebpush import WebPushException, webpush

from oya.settings import get_settings


def send_push(subscription_info: dict, title: str, body: str) -> bool:
    """Sends one push notification. Returns False (never raises) on a
    dead subscription — an expired or unsubscribed endpoint is routine,
    not an error worth failing a sync run over."""
    settings = get_settings()
    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps({"title": title, "body": body}),
            vapid_private_key=settings.resolved_vapid_private_key(),
            vapid_claims={"sub": settings.vapid_subject},
        )
        return True
    except WebPushException:
        return False
