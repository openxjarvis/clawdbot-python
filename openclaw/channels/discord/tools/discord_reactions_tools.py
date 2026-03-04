"""
Discord agent tools — reaction management.
Mirrors src/agents/tools/discord-actions.ts (reaction section).
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def register(api: Any) -> None:

    @api.tool("discord_add_reaction")
    async def discord_add_reaction(
        channel_id: str,
        message_id: str,
        emoji: str,
    ) -> dict:
        """
        Add a reaction to a Discord message.

        Args:
            channel_id: Channel containing the message
            message_id: Message to react to
            emoji: Emoji to react with (unicode or "name:id" for custom emojis)

        Returns:
            {"success": bool}
        """
        channel_obj = api.get_channel("discord")
        if not channel_obj:
            return {"error": "Discord channel not available"}
        try:
            from openclaw.channels.discord.reactions import react_message
            client = channel_obj._get_client()
            await react_message(client, channel_id, message_id, emoji)
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}

    @api.tool("discord_remove_reaction")
    async def discord_remove_reaction(
        channel_id: str,
        message_id: str,
        emoji: str,
        user_id: str | None = None,
    ) -> dict:
        """
        Remove a reaction from a Discord message.

        Args:
            channel_id: Channel containing the message
            message_id: Message to remove reaction from
            emoji: Emoji to remove
            user_id: User whose reaction to remove (None = bot's own reaction)

        Returns:
            {"success": bool}
        """
        channel_obj = api.get_channel("discord")
        if not channel_obj:
            return {"error": "Discord channel not available"}
        try:
            from openclaw.channels.discord.reactions import remove_reaction
            client = channel_obj._get_client()
            await remove_reaction(client, channel_id, message_id, emoji, user_id)
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}

    @api.tool("discord_remove_all_reactions")
    async def discord_remove_all_reactions(
        channel_id: str,
        message_id: str,
        emoji: str | None = None,
    ) -> dict:
        """
        Remove all reactions (or all of a specific emoji) from a message.

        Args:
            channel_id: Channel containing the message
            message_id: Message to clear reactions from
            emoji: If provided, only remove this specific emoji's reactions

        Returns:
            {"success": bool}
        """
        channel_obj = api.get_channel("discord")
        if not channel_obj:
            return {"error": "Discord channel not available"}
        try:
            client = channel_obj._get_client()
            ch = client.get_channel(int(channel_id)) or await client.fetch_channel(int(channel_id))
            msg = await ch.fetch_message(int(message_id))
            if emoji:
                await msg.clear_reaction(emoji)
            else:
                await msg.clear_reactions()
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}

    @api.tool("discord_get_reactions")
    async def discord_get_reactions(
        channel_id: str,
        message_id: str,
        emoji: str,
        limit: int = 100,
    ) -> dict:
        """
        Get users who reacted to a message with a specific emoji.

        Args:
            channel_id: Channel containing the message
            message_id: Target message
            emoji: Emoji to check
            limit: Max users to return

        Returns:
            {"users": [{"id": str, "name": str}], "count": int}
        """
        channel_obj = api.get_channel("discord")
        if not channel_obj:
            return {"error": "Discord channel not available"}
        try:
            from openclaw.channels.discord.reactions import fetch_reactions
            client = channel_obj._get_client()
            users = await fetch_reactions(client, channel_id, message_id, emoji, limit)
            return {"users": users, "count": len(users)}
        except Exception as e:
            return {"error": str(e)}
