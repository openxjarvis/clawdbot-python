"""Conversation label resolution — mirrors src/channels/conversation-label.ts"""
from __future__ import annotations

import re
from typing import Any

from .chat_type import normalize_chat_type


def _extract_conversation_id(from_: str | None) -> str | None:
    trimmed = (from_ or "").strip()
    if not trimmed:
        return None
    parts = [p for p in trimmed.split(":") if p]
    return parts[-1] if parts else trimmed


def _should_append_id(id_: str) -> bool:
    if re.match(r"^\d+$", id_):
        return True
    if "@g.us" in id_:
        return True
    return False


def resolve_conversation_label(ctx: Any) -> str | None:
    explicit = (getattr(ctx, "ConversationLabel", None) or "").strip()
    if explicit:
        return explicit

    thread_label = (getattr(ctx, "ThreadLabel", None) or "").strip()
    if thread_label:
        return thread_label

    chat_type = normalize_chat_type(getattr(ctx, "ChatType", None))
    if chat_type == "direct":
        return (getattr(ctx, "SenderName", None) or "").strip() or \
               (getattr(ctx, "From", None) or "").strip() or None

    base = (
        (getattr(ctx, "GroupChannel", None) or "").strip()
        or (getattr(ctx, "GroupSubject", None) or "").strip()
        or (getattr(ctx, "GroupSpace", None) or "").strip()
        or (getattr(ctx, "From", None) or "").strip()
    )
    if not base:
        return None

    id_ = _extract_conversation_id(getattr(ctx, "From", None))
    if not id_:
        return base
    if not _should_append_id(id_):
        return base
    if base == id_:
        return base
    if id_ in base:
        return base
    if " id:" in base.lower():
        return base
    if base.startswith("#") or base.startswith("@"):
        return base
    return f"{base} id:{id_}"
