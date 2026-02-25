"""Tool policy management

Fully aligned with TypeScript openclaw/src/agents/tool-policy.ts
and openclaw/src/agents/pi-tools.policy.ts

This module handles:
- Tool name normalization and aliases
- Tool groups expansion
- Tool profiles (minimal, coding, messaging, full)
- Subagent tool policies (depth-based deny lists)
- Policy matching and filtering
"""
from __future__ import annotations

import fnmatch
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Tool name aliases (mirrors TS TOOL_NAME_ALIASES)
TOOL_NAME_ALIASES: dict[str, str] = {
    "bash": "exec",
    "apply-patch": "apply_patch",
}

# Tool groups (mirrors TS TOOL_GROUPS)
TOOL_GROUPS: dict[str, list[str]] = {
    "group:memory": ["memory_search", "memory_get"],
    "group:web": ["web_search", "web_fetch"],
    "group:fs": ["read", "write", "edit", "apply_patch"],
    "group:runtime": ["exec", "process"],
    "group:sessions": [
        "sessions_list",
        "sessions_history",
        "sessions_send",
        "sessions_spawn",
        "subagents",
        "session_status",
    ],
    "group:ui": ["browser", "canvas"],
    "group:automation": ["cron", "gateway"],
    "group:messaging": ["message"],
    "group:nodes": ["nodes"],
    "group:openclaw": [
        "browser",
        "canvas",
        "nodes",
        "cron",
        "message",
        "gateway",
        "agents_list",
        "sessions_list",
        "sessions_history",
        "sessions_send",
        "sessions_spawn",
        "subagents",
        "session_status",
        "memory_search",
        "memory_get",
        "web_search",
        "web_fetch",
        "image",
    ],
}

# Tool profiles (mirrors TS TOOL_PROFILES)
TOOL_PROFILES: dict[str, dict[str, list[str]]] = {
    "minimal": {
        "allow": ["session_status"],
    },
    "coding": {
        "allow": ["group:fs", "group:runtime", "group:sessions", "group:memory", "image"],
    },
    "messaging": {
        "allow": [
            "group:messaging",
            "sessions_list",
            "sessions_history",
            "sessions_send",
            "session_status",
        ],
    },
    "full": {},
}

# Subagent tool deny lists (mirrors TS pi-tools.policy.ts lines 44-64)
# Tools always denied for sub-agents regardless of depth
SUBAGENT_TOOL_DENY_ALWAYS = [
    "gateway",           # System admin - dangerous from subagent
    "agents_list",       # System admin
    "whatsapp_login",    # Interactive setup - not a task
    "session_status",    # Status - main agent coordinates
    "cron",              # Scheduling - main agent coordinates
    "memory_search",     # Memory - pass relevant info in spawn prompt instead
    "memory_get",        # Memory - pass relevant info in spawn prompt instead
    "sessions_send",     # Direct session sends - subagents communicate through announce chain
]

# Additional tools denied for leaf sub-agents (depth >= maxSpawnDepth)
SUBAGENT_TOOL_DENY_LEAF = [
    "sessions_list",
    "sessions_history",
    "sessions_spawn",
]


def normalize_tool_name(name: str) -> str:
    """Normalize tool name (mirrors TS normalizeToolName lines 84-87)"""
    normalized = name.strip().lower()
    return TOOL_NAME_ALIASES.get(normalized, normalized)


def normalize_tool_list(tool_list: list[str] | None) -> list[str]:
    """Normalize list of tool names (mirrors TS normalizeToolList lines 114-119)"""
    if not tool_list:
        return []
    return [normalize_tool_name(name) for name in tool_list if name]


def expand_tool_groups(tool_list: list[str] | None) -> list[str]:
    """
    Expand tool groups to individual tool names.
    
    Mirrors TS expandToolGroups() lines 137-149
    
    Example:
        ["group:fs", "read"] -> ["read", "write", "edit", "apply_patch", "read"]
    """
    normalized = normalize_tool_list(tool_list)
    expanded: list[str] = []
    
    for value in normalized:
        group = TOOL_GROUPS.get(value)
        if group:
            expanded.extend(group)
        else:
            expanded.append(value)
    
    return list(set(expanded))


