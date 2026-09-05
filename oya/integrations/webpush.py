"""Web Push sender. Wraps `pywebpush`; every worker that sends a push
calls this — the API Lambda never needs the VAPID private key, since
sending only ever happens from scheduled workers.
"""

from __future__ import annotations

import json

from pywebpush import WebPushException, webpush

from oya.settings import get_settings


def send_push(subscription_info: dict, title: str, body: str, url: str = "/") -> bool:
    """Sends one push notification. `url` is where web/src/sw.ts's
    notificationclick handler opens on tap -- each worker points it at
    whatever screen that push is actually about. Returns False (never
    raises) on a dead subscription -- an expired or unsubscribed endpoint
    is routine, not an error worth failing a sync run over."""
    settings = get_settings()
    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps({"title": title, "body": body, "url": url}),
            vapid_private_key=settings.resolved_vapid_private_key(),
            vapid_claims={"sub": settings.vapid_subject},
        )
        return True
    except WebPushException:
        return False
