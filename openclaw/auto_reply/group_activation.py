"""Group activation mode management.

Mirrors TypeScript openclaw/src/auto-reply/group-activation.ts and
openclaw/src/web/auto-reply/monitor/group-activation.ts.
"""
from __future__ import annotations

import re
from typing import Any, Literal, TypedDict

from openclaw.config.group_policy import resolve_channel_group_require_mention


GroupActivationMode = Literal["mention", "always"]


class ActivationCommandResult(TypedDict):
    """Result of parsing /activation command."""
    hasCommand: bool
    mode: GroupActivationMode | None


def normalize_group_activation(raw: str | bool | None) -> GroupActivationMode | None:
    """Normalize raw activation value to GroupActivationMode.
    
    Mirrors TS normalizeGroupActivation().
    
    Args:
        raw: Raw activation value (string, bool, or None)
        
    Returns:
        Normalized activation mode or None if invalid
    """
    if raw is None:
        return None
    
    if isinstance(raw, bool):
        return "always" if raw else "mention"
    
    value = raw.strip().lower() if isinstance(raw, str) else None
    if value in ("mention", "off"):
        return "mention"
    if value in ("always", "on"):
        return "always"

    return None


def parse_activation_command(raw: str | None) -> ActivationCommandResult:
    """Parse /activation command from text.
    
    Mirrors TS parseActivationCommand().
    
    Args:
        raw: Raw command text
        
    Returns:
        Dict with hasCommand and optional mode
    """
    if not raw:
        return ActivationCommandResult(hasCommand=False, mode=None)
    
    trimmed = raw.strip()
    if not trimmed:
        return ActivationCommandResult(hasCommand=False, mode=None)
    
    # Match /activation [mode [trailing...]]
    match = re.match(r"^/activation(?:\s+([a-zA-Z]+))?(?:\s+.*)?$", trimmed, re.IGNORECASE)
    if not match:
        return ActivationCommandResult(hasCommand=False, mode=None)
    
    mode = normalize_group_activation(match.group(1))
    return ActivationCommandResult(hasCommand=True, mode=mode)


def resolve_group_activation_for(
    cfg: dict[str, Any],
    agent_id: str,
    session_key: str,
    channel: str,
    account_id: str | None = None,
    group_id: str | None = None,
    session_state: dict[str, Any] | None = None,
) -> GroupActivationMode:
    """Resolve group activation mode with session state priority.
    
    Mirrors TS resolveGroupActivationFor() from
    src/web/auto-reply/monitor/group-activation.ts.
    
    Resolution order:
    1. Session state groupActivation
    2. Config requireMention (inverted: False -> "always", True -> "mention")
    3. Default: "mention"
    
    Args:
        cfg: OpenClaw configuration
        agent_id: Agent ID
        session_key: Session key
        channel: Channel ID (e.g., "telegram", "whatsapp")
        account_id: Optional account ID for account-scoped config
        group_id: Optional group ID for group-specific config
        session_state: Optional session state dict
        
    Returns:
        Resolved activation mode
    """
    # Check session state first
    if session_state:
        group_activation = session_state.get("groupActivation")
        normalized = normalize_group_activation(group_activation)
        if normalized:
            return normalized
    
    # Resolve from config requireMention
    require_mention = resolve_channel_group_require_mention(
        cfg=cfg,
        channel=channel,
        group_id=group_id,
        account_id=account_id,
    )
    
    # requireMention=False means always respond (no mention needed)
    # requireMention=True means mention required
    default_activation: GroupActivationMode = "mention" if require_mention else "always"
    
    return default_activation


__all__ = [
    "GroupActivationMode",
    "ActivationCommandResult",
    "normalize_group_activation",
    "parse_activation_command",
    "resolve_group_activation_for",
]
