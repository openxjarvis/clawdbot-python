"""Sender identity validation — mirrors src/channels/sender-identity.ts"""
from __future__ import annotations

import re
from typing import Any

from .chat_type import normalize_chat_type


def validate_sender_identity(ctx: Any) -> list[str]:
    issues: list[str] = []

    chat_type = normalize_chat_type(getattr(ctx, "ChatType", None))
    is_direct = chat_type == "direct"

    sender_id = (getattr(ctx, "SenderId", None) or "").strip()
    sender_name = (getattr(ctx, "SenderName", None) or "").strip()
    sender_username = (getattr(ctx, "SenderUsername", None) or "").strip()
    sender_e164 = (getattr(ctx, "SenderE164", None) or "").strip()

    if not is_direct:
        if not sender_id and not sender_name and not sender_username and not sender_e164:
            issues.append(
                "missing sender identity (SenderId/SenderName/SenderUsername/SenderE164)"
            )

    if sender_e164:
        if not re.match(r"^\+\d{3,}$", sender_e164):
            issues.append(f"invalid SenderE164: {sender_e164}")

    if sender_username:
        if "@" in sender_username:
            issues.append(f'SenderUsername should not include "@": {sender_username}')
        if re.search(r"\s", sender_username):
            issues.append(f"SenderUsername should not include whitespace: {sender_username}")

    raw_sender_id = getattr(ctx, "SenderId", None)
    if raw_sender_id is not None and not sender_id:
        issues.append("SenderId is set but empty")

    return issues
