"""
Agent timeout utilities — fully aligned with TypeScript
openclaw/src/agents/timeout.ts.
"""
from __future__ import annotations

from typing import Any

DEFAULT_AGENT_TIMEOUT_SECONDS = 600  # 10 minutes
MAX_SAFE_TIMEOUT_MS = 2_147_000_000  # ~24.8 days


def _normalize_number(value: Any) -> int | None:
    """Return a finite integer or None — mirrors TS normalizeNumber()."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and value == value and abs(value) != float("inf"):
        return int(value)
    return None


def resolve_agent_timeout_seconds(cfg: Any = None) -> int:
    """Return the configured agent timeout in seconds.

    Mirrors TS resolveAgentTimeoutSeconds().

    Args:
        cfg: OpenClaw config dict. Reads agents.defaults.timeoutSeconds.

    Returns:
        Effective timeout in seconds (minimum 1).
    """
    raw: Any = None
    if isinstance(cfg, dict):
        agents_cfg = cfg.get("agents")
        if isinstance(agents_cfg, dict):
            defaults_cfg = agents_cfg.get("defaults")
            if isinstance(defaults_cfg, dict):
                raw = defaults_cfg.get("timeoutSeconds")
    normalized = _normalize_number(raw)
    seconds = normalized if normalized is not None else DEFAULT_AGENT_TIMEOUT_SECONDS
    return max(seconds, 1)


def resolve_agent_timeout_ms(
    cfg: Any = None,
    *,
    override_ms: Any = None,
    override_seconds: Any = None,
    min_ms: Any = None,
) -> int:
    """Return the effective agent timeout in milliseconds.

    Mirrors TS resolveAgentTimeoutMs().

    Args:
        cfg: OpenClaw config dict.
        override_ms: Override in ms (0 = no timeout, negative = use default).
        override_seconds: Override in seconds (0 = no timeout, negative = use default).
        min_ms: Minimum timeout in ms (default 1).

    Returns:
        Effective timeout in milliseconds.
    """
    resolved_min_ms = max(_normalize_number(min_ms) or 1, 1)

    def clamp(value_ms: int) -> int:
        return min(max(value_ms, resolved_min_ms), MAX_SAFE_TIMEOUT_MS)

    default_ms = clamp(resolve_agent_timeout_seconds(cfg) * 1000)

    # 0 = no timeout (max safe value)
    NO_TIMEOUT_MS = MAX_SAFE_TIMEOUT_MS

    norm_override_ms = _normalize_number(override_ms)
    if norm_override_ms is not None:
        if norm_override_ms == 0:
            return NO_TIMEOUT_MS
        if norm_override_ms < 0:
            return default_ms
        return clamp(norm_override_ms)

    norm_override_seconds = _normalize_number(override_seconds)
    if norm_override_seconds is not None:
        if norm_override_seconds == 0:
            return NO_TIMEOUT_MS
        if norm_override_seconds < 0:
            return default_ms
        return clamp(norm_override_seconds * 1000)

    return default_ms
