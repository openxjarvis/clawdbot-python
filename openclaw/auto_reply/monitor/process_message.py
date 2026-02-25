"""Message processing pipeline.

Processes inbound messages and determines responses.
Fully aligned with TypeScript src/web/auto-reply/monitor/process-message.ts
and src/web/auto-reply/monitor/on-message.ts
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Awaitable

from openclaw.auto_reply.group_history import GroupHistoryEntry

logger = logging.getLogger(__name__)


async def process_message(
    cfg: dict[str, Any],
    msg: dict[str, Any],
    route: dict[str, Any],
    group_history_key: str,
    group_histories: dict[str, list[GroupHistoryEntry]] | None = None,
    process_message_fn: Callable[[dict[str, Any], dict[str, Any], str], Awaitable[bool]] | None = None,
) -> bool:
    """Process an inbound message with full broadcast and group support.
    
    Mirrors TS processMessage() from src/web/auto-reply/monitor/process-message.ts
    and the flow from src/web/auto-reply/monitor/on-message.ts.
    
    This is the main entry point that:
    1. Checks for broadcast groups and dispatches to multiple agents if configured
    2. Otherwise processes the message normally via the resolved route
    
    Args:
        cfg: OpenClaw configuration
        msg: Inbound message dict
        route: Resolved agent route
        group_history_key: Key for group history storage
        group_histories: Optional group history map
        process_message_fn: Function to process message for a specific route
        
    Returns:
        True if message was processed (broadcast or normal), False otherwise
    """
    from openclaw.auto_reply.monitor.broadcast import maybe_broadcast_message
    
    # Default process function if not provided
    if process_message_fn is None:
        process_message_fn = _default_process_for_route
    
    # Check if this should be broadcast to multiple agents
    peer_id = msg.get("from", msg.get("peer_id", ""))
    
    if await maybe_broadcast_message(
        cfg=cfg,
        msg=msg,
        peer_id=peer_id,
        route=route,
        group_history_key=group_history_key,
        process_message_fn=process_message_fn,
        group_histories=group_histories,
    ):
        return True
    
    # Normal single-agent processing
    return await process_message_fn(msg, route, group_history_key)


async def _default_process_for_route(
    msg: dict[str, Any],
    route: dict[str, Any],
    group_history_key: str,
) -> bool:
    """Default message processor for a specific route.
    
    This is a fallback implementation that calls get_reply_from_config.
    
    Args:
        msg: Inbound message dict
        route: Resolved agent route
        group_history_key: Group history key
        
    Returns:
        True if reply was sent
    """
    try:
        from openclaw.auto_reply.reply.get_reply import get_reply_from_config
        
        # Build context from message
        ctx = _build_context_from_message(msg, route)
        
        # Get reply
        reply = await get_reply_from_config(
            ctx=ctx,
            cfg=route.get("config"),
            runtime=route.get("runtime"),
        )
        
        return reply is not None
    
    except Exception as exc:
        logger.error(f"Failed to process message: {exc}")
        return False


def _build_context_from_message(msg: dict[str, Any], route: dict[str, Any]) -> dict[str, Any]:
    """Build context dict from message and route.
    
    Helper to convert message dict to context format expected by get_reply_from_config.
    
    Args:
        msg: Inbound message dict
        route: Resolved route dict
        
    Returns:
        Context dict
    """
    return {
        "Body": msg.get("body", msg.get("text", "")),
        "RawBody": msg.get("body", msg.get("text", "")),
        "SessionKey": route.get("sessionKey", ""),
        "From": msg.get("from", msg.get("sender_id", "")),
        "To": msg.get("to", ""),
        "ChatType": msg.get("chatType", msg.get("chat_type", "dm")),
        "SenderName": msg.get("senderName", msg.get("sender_name")),
        "MessageId": msg.get("id", msg.get("message_id")),
        "Channel": msg.get("channel", ""),
        "GroupId": msg.get("groupId", msg.get("group_id")),
        "GroupName": msg.get("groupSubject", msg.get("group_name")),
        "WasMentioned": msg.get("wasMentioned", False),
    }
