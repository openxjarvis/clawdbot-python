"""Sandbox runtime status resolution

Determines whether a given session should run inside a Docker sandbox.
Mirrors TypeScript openclaw/src/agents/sandbox/runtime-status.ts
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _should_sandbox_session(mode: str, session_key: str, main_session_key: str) -> bool:
    """Return True if the session should be sandboxed given the mode.

    Mirrors TS ``shouldSandboxSession()``.
    """
    if mode == "off":
        return False
    if mode == "all":
        return True
    # "non-main": sandbox any session that is NOT the main session
    return session_key.strip() != main_session_key.strip()


def _resolve_main_session_key(cfg: Any | None, agent_id: str) -> str:
    """Resolve the main session key for sandbox comparison.

    Mirrors TS ``resolveMainSessionKeyForSandbox()``.
    """
    if cfg is None:
        return "main"

    # Global session scope → use literal "global"
    session_cfg = cfg.get("session", {}) if isinstance(cfg, dict) else {}
    if session_cfg.get("scope") == "global":
        return "global"

    # Delegate to the sessions config helper if available
    try:
        from openclaw.config.sessions import resolve_agent_main_session_key  # type: ignore[import]
        return resolve_agent_main_session_key(cfg=cfg, agent_id=agent_id)
    except (ImportError, Exception):
        pass

    # Fallback: derive from agents.list[agent_id].sessions.main
    if isinstance(cfg, dict):
        agents = cfg.get("agents", {})
        agents_list = agents.get("list", {}) if isinstance(agents, dict) else {}
        agent_entry = agents_list.get(agent_id, {}) if isinstance(agents_list, dict) else {}
        sessions_cfg = agent_entry.get("sessions", {}) if isinstance(agent_entry, dict) else {}
        main = sessions_cfg.get("main") if isinstance(sessions_cfg, dict) else None
        if main:
            return str(main)
    return "main"


def resolve_sandbox_runtime_status(
    cfg: Any | None,
    session_key: str,
) -> dict:
    """Return sandbox runtime status for a session.

    Mirrors TS ``resolveSandboxRuntimeStatus()``.

    Returns a dict with keys:
        agent_id     (str)
        session_key  (str)
        main_session_key (str)
        mode         ("off" | "non-main" | "all")
        sandboxed    (bool)
        tool_policy  (dict with "allow" and "deny" lists)
    """
    sk = (session_key or "").strip()

    # Resolve agent_id from session_key
    try:
        from openclaw.agents.agent_scope import resolve_session_agent_id  # type: ignore[import]
        agent_id = resolve_session_agent_id(session_key=sk, config=cfg)
    except (ImportError, Exception):
        agent_id = sk.split(":")[0] if ":" in sk else "default"

    # Resolve sandbox config for the agent
    try:
        from openclaw.agents.sandbox.config import resolve_sandbox_config_for_agent  # type: ignore[import]
        sandbox_cfg = resolve_sandbox_config_for_agent(cfg, agent_id)
        mode = sandbox_cfg.mode
        tool_policy = {
            "allow": list(sandbox_cfg.tool_policy.allow),
            "deny": list(sandbox_cfg.tool_policy.deny),
        }
    except (ImportError, Exception):
        # Fallback: read from raw config dict
        agents_defaults = {}
        if isinstance(cfg, dict):
            agents_defaults = cfg.get("agents", {}).get("defaults", {}).get("sandbox", {})
        mode = agents_defaults.get("mode", "off") if isinstance(agents_defaults, dict) else "off"
        tool_policy = {"allow": [], "deny": []}

    main_session_key = _resolve_main_session_key(cfg, agent_id)

    sandboxed: bool
    if sk:
        sandboxed = _should_sandbox_session(mode, sk, main_session_key)
    else:
        sandboxed = False

    return {
        "agent_id": agent_id,
        "session_key": sk,
        "main_session_key": main_session_key,
        "mode": mode,
        "sandboxed": sandboxed,
        "tool_policy": tool_policy,
    }


def format_sandbox_tool_policy_blocked_message(
    cfg: Any | None,
    session_key: str,
    tool_name: str,
) -> str | None:
    """Return a human-readable message when *tool_name* is blocked by sandbox policy.

    Returns ``None`` if the tool is not blocked (or sandbox is off).

    Mirrors TS ``formatSandboxToolPolicyBlockedMessage()``.
    """
    tool = tool_name.strip().lower()
    if not tool:
        return None

    runtime = resolve_sandbox_runtime_status(cfg, session_key)
    if not runtime["sandboxed"]:
        return None

    # Check tool policy
    try:
        from openclaw.agents.sandbox.tool_policy import is_tool_allowed  # type: ignore[import]
        from openclaw.agents.sandbox.context import SandboxToolPolicy  # type: ignore[import]

        policy = SandboxToolPolicy(
            allow=runtime["tool_policy"].get("allow", []),
            deny=runtime["tool_policy"].get("deny", []),
        )
        if is_tool_allowed(policy, tool):
            return None
    except (ImportError, Exception):
        pass

    deny_list = runtime["tool_policy"].get("deny", [])
    allow_list = runtime["tool_policy"].get("allow", [])
    mode = runtime["mode"]

    lines: list[str] = [
        f'Tool "{tool}" blocked by sandbox tool policy (mode={mode}).',
        f'Session: {runtime["session_key"] or "(unknown)"}',
        "Fix:",
        "- Set agents.defaults.sandbox.mode=off to disable sandbox",
    ]
    if tool in deny_list:
        lines.append(f'- Remove "{tool}" from sandbox tool deny list')
    if allow_list and tool not in allow_list:
        lines.append(f'- Add "{tool}" to sandbox tool allow list (or set it to [] to allow all)')
    if mode == "non-main":
        lines.append(f'- Use main session key: {runtime["main_session_key"]}')

    return "\n".join(lines)
