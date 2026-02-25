"""Telegram inline button scope validation

Validates inline button usage based on configured scope (off/dm/group/all/allowlist).
Supports per-account overrides via capabilities.inlineButtons.
"""
from __future__ import annotations

import logging
from typing import Any, Literal

logger = logging.getLogger(__name__)

InlineButtonsScope = Literal["off", "dm", "group", "all", "allowlist"]

DEFAULT_INLINE_BUTTONS_SCOPE: InlineButtonsScope = "allowlist"


def normalize_inline_buttons_scope(value: Any) -> InlineButtonsScope | None:
    """
    Normalize inline buttons scope value.
    
    Args:
        value: Raw scope value
    
    Returns:
        Normalized scope or None if invalid
    """
    if not isinstance(value, str):
        return None
    
    trimmed = value.strip().lower()
    
    if trimmed in ("off", "dm", "group", "all", "allowlist"):
        return trimmed
    
    return None


def resolve_inline_buttons_scope_from_capabilities(
    capabilities: Any,
) -> InlineButtonsScope:
    """
    Resolve inline buttons scope from capabilities config.
    
    Args:
        capabilities: Capabilities configuration
    
    Returns:
        Resolved scope
    """
    if not capabilities:
        return DEFAULT_INLINE_BUTTONS_SCOPE
    
    # Array format: check if "inlineButtons" is in list
    if isinstance(capabilities, list):
        enabled = any(
            str(entry).strip().lower() == "inlinebuttons"
            for entry in capabilities
        )
        return "all" if enabled else "off"
    
    # Object format: check inlineButtons key
    if isinstance(capabilities, dict):
        inline_buttons = capabilities.get("inlineButtons")
        return normalize_inline_buttons_scope(inline_buttons) or DEFAULT_INLINE_BUTTONS_SCOPE
    
    return DEFAULT_INLINE_BUTTONS_SCOPE


def resolve_telegram_inline_buttons_scope(
    config: dict[str, Any],
    account_id: str | None = None,
) -> InlineButtonsScope:
    """
    Resolve inline buttons scope for an account.
    
    Args:
        config: Full configuration
        account_id: Account ID
    
    Returns:
        Resolved scope
    """
    telegram_config = config.get("channels", {}).get("telegram", {})
    
    # Check account-specific config
    if account_id:
        accounts = telegram_config.get("accounts", {})
        account_config = accounts.get(account_id, {})
        capabilities = account_config.get("capabilities")
        if capabilities:
            return resolve_inline_buttons_scope_from_capabilities(capabilities)
    
    # Fall back to global capabilities
    capabilities = telegram_config.get("capabilities")
    return resolve_inline_buttons_scope_from_capabilities(capabilities)


def is_telegram_inline_buttons_enabled(
    config: dict[str, Any],
    account_id: str | None = None,
) -> bool:
    """
    Check if inline buttons are enabled for any account.
    
    Args:
        config: Full configuration
        account_id: Optional account ID
    
    Returns:
        True if enabled
    """
    if account_id:
        return resolve_telegram_inline_buttons_scope(config, account_id) != "off"
    
    # Check all accounts
    telegram_config = config.get("channels", {}).get("telegram", {})
    accounts = telegram_config.get("accounts", {})
    
    for acc_id in accounts.keys():
        if resolve_telegram_inline_buttons_scope(config, acc_id) != "off":
            return True
    
    # Check global config
    return resolve_telegram_inline_buttons_scope(config, None) != "off"


def resolve_telegram_target_chat_type(target: str) -> Literal["direct", "group", "unknown"]:
    """
    Resolve chat type from target string.
    
    Args:
        target: Target chat ID or username
    
    Returns:
        Chat type: direct (positive ID), group (negative ID), or unknown
    """
    target = target.strip()
    
    if not target:
        return "unknown"
    
    # Strip prefixes
    while True:
        if target.startswith(("telegram:", "tg:")):
            target = target.split(":", 1)[1].strip()
            continue
        if target.startswith("group:"):
            target = target.split(":", 1)[1].strip()
            continue
        break
    
    # Check if numeric
    if target.lstrip("-").isdigit():
        return "group" if target.startswith("-") else "direct"
    
    return "unknown"


def validate_inline_buttons_for_target(
    scope: InlineButtonsScope,
    chat_type: Literal["direct", "group", "unknown"],
    allow_from: list[str] | None = None,
    sender_id: str | None = None,
) -> bool:
    """
    Validate if inline buttons are allowed for a target.
    
    Args:
        scope: Inline buttons scope
        chat_type: Target chat type
        allow_from: AllowFrom list (for allowlist mode)
        sender_id: Sender ID (for allowlist mode)
    
    Returns:
        True if buttons are allowed
    """
    if scope == "off":
        return False
    
    if scope == "all":
        return True
    
    if scope == "dm":
        return chat_type == "direct"
    
    if scope == "group":
        return chat_type == "group"
    
    if scope == "allowlist":
        # Check allowFrom list
        if allow_from and sender_id:
            return sender_id in allow_from or "*" in allow_from
        return False
    
    return False
