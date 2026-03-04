"""Discord multi-account resolution — mirrors src/discord/accounts.ts"""
from __future__ import annotations

import logging
from typing import Any

from .config import ResolvedDiscordAccount, parse_discord_config

logger = logging.getLogger(__name__)

# Discord snowflake ID length (17-19 digits)
_MIN_SNOWFLAKE_LEN = 17
_MAX_SNOWFLAKE_LEN = 20


def resolve_discord_accounts(config: dict[str, Any]) -> list[ResolvedDiscordAccount]:
    """Parse and validate all enabled Discord accounts from config."""
    accounts = parse_discord_config(config)
    valid: list[ResolvedDiscordAccount] = []
    for acct in accounts:
        if not acct.token:
            logger.warning("[discord] Account '%s' has no token — skipping", acct.account_id)
            continue
        valid.append(acct)
    return valid


def get_default_account(accounts: list[ResolvedDiscordAccount]) -> ResolvedDiscordAccount | None:
    """Return the first enabled account (list is already filtered)."""
    return accounts[0] if accounts else None


def normalize_snowflake(raw: str) -> str:
    """
    Strip common prefixes and return the bare numeric Discord snowflake.
    Mirrors allowlist prefix stripping in allow-list.ts:
      discord:  user:  pk:  role:
    """
    for prefix in ("discord:", "user:", "pk:", "role:", "channel:"):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
    return raw.strip()


def is_valid_snowflake(value: str) -> bool:
    """Return True if value looks like a Discord snowflake (17-20 digit numeric string)."""
    stripped = normalize_snowflake(value)
    return stripped.isdigit() and _MIN_SNOWFLAKE_LEN <= len(stripped) <= _MAX_SNOWFLAKE_LEN


def account_by_id(accounts: list[ResolvedDiscordAccount], account_id: str) -> ResolvedDiscordAccount | None:
    for acct in accounts:
        if acct.account_id == account_id:
            return acct
    return None
