"""
Origin / CSRF / DNS-rebinding protection for gateway WebSocket upgrade.

Mirrors TS src/gateway/origin-check.ts.

Threat model:
- Malicious web pages making cross-origin requests to a locally running gateway
- DNS rebinding attacks that replace a safe origin with the gateway's IP
- Phishing pages that forward auth tokens to the gateway

Usage:
    from openclaw.security.origin_check import check_browser_origin, OriginCheckResult

    result = check_browser_origin(
        origin_header=request.headers.get("origin"),
        host_header=request.headers.get("host"),
        allowed_origins=config.gateway.cors_origins,
    )
    if not result.ok:
        raise HTTPException(403, result.reason)
"""
from __future__ import annotations

import logging
from typing import NamedTuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class OriginCheckResult(NamedTuple):
    ok: bool
    reason: str | None = None


# Schemes that are always safe (non-web browser extension / native)
_SAFE_SCHEMES: frozenset[str] = frozenset(["tauri", "electron", "app"])

# Loopback hostnames that are allowed as origins
_LOOPBACK_HOSTS: frozenset[str] = frozenset(
    ["localhost", "127.0.0.1", "::1", "0.0.0.0"]
)


def _is_loopback_host(host: str) -> bool:
    h = host.lower().split(":")[0]  # strip port
    if h in _LOOPBACK_HOSTS:
        return True
    if h.startswith("127."):
        return True
    return False


def _resolve_host_from_header(host_header: str | None) -> str:
    """Strip port from Host header value."""
    if not host_header:
        return ""
    h = host_header.strip().lower()
    # IPv6 format: [::1]:port
    if h.startswith("[") and "]" in h:
        return h[1 : h.index("]")]
    return h.split(":")[0]


def _origin_matches_host(origin_host: str, host_header_host: str) -> bool:
    """Check if the parsed origin host matches the gateway Host header."""
    oh = origin_host.lower().split(":")[0]
    hh = host_header_host.lower()
    return oh == hh


def check_browser_origin(
    origin_header: str | None,
    host_header: str | None = None,
    allowed_origins: list[str] | None = None,
    *,
    dangerously_allow_host_header_origin_fallback: bool = False,
) -> OriginCheckResult:
    """
    Validate the Origin header on a browser WebSocket upgrade request.

    Logic (mirrors TS checkBrowserOrigin):
    1. No Origin header → probably a non-browser client (CLI, curl) → allow.
    2. Origin in explicit allowlist → allow.
    3. Origin scheme is a safe native scheme (tauri, electron, app) → allow.
    4. Origin host matches Host header → allow (same-origin; prevents DNS rebinding
       only when the Host header is properly validated at the network layer).
    5. dangerouslyAllowHostHeaderOriginFallback=true → allow any matching host.
    6. Otherwise → deny with DNS-rebinding protection reason.

    Args:
        origin_header: value of the HTTP Origin header (may be None)
        host_header: value of the HTTP Host header
        allowed_origins: explicit CORS allowlist from config
        dangerously_allow_host_header_origin_fallback: named-dangerous override

    Returns:
        OriginCheckResult with ok=True/False and reason string on failure.
    """
    # No Origin → non-browser client (curl, CLI, SDK) → allow
    if not origin_header:
        return OriginCheckResult(ok=True)

    origin = origin_header.strip()

    # null origin (e.g. file://) — deny by default
    if origin.lower() == "null":
        return OriginCheckResult(ok=False, reason="origin_null")

    # Check explicit allowlist first
    if allowed_origins:
        for allowed in allowed_origins:
            if origin == allowed.strip():
                return OriginCheckResult(ok=True)
            # Wildcard suffix match: "*.example.com"
            if allowed.startswith("*."):
                suffix = allowed[1:]  # e.g. ".example.com"
                parsed = urlparse(origin)
                if parsed.hostname and parsed.hostname.endswith(suffix):
                    return OriginCheckResult(ok=True)

    # Parse origin URL
    try:
        parsed = urlparse(origin)
        scheme = (parsed.scheme or "").lower()
        origin_host = (parsed.hostname or "").lower()
    except Exception:
        return OriginCheckResult(ok=False, reason="origin_parse_error")

    # Safe native schemes
    if scheme in _SAFE_SCHEMES:
        return OriginCheckResult(ok=True)

    # Loopback origins are always allowed (same machine, no cross-origin risk)
    if _is_loopback_host(origin_host):
        return OriginCheckResult(ok=True)

    # Tailscale .ts.net origins are trusted (same Tailscale network)
    if origin_host.endswith(".ts.net"):
        return OriginCheckResult(ok=True)

    # Origin host must match gateway Host header (DNS-rebinding protection)
    gateway_host = _resolve_host_from_header(host_header)
    if gateway_host and _origin_matches_host(origin_host, gateway_host):
        return OriginCheckResult(ok=True)

    # Named dangerous override: allow origin if it matches the Host header value
    # (useful when running behind a reverse proxy that rewrites Host)
    if dangerously_allow_host_header_origin_fallback and gateway_host:
        if origin_host == gateway_host:
            return OriginCheckResult(ok=True)

    logger.warning(
        f"Origin check failed: origin={origin!r} does not match host={host_header!r} "
        f"and is not in allowlist. Possible DNS-rebinding attack."
    )
    return OriginCheckResult(
        ok=False,
        reason=f"origin_not_allowed:{origin}",
    )


__all__ = ["OriginCheckResult", "check_browser_origin"]
