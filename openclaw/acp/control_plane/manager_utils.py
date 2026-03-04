"""ACP session manager utilities — mirrors src/acp/control-plane/manager.utils.ts"""
from __future__ import annotations

from typing import Any

from openclaw.acp.runtime.errors import ACP_ERROR_CODES, AcpRuntimeError


def resolve_acp_agent_from_session_key(session_key: str, fallback: str = "main") -> str:
    """Extract and normalise the agent ID from a session key (e.g. 'agent:codex:main')."""
    parts = session_key.strip().split(":")
    if len(parts) >= 2:
        agent = parts[1].strip().lower()
        return agent or fallback.lower()
    return fallback.lower()


def resolve_missing_meta_error(session_key: str) -> AcpRuntimeError:
    return AcpRuntimeError(
        "ACP_SESSION_INIT_FAILED",
        f"ACP metadata is missing for {session_key}. "
        "Recreate this ACP session with /acp spawn and rebind the thread.",
    )


def normalize_session_key(session_key: str) -> str:
    return session_key.strip()


def normalize_actor_key(session_key: str) -> str:
    return session_key.strip().lower()


def normalize_acp_error_code(code: str | None) -> str:
    if not code:
        return "ACP_TURN_FAILED"
    normalized = code.strip().upper()
    for allowed in ACP_ERROR_CODES:
        if allowed == normalized:
            return allowed
    return "ACP_TURN_FAILED"


def create_unsupported_control_error(backend: str, control: str) -> AcpRuntimeError:
    return AcpRuntimeError(
        "ACP_BACKEND_UNSUPPORTED_CONTROL",
        f'ACP backend "{backend}" does not support {control}.',
    )


def resolve_runtime_idle_ttl_ms(cfg: Any) -> float:
    """Return the idle TTL in milliseconds from config (0 = disabled)."""
    acp_cfg = getattr(cfg, "acp", None) or {}
    if isinstance(acp_cfg, dict):
        runtime_cfg = acp_cfg.get("runtime") or {}
        ttl_minutes = runtime_cfg.get("ttlMinutes") if isinstance(runtime_cfg, dict) else None
    else:
        runtime_cfg = getattr(acp_cfg, "runtime", None) or {}
        ttl_minutes = getattr(runtime_cfg, "ttl_minutes", None) or \
                      (runtime_cfg.get("ttlMinutes") if isinstance(runtime_cfg, dict) else None)

    if not isinstance(ttl_minutes, (int, float)) or ttl_minutes <= 0:
        return 0.0
    return ttl_minutes * 60 * 1000


def has_legacy_acp_identity_projection(meta: dict) -> bool:
    return any(k in meta for k in ("backendSessionId", "agentSessionId", "sessionIdsProvisional"))
