"""
Configuration defaults matching TypeScript openclaw/src/config/agent-limits.ts
"""
from __future__ import annotations

from typing import Any

# Agent concurrency defaults (aligned with TS)
DEFAULT_AGENT_MAX_CONCURRENT = 4
DEFAULT_SUBAGENT_MAX_CONCURRENT = 8


def resolve_agent_max_concurrent(cfg: dict[str, Any] | None) -> int:
    """
    Resolve agent max concurrent setting with fallback to default
    
    Args:
        cfg: OpenClaw configuration dict
        
    Returns:
        Max concurrent value (>= 1)
    """
    if not cfg:
        return DEFAULT_AGENT_MAX_CONCURRENT
    
    raw = cfg.get("agents", {}).get("defaults", {}).get("maxConcurrent")
    if isinstance(raw, (int, float)) and raw > 0:
        return max(1, int(raw))
    
    return DEFAULT_AGENT_MAX_CONCURRENT


def resolve_subagent_max_concurrent(cfg: dict[str, Any] | None) -> int:
    """
    Resolve subagent max concurrent setting with fallback to default
    
    Args:
        cfg: OpenClaw configuration dict
        
    Returns:
        Max concurrent value (>= 1)
    """
    if not cfg:
        return DEFAULT_SUBAGENT_MAX_CONCURRENT
    
    raw = (
        cfg.get("agents", {})
        .get("defaults", {})
        .get("subagents", {})
        .get("maxConcurrent")
    )
    if isinstance(raw, (int, float)) and raw > 0:
        return max(1, int(raw))
    
    return DEFAULT_SUBAGENT_MAX_CONCURRENT


def apply_agent_defaults(cfg: dict[str, Any]) -> dict[str, Any]:
    """
    Apply default values to agent configuration
    
    Injects DEFAULT_AGENT_MAX_CONCURRENT and DEFAULT_SUBAGENT_MAX_CONCURRENT
    if not explicitly set by user.
    
    Args:
        cfg: OpenClaw configuration dict
        
    Returns:
        Configuration with defaults applied
    """
    agents = cfg.get("agents", {})
    defaults = agents.get("defaults", {})
    
    has_max = isinstance(defaults.get("maxConcurrent"), (int, float))
    subagents = defaults.get("subagents", {})
    has_sub_max = isinstance(subagents.get("maxConcurrent"), (int, float))
    
    if has_max and has_sub_max:
        return cfg
    
    mutated = False
    next_defaults = dict(defaults)
    
    if not has_max:
        next_defaults["maxConcurrent"] = DEFAULT_AGENT_MAX_CONCURRENT
        mutated = True
    
    next_subagents = dict(subagents)
    if not has_sub_max:
        next_subagents["maxConcurrent"] = DEFAULT_SUBAGENT_MAX_CONCURRENT
        mutated = True
    
    if not mutated:
        return cfg
    
    return {
        **cfg,
        "agents": {
            **agents,
            "defaults": {
                **next_defaults,
                "subagents": next_subagents,
            },
        },
    }
