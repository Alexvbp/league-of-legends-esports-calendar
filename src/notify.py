"""Pushover notification support for error alerting."""

from __future__ import annotations

import os

import requests


def send_error_notification(message: str, title: str = "Calendar Generator Error") -> bool:
    """Send an error notification via Pushover.

    Reads PUSHOVER_USER_KEY and PUSHOVER_API_TOKEN from environment.
    Returns True if sent, False if credentials missing or send failed.
    """
    user_key = os.environ.get("PUSHOVER_USER_KEY", "")
    api_token = os.environ.get("PUSHOVER_API_TOKEN", "")

    if not user_key or not api_token:
        print("  Pushover not configured (set PUSHOVER_USER_KEY and PUSHOVER_API_TOKEN)")
        return False

    try:
        resp = requests.post(
            "https://api.pushover.net/1/messages.json",
            data={
                "token": api_token,
                "user": user_key,
                "title": title,
                "message": message,
                "priority": 0,
            },
            timeout=10,
        )
        resp.raise_for_status()
        print(f"  Pushover notification sent: {title}")
        return True
    except Exception as e:
        print(f"  Failed to send Pushover notification: {e}")
        return False
