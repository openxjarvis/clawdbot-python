"""Message handler factory for channel integrations.

Creates message handlers that integrate routing, group gating, and broadcast.
Mirrors TypeScript src/web/auto-reply/monitor/on-message.ts
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Awaitable

from openclaw.auto_reply.group_gating import apply_group_gating
from openclaw.auto_reply.group_history import GroupHistoryEntry
from openclaw.auto_reply.monitor.process_message import process_message
from openclaw.routing.resolve_route import resolve_agent_route

logger = logging.getLogger(__name__)


def create_message_handler(
    cfg: dict[str, Any],
    channel: str,
    account_id: str | None = None,
    group_histories: dict[str, list[GroupHistoryEntry]] | None = None,
    group_history_limit: int = 50,
    owner_list: list[str] | None = None,
    process_message_fn: Callable[[dict[str, Any], dict[str, Any], str], Awaitable[bool]] | None = None,
) -> Callable[[dict[str, Any]], Awaitable[None]]:
    """Create a message handler for a channel.
    
    Mirrors TS createWebOnMessageHandler() from src/web/auto-reply/monitor/on-message.ts.
    
    The returned handler:
    1. Resolves agent route
    2. Applies group gating (if group message)
    3. Checks for broadcast groups and dispatches if configured
    4. Otherwise processes message normally
    
    Args:
        cfg: OpenClaw configuration
        channel: Channel ID (e.g., "telegram", "whatsapp")
        account_id: Optional account ID
        group_histories: Optional group history map
        group_history_limit: Maximum history entries
        owner_list: List of owner identifiers
        process_message_fn: Optional custom message processor
        
    Returns:
        Async message handler function
    """
    if group_histories is None:
        group_histories = {}
    
    async def handle_message(msg: dict[str, Any]) -> None:
        """Handle inbound message.
        
        Args:
            msg: Inbound message dict with fields:
                - body/text: Message text
                - from/sender_id: Sender identifier
                - to: Recipient identifier
                - chatType/chat_type: "dm" or "group"
                - groupId/group_id: Group identifier (for groups)
                - etc.
        """
        # Resolve agent route
        peer_id = msg.get("from", msg.get("sender_id", ""))
        
        try:
            route = resolve_agent_route(
                cfg=cfg,
                channel=channel,
                peer_id=peer_id,
                account_id=account_id,
            )
        except Exception as exc:
            logger.error(f"Failed to resolve route: {exc}")
            return
        
        # Build group history key
        chat_type = msg.get("chatType", msg.get("chat_type", "dm"))
        group_history_key = ""
        
        if chat_type == "group":
            group_id = msg.get("groupId", msg.get("group_id", ""))
            thread_id = msg.get("threadId", msg.get("thread_id"))
            
            if thread_id:
                group_history_key = f"{channel}:{group_id}:{thread_id}"
            else:
                group_history_key = f"{channel}:{group_id}"
        
        # Apply group gating if group message
        if chat_type == "group":
            conversation_id = msg.get("groupId", msg.get("group_id", peer_id))
            
            gating_result = apply_group_gating(
                cfg=cfg,
                msg=msg,
                conversation_id=conversation_id,
                group_history_key=group_history_key,
                agent_id=route.get("agentId", ""),
                session_key=route.get("sessionKey", ""),
                channel=channel,
                account_id=account_id,
                group_histories=group_histories,
                group_history_limit=group_history_limit,
                owner_list=owner_list,
                session_state=None,
            )
            
            if not gating_result["shouldProcess"]:
                logger.debug(f"Message gated out for group {conversation_id}")
                return
            
            # Update message with effective mention status
            if gating_result["wasMentioned"] is not None:
                msg["wasMentioned"] = gating_result["wasMentioned"]
        
        # Process message (with broadcast check)
        await process_message(
            cfg=cfg,
            msg=msg,
            route=route,
            group_history_key=group_history_key,
            group_histories=group_histories,
            process_message_fn=process_message_fn,
        )
    
    return handle_message


__all__ = [
    "create_message_handler",
    "process_message",
]
