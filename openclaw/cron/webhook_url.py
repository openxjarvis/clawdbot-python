"""Webhook URL validation and normalization for cron job delivery.

Mirrors TypeScript: openclaw/src/cron/webhook-url.ts
"""
from __future__ import annotations

from urllib.parse import urlparse


def _is_allowed_webhook_protocol(protocol: str) -> bool:
    return protocol in ("http", "https")


def normalize_http_webhook_url(value: object) -> str | None:
    """Validate and normalize an HTTP/HTTPS webhook URL.

    Returns the trimmed URL string if valid, or None if invalid.

    Mirrors TS normalizeHttpWebhookUrl.
    """
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    try:
        parsed = urlparse(trimmed)
        if not _is_allowed_webhook_protocol(parsed.scheme):
            return None
        if not parsed.netloc:
            return None
        return trimmed
    except Exception:
        return None