def resolve_tool_profile_policy(profile: str | None) -> dict[str, Any] | None:
    """
    Resolve tool policy from profile name.
    
    Mirrors TS resolveToolProfilePolicy() lines 278-293
    """
    if not profile:
        return None
    
    resolved = TOOL_PROFILES.get(profile)
    if not resolved:
        return None
    
    if not resolved.get("allow") and not resolved.get("deny"):
        return None
    
    return {
        "allow": list(resolved["allow"]) if "allow" in resolved else None,
        "deny": list(resolved["deny"]) if "deny" in resolved else None,
    }


def resolve_subagent_deny_list(depth: int, max_spawn_depth: int) -> list[str]:
    """
    Resolve deny list for subagent based on depth.
    
    Mirrors TS resolveSubagentDenyList() from pi-tools.policy.ts lines 74-82
    
    Rules:
    - Depth >= maxSpawnDepth (leaf): deny always + leaf tools
    - Depth < maxSpawnDepth (orchestrator): deny only always tools
    """
    is_leaf = depth >= max(1, int(max_spawn_depth))
    
    if is_leaf:
        return [*SUBAGENT_TOOL_DENY_ALWAYS, *SUBAGENT_TOOL_DENY_LEAF]
    
    # Orchestrator: only deny always-denied tools
    return list(SUBAGENT_TOOL_DENY_ALWAYS)


def resolve_subagent_tool_policy(
    cfg: Any = None,
    depth: int | None = None,
) -> dict[str, Any]:
    """
    Resolve tool policy for subagent based on depth and config.
    
    Fully aligned with TS resolveSubagentToolPolicy() from pi-tools.policy.ts lines 84-92
    
    Args:
        cfg: Configuration object
        depth: Subagent depth (1 = first level subagent, 2 = sub-subagent, etc.)
    
    Returns:
        Policy dict with "allow" and "deny" lists
    """
    # Get config values
    max_spawn_depth = 1
    configured_allow = None
    configured_deny = []
    
    if cfg:
        # Get maxSpawnDepth
        if hasattr(cfg, "agents") and hasattr(cfg.agents, "defaults"):
            defaults = cfg.agents.defaults
            if hasattr(defaults, "subagents"):
                subagents_cfg = defaults.subagents
                if isinstance(subagents_cfg, dict):
                    max_spawn_depth = subagents_cfg.get("maxSpawnDepth", 1)
                elif hasattr(subagents_cfg, "maxSpawnDepth"):
                    max_spawn_depth = subagents_cfg.maxSpawnDepth or 1
        
        # Get configured tools policy
        if hasattr(cfg, "tools"):
            tools_cfg = cfg.tools
            if hasattr(tools_cfg, "subagents"):
                subagents_tools = tools_cfg.subagents
                if hasattr(subagents_tools, "tools"):
                    tools_policy = subagents_tools.tools
                    if isinstance(tools_policy, dict):
                        configured_allow = tools_policy.get("allow")
                        configured_deny = tools_policy.get("deny", [])
                    elif hasattr(tools_policy, "deny"):
                        configured_deny = tools_policy.deny or []
                    if hasattr(tools_policy, "allow"):
                        configured_allow = tools_policy.allow
    
    # Effective depth (default to 1)
    effective_depth = depth if isinstance(depth, int) and depth >= 0 else 1
    
    # Build base deny list
    base_deny = resolve_subagent_deny_list(effective_depth, max_spawn_depth)
    
    # Merge with configured deny list
    deny = [*base_deny, *(configured_deny if isinstance(configured_deny, list) else [])]
    
    # Allow list (if configured)
    allow = configured_allow if isinstance(configured_allow, list) else None
    
    return {
        "allow": allow,
        "deny": deny,
    }


