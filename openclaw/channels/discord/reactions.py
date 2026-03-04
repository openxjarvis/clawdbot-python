"""
Discord reactions — send/remove/fetch.
Mirrors src/discord/send.reactions.ts and reaction notification gating.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def react_message(
    client: Any,
    channel_id: int | str,
    message_id: int | str,
    emoji: str,
) -> None:
    """
    Add a reaction to a message.
    Wraps PUT /channels/{id}/messages/{id}/reactions/{emoji}/@me.
    """
    try:
        ch = client.get_channel(int(channel_id))
        if ch is None:
            ch = await client.fetch_channel(int(channel_id))
        msg = await ch.fetch_message(int(message_id))
        await msg.add_reaction(emoji)
    except Exception as exc:
        logger.warning("[discord][reactions] Failed to add reaction %s: %s", emoji, exc)


async def remove_reaction(
    client: Any,
    channel_id: int | str,
    message_id: int | str,
    emoji: str,
    user_id: int | str | None = None,
) -> None:
    """
    Remove a reaction.  If user_id is None, removes the bot's own reaction.
    """
    try:
        ch = client.get_channel(int(channel_id))
        if ch is None:
            ch = await client.fetch_channel(int(channel_id))
        msg = await ch.fetch_message(int(message_id))
        if user_id:
            user = await client.fetch_user(int(user_id))
            await msg.remove_reaction(emoji, user)
        else:
            await msg.remove_reaction(emoji, client.user)
    except Exception as exc:
        logger.warning("[discord][reactions] Failed to remove reaction %s: %s", emoji, exc)


async def remove_own_reactions(
    client: Any,
    channel_id: int | str,
    message_id: int | str,
) -> None:
    """Remove all of the bot's reactions from a message."""
    try:
        ch = client.get_channel(int(channel_id))
        if ch is None:
            ch = await client.fetch_channel(int(channel_id))
        msg = await ch.fetch_message(int(message_id))
        for reaction in msg.reactions:
            if reaction.me:
                await reaction.remove(client.user)
    except Exception as exc:
        logger.warning("[discord][reactions] Failed to remove own reactions: %s", exc)


async def fetch_reactions(
    client: Any,
    channel_id: int | str,
    message_id: int | str,
    emoji: str,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """
    List users who reacted with a given emoji.
    Returns list of dicts with {id, name, discriminator}.
    """
    try:
        ch = client.get_channel(int(channel_id))
        if ch is None:
            ch = await client.fetch_channel(int(channel_id))
        msg = await ch.fetch_message(int(message_id))
        for reaction in msg.reactions:
            if str(reaction.emoji) == emoji:
                users = [u async for u in reaction.users(limit=limit)]
                return [{"id": str(u.id), "name": str(u.name)} for u in users]
        return []
    except Exception as exc:
        logger.warning("[discord][reactions] Failed to fetch reactions: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Reaction notification gating — mirrors reactionNotifications config
# ---------------------------------------------------------------------------

def should_forward_reaction(
    reaction_notifications: str,
    bot_id: int | str,
    message_author_id: int | str,
    reactor_id: int | str,
    allow_from: list[str] | None = None,
) -> bool:
    """
    Decide whether to forward a reaction event to the agent based on
    the guild/channel reactionNotifications config.

    Values:
      "off"       — never forward
      "own"       — only on bot's own messages (default)
      "all"       — all reactions in configured channels
      "allowlist" — only from users in allow_from
    """
    if reaction_notifications == "off":
        return False
    if reaction_notifications == "all":
        return True
    if reaction_notifications == "own":
        return str(message_author_id) == str(bot_id)
    if reaction_notifications == "allowlist":
        return bool(allow_from) and str(reactor_id) in (allow_from or [])
    return False
