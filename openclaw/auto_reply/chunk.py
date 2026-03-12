"""Text chunking configuration helpers.

Mirrors TypeScript src/auto-reply/chunk.ts — resolveTextChunkLimit and resolveChunkMode.
"""
from __future__ import annotations

from typing import Any, Literal, TypeVar

ChunkMode = Literal["length", "newline"]

DEFAULT_CHUNK_LIMIT: int = 4000
DEFAULT_CHUNK_MODE: ChunkMode = "length"

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


def _normalize_account_id(account_id: str | None) -> str:
    return (account_id or "").strip().lower()


def _resolve_chunk_limit_from_section(
    section: dict[str, Any] | None,
    account_id: str | None = None,
) -> int | None:
    if not section or not isinstance(section, dict):
        return None
    normalized = _normalize_account_id(account_id)
    accounts = section.get("accounts") or section.get("Accounts")
    if isinstance(accounts, dict) and normalized:
        entry = _resolve_account_entry(accounts, normalized)
        if isinstance(entry, dict):
            val = entry.get("textChunkLimit") or entry.get("text_chunk_limit")
            if isinstance(val, (int, float)) and val > 0:
                return int(val)
    val = section.get("textChunkLimit") or section.get("text_chunk_limit")
    if isinstance(val, (int, float)) and val > 0:
        return int(val)
    return None


def _resolve_chunk_mode_from_section(
    section: dict[str, Any] | None,
    account_id: str | None = None,
) -> ChunkMode | None:
    if not section or not isinstance(section, dict):
        return None
    normalized = _normalize_account_id(account_id)
    accounts = section.get("accounts") or section.get("Accounts")
    if isinstance(accounts, dict) and normalized:
        entry = _resolve_account_entry(accounts, normalized)
        if isinstance(entry, dict):
            mode = entry.get("chunkMode") or entry.get("chunk_mode")
            if mode in ("length", "newline"):
                return mode
    mode = section.get("chunkMode") or section.get("chunk_mode")
    if mode in ("length", "newline"):
        return mode
    return None


def _get_provider_section(cfg: dict[str, Any] | None, provider: str) -> dict[str, Any] | None:
    if not cfg or not isinstance(cfg, dict):
        return None
    channels = cfg.get("channels") or {}
    if isinstance(channels, dict):
        section = channels.get(provider)
        if isinstance(section, dict):
            return section
    section = cfg.get(provider)
    if isinstance(section, dict):
        return section
    return None


def resolve_text_chunk_limit(
    cfg: dict[str, Any] | None,
    provider: str | None = None,
    account_id: str | None = None,
    fallback_limit: int | None = None,
) -> int:
    """Resolve text chunk limit for a given channel/provider.

    Mirrors TS ``resolveTextChunkLimit(cfg, provider, accountId)``.
    Reads ``cfg.channels.<provider>.textChunkLimit`` with account-level override.
    Defaults to 4000 (WhatsApp standard).
    """
    fallback = fallback_limit if (isinstance(fallback_limit, int) and fallback_limit > 0) else DEFAULT_CHUNK_LIMIT
    if not provider:
        return fallback
    section = _get_provider_section(cfg, provider)
    override = _resolve_chunk_limit_from_section(section, account_id)
    if isinstance(override, int) and override > 0:
        return override
    return fallback


def resolve_chunk_mode(
    cfg: dict[str, Any] | None,
    provider: str | None = None,
    account_id: str | None = None,
) -> ChunkMode:
    """Resolve chunking mode for a given channel/provider.

    Mirrors TS ``resolveChunkMode(cfg, provider, accountId)``.
    Returns ``"length"`` (default) or ``"newline"``.
    """
    if not provider:
        return DEFAULT_CHUNK_MODE
    section = _get_provider_section(cfg, provider)
    mode = _resolve_chunk_mode_from_section(section, account_id)
    return mode if mode is not None else DEFAULT_CHUNK_MODE


__all__ = [
    "ChunkMode",
    "DEFAULT_CHUNK_LIMIT",
    "DEFAULT_CHUNK_MODE",
    "resolve_text_chunk_limit",
    "resolve_chunk_mode",
]
