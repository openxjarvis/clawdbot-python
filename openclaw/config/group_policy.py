"""Group policy resolution for channels.

Mirrors TypeScript openclaw/src/config/group-policy.ts.
"""
from __future__ import annotations

from typing import Any, TypedDict

from openclaw.routing.session_key import normalize_account_id


class ChannelGroupConfig(TypedDict, total=False):
    """Channel group configuration."""
    requireMention: bool
    tools: dict[str, Any]
    toolsBySender: dict[str, dict[str, Any]]


class ChannelGroupPolicy(TypedDict, total=False):
    """Channel group policy resolution result."""
    allowlistEnabled: bool
    allowed: bool
    requireMention: bool | None
    tools: dict[str, Any] | None
    groupConfig: ChannelGroupConfig | None
    defaultConfig: ChannelGroupConfig | None


class GroupToolPolicySender(TypedDict, total=False):
    """Sender identification for tool policy resolution."""
    senderId: str | None
    senderName: str | None
    senderUsername: str | None
    senderE164: str | None


def normalize_sender_key(value: str | None) -> str:
    """Normalize sender key for matching.

    Handles phone numbers (E.164), Telegram usernames, and generic IDs.
    Mirrors TS normalizeSenderKey().
    """
    if value is None:
        return ""
    trimmed = str(value).strip()
    if not trimmed:
        return ""
    # Strip leading @
    without_at = trimmed[1:] if trimmed.startswith("@") else trimmed
    # Phone number normalization: remove formatting characters, add + prefix
    if without_at.replace("-", "").replace(" ", "").replace("(", "").replace(")", "").isdigit():
        digits = "".join(c for c in without_at if c.isdigit())
        return f"+{digits}"
    if without_at.startswith("+"):
        # Keep + and normalize formatting
        digits = "".join(c for c in without_at[1:] if c.isdigit())
        return f"+{digits}" if digits else without_at.lower()
    return without_at.lower()


def _normalize_sender_key(value: str) -> str:
    """Internal alias for normalize_sender_key (legacy private name)."""
    return normalize_sender_key(value)


def resolve_tools_by_sender(
    tools_by_sender: dict[str, dict[str, Any]] | None,
    sender_id: str | None = None,
    sender_name: str | None = None,
    sender_username: str | None = None,
    sender_e164: str | None = None,
) -> dict[str, Any] | None:
    """Resolve per-sender tool policy.
    
    Mirrors TS resolveToolsBySender().
    """
    if not tools_by_sender:
        return None
    
    entries = list(tools_by_sender.items())
    if not entries:
        return None
    
    normalized: dict[str, dict[str, Any]] = {}
    wildcard: dict[str, Any] | None = None
    
    for raw_key, policy in entries:
        if not policy:
            continue
        key = _normalize_sender_key(raw_key)
        if not key:
            continue
        if key == "*":
            wildcard = policy
            continue
        if key not in normalized:
            normalized[key] = policy
    
    candidates: list[str] = []
    
    def push_candidate(value: str | None) -> None:
        trimmed = value.strip() if value else None
        if trimmed:
            candidates.append(trimmed)
    
    push_candidate(sender_id)
    push_candidate(sender_e164)
    push_candidate(sender_username)
    push_candidate(sender_name)
    
    for candidate in candidates:
        key = _normalize_sender_key(candidate)
        if not key:
            continue
        match = normalized.get(key)
        if match:
            return match
    
    return wildcard


def _resolve_channel_group_config(
    groups: dict[str, ChannelGroupConfig] | None,
    group_id: str,
    case_insensitive: bool = False,
) -> ChannelGroupConfig | None:
    """Resolve group-specific config from groups dict.
    
    Mirrors TS resolveChannelGroupConfig().
    """
    if not groups:
        return None
    
    direct = groups.get(group_id)
    if direct:
        return direct
    
    if not case_insensitive:
        return None
    
    target = group_id.lower()
    matched_key = next(
        (key for key in groups.keys() if key != "*" and key.lower() == target),
        None,
    )
    if not matched_key:
        return None
    
    return groups[matched_key]


def _resolve_channel_groups(
    cfg: dict[str, Any],
    channel: str,
    account_id: str | None = None,
) -> dict[str, ChannelGroupConfig] | None:
    """Resolve channel groups config with account scoping.
    
    Mirrors TS resolveChannelGroups().
    """
    normalized_account_id = normalize_account_id(account_id)
    channel_config = cfg.get("channels", {}).get(channel)
    
    if not channel_config:
        return None
    
    accounts = channel_config.get("accounts", {})
    account_groups = accounts.get(normalized_account_id, {}).get("groups")
    
    if not account_groups:
        # Try case-insensitive account lookup
        matched_account_key = next(
            (
                key
                for key in accounts.keys()
                if key.lower() == normalized_account_id.lower()
            ),
            None,
        )
        if matched_account_key:
            account_groups = accounts[matched_account_key].get("groups")
    
    return account_groups or channel_config.get("groups")


