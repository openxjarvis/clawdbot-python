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

# Tool groups (mirrors TS TOOL_GROUPS / buildCoreToolGroupMap in tool-catalog.ts)
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
    "group:agents": ["agents_list"],          # TS: sectionId="agents"
    "group:media": ["image", "tts"],          # TS: sectionId="media"
    "group:openclaw": [
        # All tools with includeInOpenClawGroup=true in TS tool-catalog.ts
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
        "tts",           # TS includes tts in group:openclaw
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
    
    # Also check alsoAllow in configured policy
    configured_also_allow: list[str] | None = None
    if cfg:
        if hasattr(cfg, "tools"):
            tools_cfg = cfg.tools
            if hasattr(tools_cfg, "subagents"):
                subagents_tools = tools_cfg.subagents
                if hasattr(subagents_tools, "tools"):
                    tools_policy = subagents_tools.tools
                    if isinstance(tools_policy, dict):
                        configured_also_allow = tools_policy.get("alsoAllow") or tools_policy.get("also_allow")
                    elif hasattr(tools_policy, "alsoAllow"):
                        configured_also_allow = tools_policy.alsoAllow
                    elif hasattr(tools_policy, "also_allow"):
                        configured_also_allow = tools_policy.also_allow

    # Effective depth (default to 1)
    effective_depth = depth if isinstance(depth, int) and depth >= 0 else 1

    # Build base deny list
    base_deny = resolve_subagent_deny_list(effective_depth, max_spawn_depth)

    # Tools explicitly allowed override base deny list
    explicit_allow: set[str] = set()
    for source in [configured_allow, configured_also_allow]:
        if isinstance(source, list):
            for t in source:
                explicit_allow.add(normalize_tool_name(t))

    deny = [
        t for t in base_deny
        if normalize_tool_name(t) not in explicit_allow
    ] + (configured_deny if isinstance(configured_deny, list) else [])

    # Merge allow + alsoAllow (mirrors TS mergedAllow)
    ca_is_list = isinstance(configured_allow, list)
    caa_is_list = isinstance(configured_also_allow, list)
    if ca_is_list and caa_is_list:
        allow: list[str] | None = list({
            *configured_allow,
            *configured_also_allow,
        })
    elif ca_is_list:
        allow = configured_allow
    elif caa_is_list:
        allow = configured_also_allow
    else:
        allow = None

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


# Owner-only tools at pi-mono coding-agent layer:
# bash/exec (shell execution) + write-type tools + send_message require owner privilege.
# This mirrors pi-mono/packages/coding-agent pi-tools.policy.ts owner-only defaults.
# NOTE: openclaw-level admin tools (cron, gateway, whatsapp_login) are in
#       openclaw.security.tool_policy.OWNER_ONLY_TOOL_NAMES, used by access-control middleware.
_OWNER_ONLY_TOOLS: frozenset[str] = frozenset({"bash", "exec", "send_message", "write_file", "write"})

# Profile definitions (what tools each profile includes)
_PROFILE_TOOLS: dict[str, list[str] | None] = {
    "permissive": None,   # All tools
    "default": ["read_file", "web_search", "calculator", "send_message", "bash", "write_file"],
    "strict": ["read_file", "web_search", "calculator"],
    "minimal": ["calculator"],
}


def _normalize_provider_key(value: str) -> str:
    return value.strip().lower()


def _pick_sandbox_tool_policy(tools_cfg: Any) -> dict[str, Any] | None:
    """Extract the effective allow/deny/profile/alsoAllow dict from a tools config block."""
    if tools_cfg is None:
        return None
    if isinstance(tools_cfg, dict):
        out: dict[str, Any] = {}
        for key in ("allow", "deny", "profile", "alsoAllow", "also_allow"):
            val = tools_cfg.get(key)
            if val is not None:
                out[key.replace("alsoAllow", "also_allow")] = val
        return out if out else None
    for attr in ("allow", "deny", "profile", "alsoAllow", "also_allow"):
        if hasattr(tools_cfg, attr):
            break
    else:
        return None
    out = {}
    for attr in ("allow", "deny", "profile"):
        val = getattr(tools_cfg, attr, None)
        if val is not None:
            out[attr] = val
    for attr in ("alsoAllow", "also_allow"):
        val = getattr(tools_cfg, attr, None)
        if val is not None:
            out["also_allow"] = val
            break
    return out if out else None


def _resolve_provider_tool_policy(
    by_provider: Any,
    model_provider: str | None,
    model_id: str | None,
) -> dict[str, Any] | None:
    """Resolve provider/model-id compound key from ``byProvider`` config block.

    Mirrors TS ``resolveProviderToolPolicy()``.
    Lookup order: ``provider/modelId`` compound key → bare ``provider`` key.
    """
    if not model_provider or not by_provider:
        return None
    lookup: dict[str, Any] = {}
    if isinstance(by_provider, dict):
        for key, val in by_provider.items():
            normalized = _normalize_provider_key(key)
            if normalized:
                lookup[normalized] = val
    if not lookup:
        return None
    normalized_provider = _normalize_provider_key(model_provider)
    raw_model_id = (model_id or "").strip().lower()
    full_model_id: str | None = None
    if raw_model_id:
        full_model_id = (
            raw_model_id
            if "/" in raw_model_id
            else f"{normalized_provider}/{raw_model_id}"
        )
    candidates = [c for c in [full_model_id, normalized_provider] if c]
    for key in candidates:
        if key in lookup:
            return lookup[key]
    return None


def resolve_effective_tool_policy(
    config: Any = None,
    session_key: str | None = None,
    agent_id: str | None = None,
    model_provider: str | None = None,
    model_id: str | None = None,
) -> dict[str, Any]:
    """Resolve the 4-layer effective tool policy for a session/agent/model combination.

    Layers (mirrors TS ``resolveEffectiveToolPolicy()``):
    1. Global tools policy
    2. Global per-provider policy (keyed by provider/modelId)
    3. Agent tools policy
    4. Agent per-provider policy

    Returns a dict with:
    - ``agent_id``
    - ``global_policy``
    - ``global_provider_policy``
    - ``agent_policy``
    - ``agent_provider_policy``
    - ``profile``
    - ``provider_profile``
    - ``profile_also_allow``
    - ``provider_profile_also_allow``
    """
    from openclaw.routing.session_key import normalize_agent_id, parse_agent_session_key

    effective_agent_id: str | None = None
    if isinstance(agent_id, str) and agent_id.strip():
        effective_agent_id = normalize_agent_id(agent_id)
    elif session_key:
        parsed = parse_agent_session_key(session_key) or {}
        raw = parsed.get("agent_id") if isinstance(parsed, dict) else None
        if raw:
            effective_agent_id = normalize_agent_id(raw)

    agent_tools_cfg: Any = None
    global_tools_cfg: Any = None

    if config is not None:
        # Resolve global tools config
        global_tools_cfg = (
            config.get("tools") if isinstance(config, dict) else getattr(config, "tools", None)
        )
        # Resolve agent tools config
        if effective_agent_id:
            try:
                from openclaw.agents.agent_scope import resolve_agent_config
                agent_cfg = resolve_agent_config(config, effective_agent_id)
                agent_tools_cfg = (
                    agent_cfg.get("tools")
                    if isinstance(agent_cfg, dict)
                    else getattr(agent_cfg, "tools", None)
                ) if agent_cfg else None
            except Exception:
                pass

    global_policy = _pick_sandbox_tool_policy(global_tools_cfg)
    agent_policy = _pick_sandbox_tool_policy(agent_tools_cfg)

    # Per-provider policies
    global_by_provider = (
        global_tools_cfg.get("byProvider")
        if isinstance(global_tools_cfg, dict)
        else getattr(global_tools_cfg, "byProvider", None)
    ) if global_tools_cfg is not None else None
    agent_by_provider = (
        agent_tools_cfg.get("byProvider")
        if isinstance(agent_tools_cfg, dict)
        else getattr(agent_tools_cfg, "byProvider", None)
    ) if agent_tools_cfg is not None else None

    global_provider_raw = _resolve_provider_tool_policy(global_by_provider, model_provider, model_id)
    agent_provider_raw = _resolve_provider_tool_policy(agent_by_provider, model_provider, model_id)
    global_provider_policy = _pick_sandbox_tool_policy(global_provider_raw)
    agent_provider_policy = _pick_sandbox_tool_policy(agent_provider_raw)

    # Profile: agent takes precedence over global
    profile: str | None = None
    for src in [agent_policy, global_policy]:
        if src and src.get("profile"):
            profile = src["profile"]
            break

    provider_profile: str | None = None
    for src in [agent_provider_policy, global_provider_policy]:
        if src and src.get("profile"):
            provider_profile = src["profile"]
            break

    # alsoAllow: agent takes precedence over global
    profile_also_allow: list[str] | None = None
    for src in [agent_policy, global_policy]:
        if src:
            aa = src.get("also_allow")
            if isinstance(aa, list) and aa:
                profile_also_allow = aa
                break

    provider_profile_also_allow: list[str] | None = None
    for src in [agent_provider_policy, global_provider_policy]:
        if src:
            aa = src.get("also_allow")
            if isinstance(aa, list) and aa:
                provider_profile_also_allow = aa
                break

    return {
        "agent_id": effective_agent_id,
        "global_policy": global_policy,
        "global_provider_policy": global_provider_policy,
        "agent_policy": agent_policy,
        "agent_provider_policy": agent_provider_policy,
        "profile": profile,
        "provider_profile": provider_profile,
        "profile_also_allow": profile_also_allow,
        "provider_profile_also_allow": provider_profile_also_allow,
    }


def _resolve_group_context_from_session_key(session_key: str | None) -> dict[str, str | None]:
    """Extract channel and groupId from a session key.

    Mirrors TS ``resolveGroupContextFromSessionKey()``.
    """
    raw = (session_key or "").strip()
    if not raw:
        return {"channel": None, "group_id": None}
    parts = [p for p in raw.split(":") if p]
    body = parts[2:] if len(parts) >= 2 and parts[0] == "agent" else parts
    if body and body[0] == "subagent":
        body = body[1:]
    if len(body) < 3:
        return {"channel": None, "group_id": None}
    channel = body[0].strip().lower()
    kind = body[1]
    if kind not in ("group", "channel"):
        return {"channel": None, "group_id": None}
    group_id = ":".join(body[2:]).strip()
    return {"channel": channel, "group_id": group_id or None}


def resolve_group_tool_policy(
    config: Any = None,
    session_key: str | None = None,
    spawned_by: str | None = None,
    message_provider: str | None = None,
    group_id: str | None = None,
    group_channel: str | None = None,
    group_space: str | None = None,
    account_id: str | None = None,
    sender_id: str | None = None,
    sender_name: str | None = None,
    sender_username: str | None = None,
    sender_e164: str | None = None,
) -> dict[str, Any] | None:
    """Resolve tool policy for a group/channel context.

    Mirrors TS ``resolveGroupToolPolicy()``.
    Queries the channel dock's ``resolveToolPolicy`` hook if available;
    falls back to ``None`` (no restriction) when the hook is absent.
    """
    if config is None:
        return None

    session_ctx = _resolve_group_context_from_session_key(session_key)
    spawned_ctx = _resolve_group_context_from_session_key(spawned_by)

    effective_group_id = group_id or session_ctx.get("group_id") or spawned_ctx.get("group_id")
    if not effective_group_id:
        return None

    channel_raw = message_provider or session_ctx.get("channel") or spawned_ctx.get("channel")
    if not channel_raw:
        return None
    channel = channel_raw.strip().lower()

    # Try to resolve via channel dock
    try:
        from openclaw.channels.dock import get_channel_dock
        dock = get_channel_dock(channel)
        groups = getattr(dock, "groups", None) if dock else None
        resolve_fn = getattr(groups, "resolve_tool_policy", None) if groups else None
        if callable(resolve_fn):
            policy = resolve_fn(
                cfg=config,
                group_id=effective_group_id,
                group_channel=group_channel,
                group_space=group_space,
                account_id=account_id,
                sender_id=sender_id,
                sender_name=sender_name,
                sender_username=sender_username,
                sender_e164=sender_e164,
            )
            return _pick_sandbox_tool_policy(policy)
    except Exception:
        pass

    return None


class ToolPolicy:
    """Structured tool policy with profile, allow/deny/alsoAllow lists, per-provider
    and per-sender overrides (mirrors TS ToolPolicy + GroupToolPolicyBySenderConfig)."""

    def __init__(
        self,
        profile: str = "default",
        allow: list[str] | None = None,
        deny: list[str] | None = None,
        also_allow: list[str] | None = None,
        by_provider: dict[str, "ToolPolicy"] | None = None,
        by_sender: dict[str, "ToolPolicy"] | None = None,
    ) -> None:
        self.profile = profile
        self.allow = allow
        self.deny = deny
        self.also_allow = also_allow  # alsoAllow: extends profile without replacing allow
        self.by_provider = by_provider or {}
        self.by_sender = by_sender or {}  # sender_id -> ToolPolicy override


def resolve_sender_tool_policy(
    base_policy: ToolPolicy,
    sender_id: str | None,
) -> ToolPolicy:
    """
    Resolve per-sender tool policy override.

    Mirrors TS GroupToolPolicyBySenderConfig lookup in resolveGroupToolPolicy():
    - If sender_id matches a key in base_policy.by_sender, returns that ToolPolicy.
    - Otherwise returns the base_policy unchanged.

    Args:
        base_policy: The resolved base ToolPolicy (global or group-level).
        sender_id: Sender identifier (e.g. phone number, user ID, chat ID).

    Returns:
        Effective ToolPolicy for this sender.
    """
    if not sender_id or not base_policy.by_sender:
        return base_policy
    override = base_policy.by_sender.get(sender_id)
    if override is None:
        # Try case-insensitive lookup
        sender_lower = sender_id.strip().lower()
        override = next(
            (v for k, v in base_policy.by_sender.items() if k.strip().lower() == sender_lower),
            None,
        )
    return override if override is not None else base_policy


class ToolPolicyResolver:
    """Resolves which tools are available given a policy, provider, and ownership."""

    def __init__(self, core_tools: list[str]) -> None:
        self.core_tools = list(core_tools)

    def resolve(
        self,
        policy: ToolPolicy,
        provider: str | None = None,
        sender_is_owner: bool = False,
        sender_id: str | None = None,
    ) -> list[str]:
        """Return the list of tool names allowed by the policy."""
        # Per-provider override
        effective_policy = policy
        if provider and provider in policy.by_provider:
            effective_policy = policy.by_provider[provider]

        # Per-sender override (F4: GroupToolPolicyBySenderConfig)
        if sender_id:
            effective_policy = resolve_sender_tool_policy(effective_policy, sender_id)

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
