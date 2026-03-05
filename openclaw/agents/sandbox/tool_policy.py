"""Sandbox tool policy enforcement

Determines which agent tools are allowed or denied inside a sandboxed
session using glob-style pattern matching.

Mirrors TypeScript openclaw/src/agents/sandbox/tool-policy.ts
"""
from __future__ import annotations

import fnmatch
import logging
from typing import Any

from .context import SandboxToolPolicy

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default allow / deny lists (mirrors TS constants.ts DEFAULT_TOOL_*)
# ---------------------------------------------------------------------------

DEFAULT_SANDBOX_TOOL_ALLOW: list[str] = [
    "exec",
    "process",
    "read",
    "write",
    "edit",
    "apply_patch",
    "image",
    "sessions_list",
    "sessions_history",
    "sessions_send",
    "sessions_spawn",
    "subagents",
    "session_status",
]

DEFAULT_SANDBOX_TOOL_DENY: list[str] = [
    "browser",
    "canvas",
    "nodes",
    "cron",
    "gateway",
    # Channel tool groups (mirrors TS `...CHANNEL_IDS` spread)
    "feishu",
    "feishu_*",
    "telegram",
    "telegram_*",
    "discord",
    "discord_*",
    "whatsapp",
    "whatsapp_*",
    "line",
    "slack",
]


def _normalize(name: str) -> str:
    return name.strip().lower()


def is_tool_allowed(policy: SandboxToolPolicy, tool_name: str) -> bool:
    """Return True if *tool_name* is permitted by *policy*.

    Deny list is checked first; then allow list (empty allow = allow-all).

    Mirrors TS ``isToolAllowed()``.
    """
    normalized = _normalize(tool_name)

    # Expand deny patterns; check deny first
    deny_expanded = _expand(policy.deny)
    for pattern in deny_expanded:
        if fnmatch.fnmatch(normalized, _normalize(pattern)):
            return False

    # Empty allow list → allow anything not denied
    allow_expanded = _expand(policy.allow)
    if not allow_expanded:
        return True

    for pattern in allow_expanded:
        if fnmatch.fnmatch(normalized, _normalize(pattern)):
            return True

    return False


def _expand(tool_list: list[str] | None) -> list[str]:
    """Expand tool group names to individual tool names."""
    if not tool_list:
        return []
    try:
        from openclaw.agents.tool_policy import expand_tool_groups  # type: ignore[import]
        return expand_tool_groups(tool_list)
    except (ImportError, Exception):
        return list(tool_list)


def resolve_sandbox_tool_policy_for_agent(
    cfg: Any | None,
    agent_id: str | None,
) -> SandboxToolPolicy:
    """Build the effective :class:`SandboxToolPolicy` for *agent_id*.

    Priority chain (highest first):
      1. ``agents.list[agent_id].tools.sandbox.tools``
      2. ``tools.sandbox.tools`` (global)
      3. :data:`DEFAULT_SANDBOX_TOOL_ALLOW` / :data:`DEFAULT_SANDBOX_TOOL_DENY`

    Always injects ``"image"`` into the allow list when:
    - the allow list is non-empty (non-empty means "explicit allow list"), and
    - ``"image"`` is not already in either list.

    Mirrors TS ``resolveSandboxToolPolicyForAgent()``.
    """
    agent_allow: list[str] | None = None
    agent_deny: list[str] | None = None
    global_allow: list[str] | None = None
    global_deny: list[str] | None = None

    if isinstance(cfg, dict) and agent_id:
        try:
            from openclaw.agents.agent_scope import resolve_agent_config  # type: ignore[import]
            agent_cfg = resolve_agent_config(cfg, agent_id)
            if isinstance(agent_cfg, dict):
                tools_sandbox = (
                    agent_cfg.get("tools", {}).get("sandbox", {}).get("tools", {})
                )
                if isinstance(tools_sandbox, dict):
                    raw_allow = tools_sandbox.get("allow")
                    raw_deny = tools_sandbox.get("deny")
                    if isinstance(raw_allow, list):
                        agent_allow = raw_allow
                    if isinstance(raw_deny, list):
                        agent_deny = raw_deny
        except (ImportError, Exception):
            pass

    if isinstance(cfg, dict):
        global_tools = cfg.get("tools", {})
        if isinstance(global_tools, dict):
            global_sandbox = global_tools.get("sandbox", {})
            if isinstance(global_sandbox, dict):
                global_sandbox_tools = global_sandbox.get("tools", {})
                if isinstance(global_sandbox_tools, dict):
                    raw = global_sandbox_tools.get("allow")
                    if isinstance(raw, list):
                        global_allow = raw
                    raw = global_sandbox_tools.get("deny")
                    if isinstance(raw, list):
                        global_deny = raw

    deny_list = agent_deny if isinstance(agent_deny, list) else (
        global_deny if isinstance(global_deny, list) else list(DEFAULT_SANDBOX_TOOL_DENY)
    )
    allow_list = agent_allow if isinstance(agent_allow, list) else (
        global_allow if isinstance(global_allow, list) else list(DEFAULT_SANDBOX_TOOL_ALLOW)
    )

    expanded_deny = _expand(deny_list)
    expanded_allow = _expand(allow_list)

    # Inject "image" when it is not already present
    if (
        expanded_allow
        and "image" not in [_normalize(t) for t in expanded_deny]
        and "image" not in [_normalize(t) for t in expanded_allow]
    ):
        expanded_allow = [*expanded_allow, "image"]

    return SandboxToolPolicy(allow=expanded_allow, deny=expanded_deny)
