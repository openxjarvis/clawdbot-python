"""Session label parsing — matches openclaw/src/sessions/session-label.ts"""
from __future__ import annotations

from typing import Union

SESSION_LABEL_MAX_LENGTH = 64


def parse_session_label(raw: object) -> Union[dict, dict]:
    """
    Parse and validate a session label.

    Returns:
        {"ok": True, "label": str} on success
        {"ok": False, "error": str} on failure

    Matches TS parseSessionLabel().
    """
    if not isinstance(raw, str):
        return {"ok": False, "error": "invalid label: must be a string"}
    trimmed = raw.strip()
    if not trimmed:
        return {"ok": False, "error": "invalid label: empty"}
    if len(trimmed) > SESSION_LABEL_MAX_LENGTH:
        return {
            "ok": False,
            "error": f"invalid label: too long (max {SESSION_LABEL_MAX_LENGTH})",
        }
    return {"ok": True, "label": trimmed}


__all__ = [
    "SESSION_LABEL_MAX_LENGTH",
    "parse_session_label",
]
