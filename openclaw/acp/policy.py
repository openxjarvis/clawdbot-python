"""ACP policy enforcement — mirrors src/acp/policy.ts

Checks the OpenClaw config to determine whether ACP and ACP dispatch are
enabled, and whether a specific agent ID is allowed.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from openclaw.config.loader import OpenClawConfig

AcpDispatchPolicyState = Literal["enabled", "acp_disabled", "dispatch_disabled"]

_ACP_DISABLED_MESSAGE = "ACP is disabled by policy (`acp.enabled=false`)."
_ACP_DISPATCH_DISABLED_MESSAGE = (
    "ACP dispatch is disabled by policy (`acp.dispatch.enabled=false`)."
)


def _normalize_agent_id(agent_id: str) -> str:
    """Normalise an agent ID to lower-case stripped form."""
    return agent_id.strip().lower()


def is_acp_enabled_by_policy(cfg: "OpenClawConfig") -> bool:
    """Return True unless acp.enabled is explicitly False in the config."""
    acp_cfg = getattr(cfg, "acp", None) or {}
    if isinstance(acp_cfg, dict):
        return acp_cfg.get("enabled", True) is not False
    enabled = getattr(acp_cfg, "enabled", True)
    return enabled is not False


def resolve_acp_dispatch_policy_state(cfg: "OpenClawConfig") -> AcpDispatchPolicyState:
    """
    Determine the ACP dispatch policy state.

    Returns:
        "enabled"          — ACP and dispatch are both on (or not configured)
        "acp_disabled"     — acp.enabled=false
        "dispatch_disabled"— acp.dispatch.enabled=false
    """
    if not is_acp_enabled_by_policy(cfg):
        return "acp_disabled"

    acp_cfg = getattr(cfg, "acp", None) or {}
    if isinstance(acp_cfg, dict):
        dispatch_cfg = acp_cfg.get("dispatch") or {}
        if isinstance(dispatch_cfg, dict) and dispatch_cfg.get("enabled") is False:
            return "dispatch_disabled"
    else:
        dispatch_cfg = getattr(acp_cfg, "dispatch", None) or {}
        if isinstance(dispatch_cfg, dict):
            if dispatch_cfg.get("enabled") is False:
                return "dispatch_disabled"
        else:
            if getattr(dispatch_cfg, "enabled", True) is False:
                return "dispatch_disabled"

    return "enabled"


def is_acp_dispatch_enabled_by_policy(cfg: "OpenClawConfig") -> bool:
    return resolve_acp_dispatch_policy_state(cfg) == "enabled"


def resolve_acp_dispatch_policy_message(cfg: "OpenClawConfig") -> str | None:
    state = resolve_acp_dispatch_policy_state(cfg)
    if state == "acp_disabled":
        return _ACP_DISABLED_MESSAGE
    if state == "dispatch_disabled":
        return _ACP_DISPATCH_DISABLED_MESSAGE
    return None


def resolve_acp_dispatch_policy_error(cfg: "OpenClawConfig") -> Exception | None:
    """
    Return an AcpRuntimeError if dispatch is disabled by policy, else None.
    Mirrors resolveAcpDispatchPolicyError().
    """
    message = resolve_acp_dispatch_policy_message(cfg)
    if not message:
        return None
    try:
        from openclaw.acp.runtime.errors import AcpRuntimeError
        return AcpRuntimeError("ACP_DISPATCH_DISABLED", message)
    except ImportError:
        return RuntimeError(message)


def is_acp_agent_allowed_by_policy(cfg: "OpenClawConfig", agent_id: str) -> bool:
    """
    Return True if the given agent ID is permitted by the allowedAgents list.

    An empty (or absent) allowedAgents list means all agents are allowed.
    """
    acp_cfg = getattr(cfg, "acp", None) or {}
    if isinstance(acp_cfg, dict):
        allowed_raw: list = acp_cfg.get("allowedAgents") or []
    else:
        allowed_raw = getattr(acp_cfg, "allowed_agents", None) or \
                      getattr(acp_cfg, "allowedAgents", None) or []

    allowed = [_normalize_agent_id(a) for a in allowed_raw if isinstance(a, str) and a.strip()]
    if not allowed:
        return True
    return _normalize_agent_id(agent_id) in allowed


def resolve_acp_agent_policy_error(cfg: "OpenClawConfig", agent_id: str) -> Exception | None:
    """
    Return an AcpRuntimeError if the agent is blocked by the allowedAgents policy, else None.
    Mirrors resolveAcpAgentPolicyError().
    """
    if is_acp_agent_allowed_by_policy(cfg, agent_id):
        return None
    normalized = _normalize_agent_id(agent_id)
    msg = f'ACP agent "{normalized}" is not allowed by policy.'
    try:
        from openclaw.acp.runtime.errors import AcpRuntimeError
        return AcpRuntimeError("ACP_SESSION_INIT_FAILED", msg)
    except ImportError:
        return RuntimeError(msg)
