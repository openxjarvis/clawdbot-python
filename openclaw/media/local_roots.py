"""Media local roots configuration.

Mirrors TypeScript src/media/local-roots.ts
Provides functions to resolve allowed local directories for media access.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


_cached_preferred_tmp_dir: Optional[str] = None


def _resolve_cached_preferred_tmp_dir() -> str:
    """Resolve and cache preferred OpenClaw temp directory.
    
    Mirrors TS resolveCachedPreferredTmpDir() lines 13-18.
    """
    global _cached_preferred_tmp_dir
    if _cached_preferred_tmp_dir is None:
        from openclaw.config.paths import resolve_preferred_openclaw_tmp_dir
        _cached_preferred_tmp_dir = resolve_preferred_openclaw_tmp_dir()
    return _cached_preferred_tmp_dir


def build_media_local_roots(
    state_dir: str,
    preferred_tmp_dir: Optional[str] = None,
) -> list[str]:
    """Build standard media local roots list.
    
    Mirrors TS buildMediaLocalRoots() from lines 20-33.
    
    Args:
        state_dir: State directory path (typically ~/.openclaw)
        preferred_tmp_dir: Optional preferred temp dir override
    
    Returns:
        List of allowed root directories for media access
    """
    resolved_state_dir = os.path.abspath(state_dir)
    tmp_dir = preferred_tmp_dir if preferred_tmp_dir is not None else _resolve_cached_preferred_tmp_dir()
    
    return [
        tmp_dir,
        os.path.join(resolved_state_dir, "media"),
        os.path.join(resolved_state_dir, "agents"),
        os.path.join(resolved_state_dir, "workspace"),
        os.path.join(resolved_state_dir, "sandboxes"),
    ]


def get_default_media_local_roots() -> list[str]:
    """Get default media local roots (no agent-specific workspace).
    
    Mirrors TS getDefaultMediaLocalRoots() lines 35-37.
    """
    from openclaw.config.paths import resolve_state_dir
    return build_media_local_roots(resolve_state_dir())


def get_agent_scoped_media_local_roots(
    cfg: dict | None,
    agent_id: Optional[str] = None,
) -> list[str]:
    """Get media local roots including agent-specific workspace.
    
    Mirrors TS getAgentScopedMediaLocalRoots() from lines 39-56.
    
    When agent_id is provided, includes the agent's workspace directory
    in the allowed roots list (if not already included).
    
    Args:
        cfg: OpenClaw config dict
        agent_id: Agent identifier (optional)
    
    Returns:
        List of allowed root directories for media access
    """
    from openclaw.config.paths import resolve_state_dir
    
    roots = build_media_local_roots(resolve_state_dir())
    
    if not agent_id or not agent_id.strip():
        return roots
    
    # Resolve agent workspace directory
    workspace_dir = _resolve_agent_workspace_dir(cfg, agent_id)
    if not workspace_dir:
        return roots
    
    # Normalize and add if not already present
    normalized_workspace_dir = os.path.abspath(workspace_dir)
    if normalized_workspace_dir not in roots:
        roots.append(normalized_workspace_dir)
    
    return roots


def _resolve_agent_workspace_dir(cfg: dict | None, agent_id: str) -> Optional[str]:
    """Resolve agent workspace directory.
    
    Mirrors TS resolveAgentWorkspaceDir() from agent-scope.ts lines 255-271.
    
    Resolution order:
    1. Agent-specific config: cfg.agents[agent_id].workspace
    2. Default agent fallback: cfg.agents.defaults.workspace
    3. State dir fallback: {state_dir}/workspace-{agent_id}
    
    Args:
        cfg: OpenClaw config dict
        agent_id: Agent identifier
    
    Returns:
        Absolute workspace directory path, or None if cannot be resolved
    """
    from openclaw.config.paths import resolve_state_dir, resolve_user_path
    from openclaw.routing.session_key import normalize_agent_id
    
    if not cfg or not agent_id:
        return None
    
    normalized_id = normalize_agent_id(agent_id)
    
    # 1. Check agent-specific config
    agents = cfg.get("agents", {})
    agent_config = agents.get(normalized_id, {})
    configured = agent_config.get("workspace", "").strip()
    if configured:
        return resolve_user_path(configured)
    
    # 2. Check if this is the default agent
    default_agent_id = cfg.get("agent", "").strip() or "default"
    if normalized_id == normalize_agent_id(default_agent_id):
        fallback = agents.get("defaults", {}).get("workspace", "").strip()
        if fallback:
            return resolve_user_path(fallback)
        
        # Use environment-based default workspace
        default_workspace = os.environ.get("OPENCLAW_WORKSPACE")
        if default_workspace:
            return os.path.abspath(default_workspace)
        
        # Final fallback to ~/.openclaw/workspace
        return os.path.join(resolve_state_dir(), "workspace")
    
    # 3. Per-agent workspace in state dir
    state_dir = resolve_state_dir()
    return os.path.join(state_dir, f"workspace-{normalized_id}")


__all__ = [
    "build_media_local_roots",
    "get_default_media_local_roots",
    "get_agent_scoped_media_local_roots",
]
