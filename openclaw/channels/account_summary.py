"""Channel account summary helpers — mirrors src/channels/account-summary.ts"""
from __future__ import annotations

from typing import Any


def build_channel_account_snapshot(
    *,
    plugin: Any,
    account: Any,
    cfg: Any,
    account_id: str,
    enabled: bool,
    configured: bool,
) -> dict:
    described: dict = {}
    describe_fn = getattr(getattr(plugin, "config", None), "describe_account", None) or \
                  getattr(getattr(plugin, "config", None), "describeAccount", None)
    if callable(describe_fn):
        result = describe_fn(account, cfg)
        if isinstance(result, dict):
            described = result

    return {
        "enabled": enabled,
        "configured": configured,
        **described,
        "accountId": account_id,
    }


def format_channel_allow_from(
    *,
    plugin: Any,
    cfg: Any,
    account_id: str | None = None,
    allow_from: list[str | int],
) -> list[str]:
    fmt_fn = getattr(getattr(plugin, "config", None), "format_allow_from", None) or \
             getattr(getattr(plugin, "config", None), "formatAllowFrom", None)
    if callable(fmt_fn):
        return fmt_fn(cfg=cfg, account_id=account_id, allow_from=allow_from)
    return [str(e).strip() for e in allow_from if str(e).strip()]
