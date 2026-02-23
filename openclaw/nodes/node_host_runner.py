"""Node host runner — mirrors src/node-host/runner.ts"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Any

from .node_host_config import (
    NodeHostGatewayConfig,
    ensure_node_host_config,
    save_node_host_config,
)
from .node_invoke import NodeInvokeRequestPayload, SkillBinsProvider, coerce_node_invoke_payload, handle_invoke

logger = logging.getLogger(__name__)

DEFAULT_NODE_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

SKILL_BINS_CACHE_TTL_MS = 90_000  # 90 seconds


@dataclass
class NodeHostRunOptions:
    gateway_host: str
    gateway_port: int
    gateway_tls: bool = False
    gateway_tls_fingerprint: str | None = None
    node_id: str | None = None
    display_name: str | None = None


class SkillBinsCache:
    """TTL-based cache for available skill bins.

    Mirrors SkillBinsCache from runner.ts.
    """

    def __init__(self, fetch: Any):
        self._bins: set[str] = set()
        self._last_refresh: float = 0.0
        self._ttl_ms = SKILL_BINS_CACHE_TTL_MS
        self._fetch = fetch

    async def current(self, force: bool = False) -> set[str]:
        import time
        now_ms = time.time() * 1000
        if force or (now_ms - self._last_refresh) > self._ttl_ms:
            await self._refresh()
        return self._bins

    async def _refresh(self) -> None:
        import time
        try:
            bins = await self._fetch()
            self._bins = set(bins) if isinstance(bins, list) else set()
            self._last_refresh = time.time() * 1000
        except Exception as e:
            logger.warning(f"[node_host] skill bins refresh failed: {e}")
            if not self._last_refresh:
                self._bins = set()


def _ensure_node_path_env() -> str:
    current = os.environ.get("PATH", "")
    if current.strip():
        return current
    os.environ["PATH"] = DEFAULT_NODE_PATH
    return DEFAULT_NODE_PATH


async def _get_machine_display_name() -> str:
    """Get a human-readable machine name."""
    try:
        import socket
        return socket.gethostname()
    except Exception:
        return "python-node"


async def run_node_host(opts: NodeHostRunOptions) -> None:
    """Connect to the gateway as a NODE role client and handle node.invoke.request events.

    Mirrors runNodeHost() from runner.ts.
    """
    config = await ensure_node_host_config()

    node_id = (opts.node_id or "").strip() or config.node_id
    if node_id != config.node_id:
        config.node_id = node_id

    display_name = (opts.display_name or "").strip() or config.display_name or await _get_machine_display_name()
    config.display_name = display_name

    gateway_cfg = NodeHostGatewayConfig(
        host=opts.gateway_host,
        port=opts.gateway_port,
        tls=opts.gateway_tls,
        tls_fingerprint=opts.gateway_tls_fingerprint,
    )
    config.gateway = gateway_cfg
    await save_node_host_config(config)

    host = gateway_cfg.host or "127.0.0.1"
    port = gateway_cfg.port or 18789
    scheme = "wss" if gateway_cfg.tls else "ws"
    url = f"{scheme}://{host}:{port}"

    path_env = _ensure_node_path_env()
    logger.info(f"[node_host] PATH: {path_env}")

    try:
        from openclaw.gateway.client import GatewayClient
    except ImportError:
        logger.error("[node_host] GatewayClient not available — cannot start node host")
        return

    token: str | None = (
        os.environ.get("OPENCLAW_GATEWAY_TOKEN", "").strip() or config.token or None
    )
    password: str | None = os.environ.get("OPENCLAW_GATEWAY_PASSWORD", "").strip() or None

    client_kwargs: dict = {
        "url": url,
        "instance_id": node_id,
        "client_name": "node-host",
        "client_display_name": display_name,
        "mode": "node",
        "role": "node",
        "caps": ["system"],
        "path_env": path_env,
    }
    if token:
        client_kwargs["token"] = token
    if password:
        client_kwargs["password"] = password
    if gateway_cfg.tls_fingerprint:
        client_kwargs["tls_fingerprint"] = gateway_cfg.tls_fingerprint

    client = GatewayClient(**client_kwargs)

    async def _fetch_skill_bins() -> list[str]:
        try:
            res = await client.request("skills.bins", {})
            bins = res.get("bins", []) if isinstance(res, dict) else []
            return [str(b) for b in bins if b]
        except Exception:
            return []

    skill_bins = SkillBinsCache(_fetch_skill_bins)

    def _on_event(evt: Any) -> None:
        if not isinstance(evt, dict) or evt.get("event") != "node.invoke.request":
            return
        payload = coerce_node_invoke_payload(evt.get("payload"))
        if not payload:
            return
        asyncio.create_task(handle_invoke(payload, client, skill_bins))

    client.on_event = _on_event
    client.start()

    logger.info(f"[node_host] connected to {url} as node {node_id}")
    # Keep running indefinitely
    await asyncio.Event().wait()
