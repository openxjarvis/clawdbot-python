"""Telegram group migration handler

Handles chat ID changes when a Telegram group is upgraded to a supergroup.
Updates group configuration to use the new chat ID.
"""
from __future__ import annotations

import logging
from typing import Any, Literal

logger = logging.getLogger(__name__)

MigrationScope = Literal["account", "global"]


def migrate_telegram_groups_in_place(
    groups: dict[str, Any] | None,
    old_chat_id: str,
    new_chat_id: str,
) -> dict[str, bool]:
    """
    Migrate group config from old chat ID to new chat ID.
    
    Updates the groups dict in place.
    
    Args:
        groups: Groups configuration dict
        old_chat_id: Old chat ID (before migration)
        new_chat_id: New chat ID (after migration)
    
    Returns:
        Dict with migrated and skipped_existing flags
    """
    if not groups:
        return {"migrated": False, "skipped_existing": False}
    
    if old_chat_id == new_chat_id:
        return {"migrated": False, "skipped_existing": False}
    
    if old_chat_id not in groups:
        return {"migrated": False, "skipped_existing": False}
    
    if new_chat_id in groups:
        return {"migrated": False, "skipped_existing": True}
    
    # Migrate config
    groups[new_chat_id] = groups[old_chat_id]
    del groups[old_chat_id]
    
    return {"migrated": True, "skipped_existing": False}


def resolve_account_groups(
    config: dict[str, Any],
    account_id: str | None,
) -> dict[str, Any] | None:
    """
    Resolve groups config for a specific account.
    
    Args:
        config: Full configuration
        account_id: Account ID
    
    Returns:
        Groups dict or None
    """
    if not account_id:
        return None
    
    telegram_config = config.get("channels", {}).get("telegram", {})
    accounts = telegram_config.get("accounts", {})
    
    if not isinstance(accounts, dict):
        return None
    
    # Try exact match
    account_config = accounts.get(account_id, {})
    if account_config and "groups" in account_config:
        return account_config.get("groups")
    
    # Try case-insensitive match
    account_id_lower = account_id.lower()
    for key, acc_cfg in accounts.items():
        if key.lower() == account_id_lower:
            return acc_cfg.get("groups")
    
    return None


def migrate_telegram_group_config(
    config: dict[str, Any],
    account_id: str | None,
    old_chat_id: str,
    new_chat_id: str,
) -> dict[str, Any]:
    """
    Migrate group configuration across all scopes.
    
    Checks both account-specific and global groups configs.
    
    Args:
        config: Full configuration
        account_id: Account ID
        old_chat_id: Old chat ID
        new_chat_id: New chat ID
    
    Returns:
        Dict with:
            - migrated: Whether any migration occurred
            - skipped_existing: Whether new chat ID already exists
            - scopes: List of scopes where migration occurred
    """
    scopes: list[MigrationScope] = []
    migrated = False
    skipped_existing = False
    
    # Account-level groups
    account_groups = resolve_account_groups(config, account_id)
    if account_groups:
        result = migrate_telegram_groups_in_place(
            account_groups, old_chat_id, new_chat_id
        )
        if result["migrated"]:
            migrated = True
            scopes.append("account")
        if result["skipped_existing"]:
            skipped_existing = True
    
    # Global-level groups
    telegram_config = config.get("channels", {}).get("telegram", {})
    global_groups = telegram_config.get("groups")
    if global_groups:
        result = migrate_telegram_groups_in_place(
            global_groups, old_chat_id, new_chat_id
        )
        if result["migrated"]:
            migrated = True
            scopes.append("global")
        if result["skipped_existing"]:
            skipped_existing = True
    
    return {
        "migrated": migrated,
        "skipped_existing": skipped_existing,
        "scopes": scopes,
    }
