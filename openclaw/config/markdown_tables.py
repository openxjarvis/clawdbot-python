"""Markdown table rendering mode helpers.

Mirrors TypeScript src/config/markdown-tables.ts — resolveMarkdownTableMode.
"""
from __future__ import annotations

from typing import Any, Literal, TypeVar

MarkdownTableMode = Literal["off", "bullets", "code"]

# Default table modes per channel — matches TS DEFAULT_TABLE_MODES
_DEFAULT_TABLE_MODES: dict[str, MarkdownTableMode] = {
    "signal": "bullets",
    "whatsapp": "bullets",
}

_VALID_MODES = frozenset(("off", "bullets", "code"))

T = TypeVar("T")


def _resolve_account_entry(
    accounts: dict[str, T] | None,
    account_id: str,
) -> T | None:
    """Resolve account entry with case-insensitive fuzzy matching.
    
    Mirrors TS resolveAccountEntry from src/routing/account-lookup.ts.
    Tries exact match first, then case-insensitive match.
    """
    if not accounts or not isinstance(accounts, dict):
        return None
    if account_id in accounts:
        return accounts[account_id]
    normalized = account_id.lower()
    for key in accounts:
        if key.lower() == normalized:
            return accounts[key]
    return None


def _normalize_channel(channel: str | None) -> str:
    return (channel or "").strip().lower()


def _normalize_account_id(account_id: str | None) -> str:
    return (account_id or "").strip().lower()


def _resolve_mode_from_section(
    section: dict[str, Any] | None,
    account_id: str | None = None,
) -> MarkdownTableMode | None:
    if not section or not isinstance(section, dict):
        return None
    normalized = _normalize_account_id(account_id)
    accounts = section.get("accounts") or {}
    if isinstance(accounts, dict) and normalized:
        entry = _resolve_account_entry(accounts, normalized)
        if isinstance(entry, dict):
            mode = (entry.get("markdown") or {}).get("tables")
            if mode in _VALID_MODES:
                return mode
    markdown = section.get("markdown") or {}
    if isinstance(markdown, dict):
        mode = markdown.get("tables")
        if mode in _VALID_MODES:
            return mode
    return None


def resolve_markdown_table_mode(
    cfg: dict[str, Any] | None = None,
    channel: str | None = None,
    account_id: str | None = None,
) -> MarkdownTableMode:
    """Resolve markdown table rendering mode for a channel/account.

    Mirrors TS ``resolveMarkdownTableMode({cfg, channel, accountId})``.

    WhatsApp and Signal default to ``"bullets"``; all others default to ``"code"``.
    Can be overridden per-channel or per-account in the config.
    """
    ch = _normalize_channel(channel)
    default_mode: MarkdownTableMode = _DEFAULT_TABLE_MODES.get(ch, "code")
    if not ch or not cfg or not isinstance(cfg, dict):
        return default_mode

    channels = cfg.get("channels") or {}
    section = None
    if isinstance(channels, dict):
        section = channels.get(ch)
    if not isinstance(section, dict):
        section = cfg.get(ch)
    if not isinstance(section, dict):
        return default_mode

    resolved = _resolve_mode_from_section(section, account_id)
    return resolved if resolved is not None else default_mode


__all__ = [
    "MarkdownTableMode",
    "resolve_markdown_table_mode",
]
