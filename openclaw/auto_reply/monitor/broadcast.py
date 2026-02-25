"""Broadcast message handling for multi-agent dispatch.

Mirrors TypeScript openclaw/src/web/auto-reply/monitor/broadcast.ts.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from openclaw.auto_reply.group_history import GroupHistoryEntry, get_group_history, clear_group_history
from openclaw.routing.broadcast_groups import (
    resolve_broadcast_agents,
    dispatch_to_broadcast_group,
)

logger = logging.getLogger(__name__)


async def maybe_broadcast_message(
    cfg: dict[str, Any],
    msg: dict[str, Any],
    peer_id: str,
    route: dict[str, Any],
    group_history_key: str,
    process_message_fn: Callable,
    group_histories: dict[str, list[GroupHistoryEntry]] | None = None,
) -> bool:
    """Check if message should be broadcast and dispatch to multiple agents.
    
    Mirrors TS maybeBroadcastMessage().
    
    Args:
        cfg: OpenClaw configuration
        msg: Inbound message dict
        peer_id: Peer identifier (group JID, phone number, etc.)
        route: Resolved route from routing
        group_history_key: Key for group history storage
        process_message_fn: Function to process message for each agent
        group_histories: Optional group history map
        
    Returns:
        True if broadcast was handled, False if no broadcast configured
    """
    broadcast_agents = resolve_broadcast_agents(cfg, peer_id)

    # Broadcast only triggers when there are 2+ agents
    # (single-agent is the default route, not a broadcast)
    if len(broadcast_agents) < 2:
        return False

    logger.info("Broadcasting message to %d agents", len(broadcast_agents))

    chat_type = msg.get("chatType", msg.get("chat_type", "direct"))
    channel = route.get("channel", "whatsapp")
    peer_kind = "group" if chat_type == "group" else "direct"

    await dispatch_to_broadcast_group(
        cfg=cfg,
        msg=msg,
        peer_id=peer_id,
        base_route=route,
        channel=channel,
        peer_kind=peer_kind,
        process_message_fn=process_message_fn,
        group_history_key=group_history_key,
        group_histories=group_histories,
        broadcast_agents=broadcast_agents,
    )

    return True


__all__ = [
    "maybe_broadcast_message",
]
