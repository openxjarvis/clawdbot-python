"""Node resolution utilities for agent tools.

Ported from TypeScript:
- openclaw/src/agents/tools/nodes-utils.ts
- openclaw/src/shared/node-match.ts

Provides:
- list_nodes(): fetch node list via gateway RPC
- resolve_node_id(): find a node ID by name/ID query
- resolve_node_id_from_list(): match from an already-loaded list
"""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Node matching helpers (mirrors src/shared/node-match.ts)
# ---------------------------------------------------------------------------

def normalize_node_key(value: str) -> str:
    """Normalize a node name/ID for matching. Mirrors TS normalizeNodeKey()."""
    result = value.lower()
    result = re.sub(r"[^a-z0-9]+", "-", result)
    result = result.strip("-")
    return result


def resolve_node_matches(nodes: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    """Find all nodes matching query string. Mirrors TS resolveNodeMatches()."""
    q = query.strip()
    if not q:
        return []
    q_norm = normalize_node_key(q)
    matches = []
    for n in nodes:
        node_id = str(n.get("nodeId", ""))
        remote_ip = n.get("remoteIp") or ""
        display_name = n.get("displayName") or ""
        # Exact nodeId match
        if node_id == q:
            matches.append(n)
            continue
        # Exact remoteIp match
        if remote_ip and remote_ip == q:
            matches.append(n)
            continue
        # Normalized displayName match
        if display_name and normalize_node_key(display_name) == q_norm:
            matches.append(n)
            continue
        # Prefix match on nodeId (>= 6 chars)
        if len(q) >= 6 and node_id.startswith(q):
            matches.append(n)
            continue
    return matches


def resolve_node_id_from_candidates(nodes: list[dict[str, Any]], query: str) -> str:
    """Resolve a single node ID from candidates. Mirrors TS resolveNodeIdFromCandidates()."""
    q = query.strip()
    if not q:
        raise ValueError("node required")
    matches = resolve_node_matches(nodes, q)
    if len(matches) == 1:
        return matches[0].get("nodeId", "")
    if len(matches) == 0:
        known = ", ".join(
            n.get("displayName") or n.get("remoteIp") or n.get("nodeId", "")
            for n in nodes
            if n.get("displayName") or n.get("remoteIp") or n.get("nodeId")
        )
        raise ValueError(f"unknown node: {q}" + (f" (known: {known})" if known else ""))
    raise ValueError(
        f"ambiguous node: {q} (matches: "
        + ", ".join(
            n.get("displayName") or n.get("remoteIp") or n.get("nodeId", "")
            for n in matches
        )
        + ")"
    )


# ---------------------------------------------------------------------------
# Node list loading (mirrors nodes-utils.ts loadNodes / listNodes)
# ---------------------------------------------------------------------------

async def _call_gateway(method: str, params: dict[str, Any]) -> Any:
    """Call gateway RPC, returns raw result."""
    from openclaw.gateway.rpc_client import create_client
    client = await create_client()
    return await client.call(method, params)


def _parse_node_list(value: Any) -> list[dict[str, Any]]:
    """Parse node.list response. Mirrors TS parseNodeList()."""
    if isinstance(value, dict) and isinstance(value.get("nodes"), list):
        return value["nodes"]
    return []


def _parse_pairing_list_paired(value: Any) -> list[dict[str, Any]]:
    """Parse node.pair.list response, return paired nodes."""
    if isinstance(value, dict):
        paired = value.get("paired", [])
        if isinstance(paired, list):
            return [
                {
                    "nodeId": n.get("nodeId", ""),
                    "displayName": n.get("displayName"),
                    "platform": n.get("platform"),
                    "remoteIp": n.get("remoteIp"),
                }
                for n in paired
                if isinstance(n, dict)
            ]
    return []


async def list_nodes(gateway_opts: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """List all nodes via gateway RPC.

    Mirrors TypeScript listNodes() / loadNodes() from nodes-utils.ts.
    Tries node.list first; falls back to node.pair.list on failure.
    """
    try:
        res = await _call_gateway("node.list", {})
        return _parse_node_list(res)
    except Exception as exc:
        logger.debug("node.list failed (%s), trying node.pair.list", exc)
        try:
            res = await _call_gateway("node.pair.list", {})
            return _parse_pairing_list_paired(res)
        except Exception as exc2:
            logger.warning("node.pair.list also failed: %s", exc2)
            return []


def _pick_default_node(nodes: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Pick a default canvas-capable node. Mirrors TS pickDefaultNode()."""
    with_canvas = [
        n for n in nodes
        if not isinstance(n.get("caps"), list) or "canvas" in n.get("caps", [])
    ]
    if not with_canvas:
        return None
    connected = [n for n in with_canvas if n.get("connected")]
    candidates = connected if connected else with_canvas
    if len(candidates) == 1:
        return candidates[0]
    # Prefer local mac node
    local = [
        n for n in candidates
        if isinstance(n.get("platform"), str)
        and n["platform"].lower().startswith("mac")
        and isinstance(n.get("nodeId"), str)
        and n["nodeId"].startswith("mac-")
    ]
    if len(local) == 1:
        return local[0]
    return None


def resolve_node_id_from_list(
    nodes: list[dict[str, Any]],
    query: str | None = None,
    allow_default: bool = False,
) -> str:
    """Resolve a node ID from an already-loaded list.

    Mirrors TypeScript resolveNodeIdFromList() from nodes-utils.ts.
    """
    q = (query or "").strip()
    if not q:
        if allow_default:
            picked = _pick_default_node(nodes)
            if picked:
                return picked.get("nodeId", "")
        raise ValueError("node required")
    return resolve_node_id_from_candidates(nodes, q)


async def resolve_node_id(
    gateway_opts: dict[str, Any] | None,
    query: str | None = None,
    allow_default: bool = False,
) -> str:
    """Resolve a node ID by querying the gateway.

    Mirrors TypeScript resolveNodeId() from nodes-utils.ts.
    Fetches node list then calls resolve_node_id_from_list().
    """
    nodes = await list_nodes(gateway_opts)
    return resolve_node_id_from_list(nodes, query, allow_default)


__all__ = [
    "list_nodes",
    "resolve_node_id",
    "resolve_node_id_from_list",
    "resolve_node_id_from_candidates",
    "resolve_node_matches",
    "normalize_node_key",
]
