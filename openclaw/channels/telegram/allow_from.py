"""Telegram allow-from normalization utilities.

Mirrors TypeScript openclaw/src/channels/telegram/allow-from.ts.
"""
from __future__ import annotations

import re


def normalize_telegram_allow_from_entry(raw: object) -> str:
    """Normalize a raw allowFrom entry to a canonical Telegram ID/username string.

    Accepts str or int values.  Strips leading ``telegram:`` / ``tg:`` prefixes
    so that configuration entries like ``"telegram:12345"`` and ``"12345"`` are
    treated identically.

    Mirrors TS normalizeTelegramAllowFromEntry().
    """
    if isinstance(raw, str):
        base = raw
    elif isinstance(raw, (int, float)):
        base = str(raw)
    else:
        base = ""
    return re.sub(r"^(telegram|tg):", "", base.strip(), flags=re.IGNORECASE).strip()


def is_numeric_telegram_user_id(raw: str) -> bool:
    """Return True when *raw* looks like a numeric Telegram user/chat ID.

    Telegram user IDs are positive integers; group/channel IDs are negative.
    Mirrors TS isNumericTelegramUserId().
    """
    return bool(re.fullmatch(r"-?\d+", raw))


__all__ = [
    "normalize_telegram_allow_from_entry",
    "is_numeric_telegram_user_id",
]
