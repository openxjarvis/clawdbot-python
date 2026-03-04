"""Multi-account resolution for Feishu channel.

Mirrors TypeScript: extensions/feishu/src/accounts.ts
"""
from __future__ import annotations

import logging
from typing import Any

from .config import ResolvedFeishuAccount, parse_feishu_config

logger = logging.getLogger(__name__)


def resolve_feishu_accounts(cfg: dict[str, Any]) -> list[ResolvedFeishuAccount]:
    """
    Parse raw channel config and return a list of resolved accounts.

    Mirrors TS resolveFeishuAccounts().
    Returns empty list if no valid credentials found.
    """
    accounts = parse_feishu_config(cfg)
    valid = [a for a in accounts if a.app_id and a.app_secret]

    if not valid:
        logger.warning(
            "[feishu] No valid Feishu credentials found. "
            "Set channels.feishu.appId and channels.feishu.appSecret."
        )

    return valid


def resolve_feishu_account(
    cfg: dict[str, Any],
    account_id: str,
) -> ResolvedFeishuAccount | None:
    """
    Resolve a single account by ID. Returns None if not found.

    Mirrors TS resolveFeishuAccount().
    """
    accounts = resolve_feishu_accounts(cfg)
    for acct in accounts:
        if acct.account_id == account_id:
            return acct
    return None


def get_default_account(cfg: dict[str, Any]) -> ResolvedFeishuAccount | None:
    """
    Return the default account (first, or the one named by defaultAccount).

    Mirrors TS getDefaultFeishuAccount().
    """
    accounts = resolve_feishu_accounts(cfg)
    if not accounts:
        return None

    default_name = (cfg.get("defaultAccount") or "").strip()
    if default_name:
        for acct in accounts:
            if acct.account_id == default_name:
                return acct
        logger.warning("[feishu] defaultAccount=%r not found; using first account", default_name)

    return accounts[0]


def normalize_account_id(raw: str) -> str:
    """Normalize account ID to lowercase slug. Mirrors TS normalizeAccountId()."""
    return raw.strip().lower().replace(" ", "_")