def make_tool_policy_matcher(policy: dict[str, Any]) -> callable:
    """
    Create matcher function for tool policy.
    
    Mirrors TS makeToolPolicyMatcher() from pi-tools.policy.ts
    
    Args:
        policy: Policy dict with "allow" and "deny" lists
    
    Returns:
        Function that takes tool name and returns True if allowed
    """
    allow_list = policy.get("allow")
    deny_list = policy.get("deny")
    
    # Normalize and expand
    allow_expanded = expand_tool_groups(allow_list) if allow_list else None
    deny_expanded = expand_tool_groups(deny_list) if deny_list else []
    
    def matcher(tool_name: str) -> bool:
        """Check if tool is allowed by policy"""
        normalized_name = normalize_tool_name(tool_name)
        
        # Check deny list first (takes precedence)
        if deny_expanded:
            for pattern in deny_expanded:
                if pattern == "*":
                    return False
                if fnmatch.fnmatch(normalized_name, pattern):
                    return False
                if normalized_name == pattern:
                    return False
        
        # If allow list exists, tool must match
        if allow_expanded is not None:
            if not allow_expanded:  # Empty allow list = deny all
                return False
            
            for pattern in allow_expanded:
                if pattern == "*":
                    return True
                if fnmatch.fnmatch(normalized_name, pattern):
                    return True
                if normalized_name == pattern:
                    return True
                # Special case: exec allows apply_patch
                if pattern == "exec" and normalized_name == "apply_patch":
                    return True
            
            return False
        
        # No allow list = allow all (unless denied)
        return True
    
    return matcher


def is_tool_allowed_by_policy_name(name: str, policy: dict[str, Any] | None) -> bool:
    """
    Check if tool is allowed by policy.
    
    Mirrors TS isToolAllowedByPolicyName() from pi-tools.policy.ts lines 94-99
    """
    if not policy:
        return True
    
    return make_tool_policy_matcher(policy)(name)


def is_tool_allowed_by_policies(
    name: str,
    policies: list[dict[str, Any] | None],
) -> bool:
    """
    Check if tool is allowed by all policies.
    
    Mirrors TS isToolAllowedByPolicies() from pi-tools.policy.ts
    """
    for policy in policies:
        if policy and not is_tool_allowed_by_policy_name(name, policy):
            return False
    
    return True


def filter_tools_by_policy(
    tools: list[Any],
    policy: dict[str, Any] | None,
) -> list[Any]:
    """
    Filter tools by policy.
    
    Mirrors TS filterToolsByPolicy() from pi-tools.policy.ts
    """
    if not policy:
        return tools
    
    matcher = make_tool_policy_matcher(policy)
    return [tool for tool in tools if matcher(tool.name)]


# Owner-only tools that non-owners should not access
_OWNER_ONLY_TOOLS: frozenset[str] = frozenset({"bash", "exec", "send_message", "write_file", "write"})

# Profile definitions (what tools each profile includes)
_PROFILE_TOOLS: dict[str, list[str] | None] = {
    "permissive": None,   # All tools
    "default": ["read_file", "web_search", "calculator", "send_message", "bash", "write_file"],
    "strict": ["read_file", "web_search", "calculator"],
    "minimal": ["calculator"],
}


class ToolPolicy:
    """Structured tool policy with profile, allow/deny lists and per-provider overrides."""

    def __init__(
        self,
        profile: str = "default",
        allow: list[str] | None = None,
        deny: list[str] | None = None,
        by_provider: dict[str, "ToolPolicy"] | None = None,
    ) -> None:
        self.profile = profile
        self.allow = allow
        self.deny = deny
        self.by_provider = by_provider or {}


class ToolPolicyResolver:
    """Resolves which tools are available given a policy, provider, and ownership."""

    def __init__(self, core_tools: list[str]) -> None:
        self.core_tools = list(core_tools)

    def resolve(
        self,
        policy: ToolPolicy,
        provider: str | None = None,
        sender_is_owner: bool = False,
    ) -> list[str]:
        """Return the list of tool names allowed by the policy."""
        # Per-provider override
        effective_policy = policy
        if provider and provider in policy.by_provider:
            effective_policy = policy.by_provider[provider]

        # Profile filter
        profile_tools = _PROFILE_TOOLS.get(effective_policy.profile)
        if profile_tools is None:
            # permissive: all core tools
            candidate = list(self.core_tools)
        else:
            candidate = [t for t in self.core_tools if t in profile_tools]

        # Apply allowlist (intersection)
        if effective_policy.allow is not None:
            allow_set = set(effective_policy.allow)
            candidate = [t for t in candidate if t in allow_set]

        # Apply denylist (subtraction)
        if effective_policy.deny:
            deny_set = set(effective_policy.deny)
            candidate = [t for t in candidate if t not in deny_set]

        # Owner-only filtering
        if not sender_is_owner:
            candidate = [t for t in candidate if t not in _OWNER_ONLY_TOOLS]

        return candidate
