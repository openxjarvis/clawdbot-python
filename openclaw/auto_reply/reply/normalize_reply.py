"""Reply payload normalization utilities.

Mirrors TS normalizeReplyPayload from auto-reply/reply/normalize-reply.ts.
"""
from __future__ import annotations

from typing import Any


def normalize_reply_payload(
    payload: Any,
    response_prefix: str | None = None,
) -> dict[str, Any] | None:
    """Normalize a raw reply payload into a canonical dict.

    Accepts either a string (treated as ``text``), a dict, or ``None``.
    Returns ``None`` when there is nothing to send.
    """
    if payload is None:
        return None

    if isinstance(payload, str):
        text = payload
    elif isinstance(payload, dict):
        text = payload.get("text") or payload.get("content") or ""
    else:
        text = str(payload)

    if not text and not isinstance(payload, dict):
        return None

    if response_prefix and text:
        text = f"{response_prefix} {text}"

    result: dict[str, Any] = {"text": text}

    if isinstance(payload, dict):
        for key in ("images", "files", "voice", "reactions", "silent", "channel"):
            if key in payload:
                result[key] = payload[key]

    return result if (result.get("text") or result.get("images") or result.get("files")) else None