def resolve_channel_group_policy(
    cfg: dict[str, Any],
    channel: str,
    group_id: str | None = None,
    account_id: str | None = None,
    group_id_case_insensitive: bool = False,
) -> ChannelGroupPolicy:
    """Resolve channel group policy with hierarchical config resolution.
    
    Mirrors TS resolveChannelGroupPolicy().
    
    Resolution order:
    1. Group-specific config (channels.<channel>.groups.<groupId>)
    2. Wildcard config (channels.<channel>.groups.*)
    3. Channel default (no groups configured)
    
    Account-scoped groups take precedence over channel-level groups.
    """
    groups = _resolve_channel_groups(cfg, channel, account_id)
    allowlist_enabled = bool(groups and len(groups) > 0)
    
    normalized_id = group_id.strip() if group_id else None
    group_config = (
        _resolve_channel_group_config(groups, normalized_id, group_id_case_insensitive)
        if normalized_id
        else None
    )
    
    default_config = groups.get("*") if groups else None
    allow_all = allowlist_enabled and bool(groups and "*" in groups)
    allowed = not allowlist_enabled or allow_all or bool(group_config)
    
    # Resolve effective requireMention and tools from group/default config
    effective_config = group_config or default_config
    require_mention = effective_config.get("requireMention") if effective_config else None
    tools = effective_config.get("tools") if effective_config else None

    return ChannelGroupPolicy(
        allowlistEnabled=allowlist_enabled,
        allowed=allowed,
        requireMention=require_mention,
        tools=tools,
        groupConfig=group_config,
        defaultConfig=default_config,
    )


def resolve_channel_group_require_mention(
    cfg: dict[str, Any],
    channel: str,
    group_id: str | None = None,
    account_id: str | None = None,
    group_id_case_insensitive: bool = False,
    require_mention_override: bool | None = None,
    override_order: str = "after-config",
) -> bool:
    """Resolve requireMention setting with hierarchical resolution.
    
    Mirrors TS resolveChannelGroupRequireMention().
    
    Resolution order (when override_order="after-config"):
    1. Group-specific requireMention
    2. Wildcard requireMention
    3. require_mention_override parameter
    4. Default (True)
    
    When override_order="before-config", parameter takes precedence.
    """
    policy = resolve_channel_group_policy(
        cfg, channel, group_id, account_id, group_id_case_insensitive
    )
    
    group_config = policy["groupConfig"]
    default_config = policy["defaultConfig"]
    
    config_mention: bool | None = None
    if group_config and "requireMention" in group_config:
        config_mention = group_config["requireMention"]
    elif default_config and "requireMention" in default_config:
        config_mention = default_config["requireMention"]
    
    if override_order == "before-config" and require_mention_override is not None:
        return require_mention_override
    
    if config_mention is not None:
        return config_mention
    
    if override_order != "before-config" and require_mention_override is not None:
        return require_mention_override
    
    return True


def resolve_channel_group_tools_policy(
    cfg: dict[str, Any],
    channel: str,
    group_id: str | None = None,
    account_id: str | None = None,
    group_id_case_insensitive: bool = False,
    sender_id: str | None = None,
    sender_name: str | None = None,
    sender_username: str | None = None,
    sender_e164: str | None = None,
) -> dict[str, Any] | None:
    """Resolve per-sender tool policy for a group.
    
    Mirrors TS resolveChannelGroupToolsPolicy().
    
    Resolution order:
    1. Group-specific sender policy (toolsBySender)
    2. Group-specific tools policy
    3. Wildcard sender policy (toolsBySender)
    4. Wildcard tools policy
    5. None (no policy)
    """
    policy = resolve_channel_group_policy(
        cfg, channel, group_id, account_id, group_id_case_insensitive
    )
    
    group_config = policy["groupConfig"]
    default_config = policy["defaultConfig"]
    
    # Check group-specific sender policy
    if group_config:
        group_sender_policy = resolve_tools_by_sender(
            group_config.get("toolsBySender"),
            sender_id,
            sender_name,
            sender_username,
            sender_e164,
        )
        if group_sender_policy:
            return group_sender_policy
        
        if "tools" in group_config:
            return group_config["tools"]
    
    # Check wildcard sender policy
    if default_config:
        default_sender_policy = resolve_tools_by_sender(
            default_config.get("toolsBySender"),
            sender_id,
            sender_name,
            sender_username,
            sender_e164,
        )
        if default_sender_policy:
            return default_sender_policy
        
        if "tools" in default_config:
            return default_config["tools"]
    
    return None


__all__ = [
    "ChannelGroupConfig",
    "ChannelGroupPolicy",
    "GroupToolPolicySender",
    "normalize_sender_key",
    "resolve_channel_group_policy",
    "resolve_channel_group_require_mention",
    "resolve_channel_group_tools_policy",
    "resolve_tools_by_sender",
]
