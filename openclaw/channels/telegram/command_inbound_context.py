"""Inbound context finalization for commands.

Simplified version aligned with TypeScript openclaw/src/auto-reply/reply/inbound-context.ts
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def finalize_inbound_context(ctx: dict[str, Any]) -> dict[str, Any]:
    """Finalize inbound context for command processing (mirrors TS finalizeInboundContext).
    
    Args:
        ctx: Inbound context dictionary
        
    Returns:
        Finalized context with normalized fields
    """
    # Normalize text fields
    body = ctx.get("Body", "")
    if not isinstance(body, str):
        body = ""
    
    # Normalize newlines
    body = body.replace("\r\n", "\n").replace("\r", "\n")
    ctx["Body"] = body
    
    # Set BodyForAgent (prefer CommandBody for commands)
    command_body = ctx.get("CommandBody", "")
    raw_body = ctx.get("RawBody", "")
    ctx["BodyForAgent"] = command_body or raw_body or body
    
    # Set BodyForCommands
    ctx["BodyForCommands"] = command_body or raw_body or body
    
    # Ensure CommandAuthorized is boolean (default False)
    ctx["CommandAuthorized"] = ctx.get("CommandAuthorized") is True
    
    # Set conversation label if missing
    if not ctx.get("ConversationLabel"):
        from_str = ctx.get("From", "")
        to_str = ctx.get("To", "")
        if from_str:
            ctx["ConversationLabel"] = from_str
        elif to_str:
            ctx["ConversationLabel"] = to_str
        else:
            ctx["ConversationLabel"] = "telegram"
    
    # Normalize ChatType
    chat_type = ctx.get("ChatType", "chat")
    if chat_type not in ("chat", "repl", "thread"):
        chat_type = "chat"
    ctx["ChatType"] = chat_type
    
    return ctx


__all__ = [
    "finalize_inbound_context",
]
