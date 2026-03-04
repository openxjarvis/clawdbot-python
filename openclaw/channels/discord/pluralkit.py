"""
PluralKit proxy identity resolution.
Mirrors src/discord/pluralkit.ts and src/discord/monitor/sender-identity.ts.

PluralKit is a Discord bot that allows plural systems to post messages via webhook
proxies. This module queries the PluralKit API /v2/messages/{messageId} to resolve
the true system/member identity behind proxied messages.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

_PK_API_BASE = "https://api.pluralkit.me/v2"
_PK_CACHE: dict[str, "_PkMessageInfo | None"] = {}
_CACHE_SIZE_LIMIT = 500


@dataclass
class _PkMember:
    id: str
    name: str | None
    display_name: str | None


@dataclass
class _PkSystem:
    id: str
    name: str | None


@dataclass
class _PkMessageInfo:
    message_id: str
    sender: str | None          # Discord user ID of the actual sender
    system: _PkSystem | None
    member: _PkMember | None


async def fetch_pluralkit_message_info(
    message_id: str,
    config: dict[str, Any] | None = None,
) -> "_PkMessageInfo | None":
    """
    Query the PluralKit API for message info by Discord message ID.

    Returns a _PkMessageInfo or None if not a PK proxy / API query failed.

    Mirrors TS fetchPluralKitMessageInfo() using /v2/messages/{messageId}.
    """
    if config and not config.get("enabled", True):
        return None

    # Check cache
    if message_id in _PK_CACHE:
        return _PK_CACHE[message_id]

    headers: dict[str, str] = {}
    if config:
        token = (config.get("token") or "").strip()
        if token:
            headers["Authorization"] = token

    try:
        url = f"{_PK_API_BASE}/messages/{message_id}"
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, headers=headers, timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 404:
                    _cache_set(message_id, None)
                    return None
                if resp.status != 200:
                    logger.debug(
                        "[discord][pk] API returned %d for message %s", resp.status, message_id
                    )
                    return None

                data = await resp.json()
                sys_data = data.get("system") or {}
                mem_data = data.get("member") or {}
                info = _PkMessageInfo(
                    message_id=message_id,
                    sender=data.get("sender"),
                    system=_PkSystem(
                        id=sys_data.get("id", ""),
                        name=sys_data.get("name"),
                    ) if sys_data else None,
                    member=_PkMember(
                        id=mem_data.get("id", ""),
                        name=mem_data.get("name"),
                        display_name=mem_data.get("display_name"),
                    ) if mem_data else None,
                )
                _cache_set(message_id, info)
                return info
    except Exception as exc:
        logger.debug("[discord][pk] API query failed for message %s: %s", message_id, exc)
        return None


def resolve_pluralkit_sender_id(pk_info: "_PkMessageInfo | None") -> str | None:
    """
    Extract the effective sender ID from PluralKit message info.

    Returns "pk:<member_id>" for PK members, or the raw Discord sender ID,
    prefixed with "pk:" to mark it as PluralKit-originated.

    Mirrors resolveDiscordSenderIdentity logic for PluralKit senders.
    """
    if pk_info is None:
        return None
    member = pk_info.member
    if member and member.id:
        return f"pk:{member.id}"
    # Fall back to the Discord sender ID if member resolution failed
    if pk_info.sender:
        return f"pk:{pk_info.sender}"
    return None


def resolve_pluralkit_display(pk_info: "_PkMessageInfo | None") -> str | None:
    """Return a human-readable label for the PK sender, or None."""
    if pk_info is None:
        return None
    member = pk_info.member
    if member:
        name = (member.display_name or member.name or "").strip()
        system_name = (pk_info.system.name or "").strip() if pk_info.system else ""
        if name:
            return f"{name} (PK:{system_name})" if system_name else f"{name} (PK)"
    return None


def _cache_set(key: str, value: "_PkMessageInfo | None") -> None:
    if len(_PK_CACHE) >= _CACHE_SIZE_LIMIT:
        keys = list(_PK_CACHE.keys())[: _CACHE_SIZE_LIMIT // 2]
        for k in keys:
            del _PK_CACHE[k]
    _PK_CACHE[key] = value


def is_pluralkit_webhook(message: Any) -> bool:
    """
    Detect if a Discord message was sent by a PluralKit webhook proxy.
    PluralKit messages are sent via webhook — discord.py sets webhook_id.
    """
    return bool(getattr(message, "webhook_id", None))


# Legacy shim for code that calls resolve_pluralkit_sender(discord_user_id, webhook_user)
async def resolve_pluralkit_sender(
    discord_user_id: str,
    webhook_user: bool = False,
) -> str | None:
    """
    Legacy shim — kept for backwards compatibility.
    New code should call fetch_pluralkit_message_info with the message ID.
    """
    if not webhook_user:
        return None
    # Without a message ID we cannot do the correct lookup; return None
    logger.debug(
        "[discord][pk] resolve_pluralkit_sender called without message ID for %s; skipping",
        discord_user_id,
    )
    return None
