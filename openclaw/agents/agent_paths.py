"""Agent directory path utilities.

Aligned with TypeScript openclaw/src/agents/agent-paths.ts.
"""
from __future__ import annotations

import os
from pathlib import Path


def resolve_openclaw_agent_dir() -> str:
    """Return the OpenClaw agent directory path.

    Respects OPENCLAW_AGENT_DIR and PI_CODING_AGENT_DIR env vars.
    Mirrors TS resolveOpenClawAgentDir().
    """
    override = (
        os.environ.get("OPENCLAW_AGENT_DIR", "").strip()
        or os.environ.get("PI_CODING_AGENT_DIR", "").strip()
    )
    if override:
        return str(Path(override).expanduser().resolve())

    from openclaw.config.paths import resolve_state_dir
    from openclaw.routing.session_key import DEFAULT_AGENT_ID

    state_dir = resolve_state_dir()
    default_agent_dir = Path(state_dir) / "agents" / DEFAULT_AGENT_ID / "agent"
    return str(default_agent_dir.expanduser().resolve())


def ensure_openclaw_agent_env() -> str:
    """Resolve agent dir and export it to environment variables.

    Mirrors TS ensureOpenClawAgentEnv().
    """
    directory = resolve_openclaw_agent_dir()
    if not os.environ.get("OPENCLAW_AGENT_DIR"):
        os.environ["OPENCLAW_AGENT_DIR"] = directory
    if not os.environ.get("PI_CODING_AGENT_DIR"):
        os.environ["PI_CODING_AGENT_DIR"] = directory
    return directory


__all__ = ["resolve_openclaw_agent_dir", "ensure_openclaw_agent_env"]
