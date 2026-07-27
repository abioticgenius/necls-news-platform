from __future__ import annotations

import time
from datetime import datetime

_cooldown_tracker: dict[str, float] = {}
COOLDOWN_SECONDS = 30 * 60  # 30 minutes


def slack_alert(message: str, cooldown_key: str, cooldown_seconds: int = COOLDOWN_SECONDS) -> None:
    """Send a Slack alert via webhook. Silent no-op if SLACK_ALERT_WEBHOOK is not set.

    Uses an in-memory cooldown per cooldown_key to avoid spamming during sustained outages.
    """
    import os
    webhook_url = os.getenv("SLACK_ALERT_WEBHOOK", "").strip()
    if not webhook_url:
        return

    now = time.monotonic()
    last_sent = _cooldown_tracker.get(cooldown_key, 0.0)
    if now - last_sent < cooldown_seconds:
        return

    _cooldown_tracker[cooldown_key] = now

    try:
        import requests
        payload = {"text": f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC]\n{message}"}
        requests.post(webhook_url, json=payload, timeout=5)
    except Exception:
        pass  # Never let alerting break the pipeline
