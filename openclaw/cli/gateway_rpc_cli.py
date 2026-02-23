"""CLI gateway RPC utility — mirrors TypeScript src/cli/gateway-rpc.ts"""
from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass, field
from typing import Any, Optional

from rich.console import Console

console = Console(stderr=True)


@dataclass
class GatewayRpcOpts:
    """Options for CLI gateway RPC calls."""
    url: Optional[str] = None
    token: Optional[str] = None
    timeout: int = 30_000
    expect_final: bool = False
    json_output: bool = False


def _resolve_gateway_url(url: Optional[str] = None) -> str:
    if url:
        return url
    try:
        from ..config.loader import load_config
        from ..config.paths import DEFAULT_GATEWAY_PORT
        cfg = load_config()
        port = DEFAULT_GATEWAY_PORT
        if cfg and hasattr(cfg, "gateway") and cfg.gateway:
            gw = cfg.gateway
            if isinstance(gw, dict):
                port = gw.get("port", port)
            elif hasattr(gw, "port") and gw.port:
                port = gw.port
        remote_url = None
        if cfg and hasattr(cfg, "gateway") and cfg.gateway:
            gw = cfg.gateway
            if isinstance(gw, dict):
                remote = gw.get("remote", {}) or {}
                remote_url = (remote.get("url") if isinstance(remote, dict) else None)
            elif hasattr(gw, "remote") and gw.remote:
                remote_url = getattr(gw.remote, "url", None)
        if remote_url:
            return remote_url
        return f"ws://localhost:{port}"
    except Exception:
        return "ws://localhost:18789"


def _resolve_auth_token(token: Optional[str] = None) -> Optional[str]:
    if token:
        return token
    try:
        from ..config.loader import load_config
        cfg = load_config()
        if cfg and hasattr(cfg, "gateway") and cfg.gateway:
            gw = cfg.gateway
            if isinstance(gw, dict):
                auth = gw.get("auth") or {}
                return (auth.get("token") if isinstance(auth, dict) else None)
            elif hasattr(gw, "auth") and gw.auth:
                return getattr(gw.auth, "token", None)
    except Exception:
        pass
    return None


def call_gateway_from_cli(
    method: str,
    opts: GatewayRpcOpts,
    params: Any = None,
    *,
    expect_final: Optional[bool] = None,
    show_progress: Optional[bool] = None,
) -> Any:
    """
    Call a gateway RPC method from the CLI.

    Mirrors TypeScript ``callGatewayFromCli`` in gateway-rpc.ts:
    - Resolves URL / token from config when not explicitly supplied.
    - Shows a spinner unless JSON output mode is enabled.
    - Returns the raw result dict/list from the gateway.
    """
    url = _resolve_gateway_url(opts.url)
    auth_token = _resolve_auth_token(opts.token)
    timeout_ms = opts.timeout if opts.timeout is not None else 30_000
    use_expect_final = expect_final if expect_final is not None else opts.expect_final
    use_progress = show_progress if show_progress is not None else (not opts.json_output)

    from ..gateway.rpc_client import GatewayRPCClient, GatewayRPCError

    client = GatewayRPCClient(url=url, auth_token=auth_token)

    spinner = None
    if use_progress:
        try:
            from rich.spinner import Spinner as _S  # noqa: F401
            console.print(f"[dim]  → {method}…[/dim]", end="\r")
        except Exception:
            pass

    try:
        result = asyncio.run(
            asyncio.wait_for(
                client.call(method, params or {}),
                timeout=timeout_ms / 1000,
            )
        )
        if use_progress:
            # Clear the progress line
            console.print(" " * 60, end="\r")
        return result
    except asyncio.TimeoutError:
        if use_progress:
            console.print(" " * 60, end="\r")
        raise GatewayRPCError(f"Gateway call timed out after {timeout_ms}ms")
    except GatewayRPCError:
        if use_progress:
            console.print(" " * 60, end="\r")
        raise


def gateway_unreachable_message() -> str:
    return (
        "Gateway is not running or unreachable.\n"
        "Start with: [cyan]openclaw gateway run[/cyan]"
    )
