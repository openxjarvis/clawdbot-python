"""Broadcast groups for routing messages to multiple agents.

Mirrors TypeScript openclaw/src/web/auto-reply/monitor/broadcast.ts.
The config structure uses `broadcastGroups` key for clarity:
  broadcastGroups:
    <group_id>:
      agents: [...]
      strategy: parallel | sequential
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Literal

from openclaw.routing.session_key import (
    DEFAULT_MAIN_KEY,
    build_agent_main_session_key,
    normalize_agent_id,
)

logger = logging.getLogger(__name__)

BroadcastStrategy = Literal["parallel", "sequential"]


def _get_broadcast_group_config(cfg: dict[str, Any], group_id: str) -> dict[str, Any] | None:
    """Return the broadcast group config for *group_id*, or None."""
    # Support both 'broadcastGroups' (Python/test style) and 'broadcast' (TS style)
    broadcast = cfg.get("broadcastGroups") or {}
    if group_id in broadcast:
        return broadcast[group_id]
    # Also try legacy 'broadcast' key (TS format: broadcast[peer_id] = [...agents])
    legacy = cfg.get("broadcast") or {}
    if group_id in legacy:
        agents = legacy[group_id]
        if isinstance(agents, list):
            return {"agents": agents}
    return None


def resolve_broadcast_agents(cfg: dict[str, Any], group_id: str) -> list[str]:
    """Resolve broadcast agent list for a group ID.

    Mirrors TS maybeBroadcastMessage() agent resolution.

    Args:
        cfg: OpenClaw config
        group_id: Broadcast group identifier

    Returns:
        List of agent IDs to broadcast to (empty list if not configured)
    """
    group_cfg = _get_broadcast_group_config(cfg, group_id)
    if not group_cfg:
        return []

    agents = group_cfg.get("agents")
    if not agents or not isinstance(agents, list):
        return []

    return [str(a) for a in agents if a and str(a).strip()]


def get_broadcast_strategy(cfg: dict[str, Any], group_id: str | None = None) -> BroadcastStrategy:
    """Get broadcast strategy for a group.

    Args:
        cfg: OpenClaw config
        group_id: Optional broadcast group identifier

    Returns:
        "parallel" or "sequential" (default: "parallel")
    """
    if group_id:
        group_cfg = _get_broadcast_group_config(cfg, group_id)
        if group_cfg:
            strategy = group_cfg.get("strategy", "parallel")
            if strategy in ("parallel", "sequential"):
                return strategy
            return "parallel"

    # Fallback: top-level broadcast strategy
    broadcast_cfg = cfg.get("broadcastGroups") or cfg.get("broadcast") or {}
    strategy = broadcast_cfg.get("strategy", "parallel") if isinstance(broadcast_cfg, dict) else "parallel"
    if strategy not in ("parallel", "sequential"):
        return "parallel"
    return strategy


def create_broadcast_route(
    base_route: dict[str, Any],
    agent_id: str,
    peer_id: str,
    channel: str,
    account_id: str | None = None,
    peer_kind: str = "group",
    cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create agent-specific route for broadcast.

    Mirrors TS broadcast route creation in maybeBroadcastMessage().

    Args:
        base_route: Base route from routing resolution
        agent_id: Target agent ID
        peer_id: Peer ID
        channel: Channel name
        account_id: Account ID (defaults to base_route's accountId)
        peer_kind: Peer kind ("group", "direct", etc.)
        cfg: OpenClaw config

    Returns:
        Agent-specific route dict
    """
    cfg = cfg or {}
    effective_account_id = (
        account_id
        or base_route.get("accountId")
        or base_route.get("account_id")
        or "default"
    )

    normalized_agent_id = normalize_agent_id(agent_id)

    try:
        from openclaw.routing.session_key import build_agent_peer_session_key
        session_key = build_agent_peer_session_key(
            agent_id=normalized_agent_id,
            channel=channel,
            peer_kind=peer_kind,
            peer_id=peer_id,
            account_id=effective_account_id,
            dm_scope=cfg.get("session", {}).get("dmScope"),
            identity_links=cfg.get("session", {}).get("identityLinks"),
        )
    except Exception:
        session_key = f"{channel}:{peer_id}:{normalized_agent_id}"

    main_session_key = build_agent_main_session_key(
        agent_id=normalized_agent_id,
        main_key=DEFAULT_MAIN_KEY,
    )

    return {
        **base_route,
        "agentId": normalized_agent_id,
        "agent_id": normalized_agent_id,
        "sessionKey": session_key,
        "session_key": session_key,
        "mainSessionKey": main_session_key,
        "accountId": effective_account_id,
        "account_id": effective_account_id,
    }


async def dispatch_to_broadcast_group(
    cfg: dict[str, Any],
    peer_id: str,
    base_route: dict[str, Any],
    channel: str,
    process_message_fn: Callable,
    msg: dict[str, Any] | None = None,
    group_history_key: str | None = None,
    group_histories: dict[str, list[Any]] | None = None,
    peer_kind: str = "group",
    broadcast_agents: list[str] | None = None,
    group_history_snapshot: list[Any] | None = None,
) -> bool:
    """Dispatch message to broadcast group.

    Mirrors TS maybeBroadcastMessage() dispatch logic.

    Args:
        cfg: OpenClaw config
        peer_id: Peer/group ID
        base_route: Base route from routing
        channel: Channel name
        process_message_fn: async (msg, route, key) -> Any
        msg: Message dict
        group_history_key: Group history key for shared context
        group_histories: Shared group history store
        peer_kind: Peer kind
        broadcast_agents: Explicit agent list (resolved from cfg if not provided)
        group_history_snapshot: Snapshot of group history

    Returns:
        True (broadcast handled)
    """
    if broadcast_agents is None:
        broadcast_agents = resolve_broadcast_agents(cfg, peer_id)

    strategy = get_broadcast_strategy(cfg, peer_id)
    logger.info("Broadcasting message to %d agents (%s)", len(broadcast_agents), strategy)

    account_id = (
        base_route.get("accountId")
        or base_route.get("account_id")
        or "default"
    )

    agents_list = cfg.get("agents", {}).get("list", [])
    agent_ids = {normalize_agent_id(a.get("id")) for a in agents_list if a.get("id")}
    has_known_agents = bool(agent_ids)

    async def process_for_agent(agent_id: str) -> bool:
        normalized = normalize_agent_id(agent_id)

        if has_known_agents and normalized not in agent_ids:
            logger.warning("Broadcast agent %s not in agents.list; skipping", agent_id)
            return False

        agent_route = create_broadcast_route(
            base_route=base_route,
            agent_id=normalized,
            peer_id=peer_id,
            channel=channel,
            account_id=account_id,
            peer_kind=peer_kind,
            cfg=cfg,
        )

        try:
            return await process_message_fn(msg, agent_route, group_history_key)
        except Exception as err:
            logger.error("Broadcast agent %s failed: %s", agent_id, err)
            return False

    if strategy == "sequential":
        for agent_id in broadcast_agents:
            await process_for_agent(agent_id)
    else:
        await asyncio.gather(
            *[process_for_agent(a) for a in broadcast_agents],
            return_exceptions=True,
        )

    # Clear group history after broadcast if tracking
    if group_histories is not None and group_history_key is not None:
        group_histories[group_history_key] = []

    return True


__all__ = [
    "BroadcastStrategy",
    "resolve_broadcast_agents",
    "get_broadcast_strategy",
    "create_broadcast_route",
    "dispatch_to_broadcast_group",
]
