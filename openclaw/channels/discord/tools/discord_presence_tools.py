"""
Discord agent tools — bot presence and activity.
Mirrors src/agents/tools/discord-actions-presence.ts.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def register(api: Any) -> None:

    @api.tool("discord_set_presence")
    async def discord_set_presence(
        activity: str | None = None,
        activity_type: int = 0,
        status: str = "online",
        url: str | None = None,
    ) -> dict:
        """
        Set the Discord bot's activity and status.

        Args:
            activity: Activity text (e.g. "with fire")
            activity_type: 0=Playing, 1=Streaming, 2=Listening, 3=Watching, 4=Custom, 5=Competing
            status: "online" | "idle" | "dnd" | "invisible"
            url: Streaming URL (required for activity_type=1, must be Twitch/YouTube)

        Returns:
            {"success": bool}
        """
        channel_obj = api.get_channel("discord")
        if not channel_obj:
            return {"error": "Discord channel not available"}
        try:
            from openclaw.channels.discord.presence import set_presence
            client = channel_obj._get_client()
            await set_presence(client, activity, activity_type, status, url)
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}

    @api.tool("discord_clear_presence")
    async def discord_clear_presence() -> dict:
        """
        Clear the Discord bot's activity (shows as idle with no activity).

        Returns:
            {"success": bool}
        """
        channel_obj = api.get_channel("discord")
        if not channel_obj:
            return {"error": "Discord channel not available"}
        try:
            from openclaw.channels.discord.presence import set_presence
            client = channel_obj._get_client()
            await set_presence(client, activity_text=None, status="online")
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}

    @api.tool("discord_get_bot_info")
    async def discord_get_bot_info() -> dict:
        """
        Get information about the bot user.

        Returns:
            {"id", "name", "discriminator", "avatar_url", "guilds_count", "invite_url"}
        """
        channel_obj = api.get_channel("discord")
        if not channel_obj:
            return {"error": "Discord channel not available"}
        try:
            client = channel_obj._get_client()
            if not client or not client.user:
                return {"error": "Bot not connected"}
            user = client.user
            invite_url = await channel_obj.get_invite_url()
            return {
                "id": str(user.id),
                "name": str(user.name),
                "discriminator": getattr(user, "discriminator", "0"),
                "avatar_url": str(user.display_avatar.url) if user.display_avatar else None,
                "guilds_count": len(client.guilds),
                "invite_url": invite_url,
            }
        except Exception as e:
            return {"error": str(e)}
