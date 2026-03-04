"""
Discord agent tools — channel management (create/edit/delete/move/permissions).
Mirrors src/agents/tools/discord-actions.ts (channel section).
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def register(api: Any) -> None:

    @api.tool("discord_create_channel")
    async def discord_create_channel(
        guild_id: str,
        name: str,
        channel_type: str = "text",
        category_id: str | None = None,
        topic: str | None = None,
        nsfw: bool = False,
        position: int | None = None,
        reason: str | None = None,
    ) -> dict:
        """
        Create a new Discord channel.

        Args:
            guild_id: Guild to create the channel in
            name: Channel name
            channel_type: "text" | "voice" | "stage" | "forum" | "category" | "announcement"
            category_id: Parent category ID
            topic: Channel topic/description
            nsfw: Mark as NSFW
            position: Position in channel list
            reason: Reason shown in audit log

        Returns:
            {"channel_id": str, "channel_name": str}
        """
        channel_obj = api.get_channel("discord")
        if not channel_obj:
            return {"error": "Discord channel not available"}
        try:
            import discord
            client = channel_obj._get_client()
            guild = client.get_guild(int(guild_id)) or await client.fetch_guild(int(guild_id))

            type_map = {
                "text": discord.ChannelType.text,
                "voice": discord.ChannelType.voice,
                "stage": discord.ChannelType.stage_voice,
                "forum": discord.ChannelType.forum,
                "category": discord.ChannelType.category,
                "announcement": discord.ChannelType.news,
            }
            ch_type = type_map.get(channel_type, discord.ChannelType.text)

            kwargs: dict[str, Any] = {"name": name, "reason": reason}
            if topic:
                kwargs["topic"] = topic
            if nsfw:
                kwargs["nsfw"] = nsfw
            if position is not None:
                kwargs["position"] = position
            if category_id:
                kwargs["category"] = discord.Object(id=int(category_id))

            ch = await guild.create_text_channel(**kwargs) if ch_type == discord.ChannelType.text else \
                 await guild.create_voice_channel(**kwargs) if ch_type == discord.ChannelType.voice else \
                 await guild.create_category(**{k: v for k, v in kwargs.items() if k != "topic"}) if ch_type == discord.ChannelType.category else \
                 await guild.create_forum_channel(**kwargs) if ch_type == discord.ChannelType.forum else \
                 await guild.create_text_channel(**kwargs)

            return {"channel_id": str(ch.id), "channel_name": ch.name}
        except Exception as e:
            return {"error": str(e)}

    @api.tool("discord_edit_channel")
    async def discord_edit_channel(
        channel_id: str,
        name: str | None = None,
        topic: str | None = None,
        position: int | None = None,
        nsfw: bool | None = None,
        slowmode_delay: int | None = None,
        reason: str | None = None,
    ) -> dict:
        """
        Edit a Discord channel's settings.

        Args:
            channel_id: Channel to edit
            name: New channel name
            topic: New channel topic
            position: New position in channel list
            nsfw: Set NSFW flag
            slowmode_delay: Slowmode delay in seconds (0 to disable)
            reason: Reason shown in audit log

        Returns:
            {"success": bool}
        """
        channel_obj = api.get_channel("discord")
        if not channel_obj:
            return {"error": "Discord channel not available"}
        try:
            client = channel_obj._get_client()
            ch = client.get_channel(int(channel_id)) or await client.fetch_channel(int(channel_id))
            kwargs: dict[str, Any] = {}
            if name is not None:
                kwargs["name"] = name
            if topic is not None:
                kwargs["topic"] = topic
            if position is not None:
                kwargs["position"] = position
            if nsfw is not None:
                kwargs["nsfw"] = nsfw
            if slowmode_delay is not None:
                kwargs["slowmode_delay"] = slowmode_delay
            if reason:
                kwargs["reason"] = reason
            await ch.edit(**kwargs)
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}

    @api.tool("discord_delete_channel")
    async def discord_delete_channel(
        channel_id: str,
        reason: str | None = None,
    ) -> dict:
        """
        Delete a Discord channel.

        Args:
            channel_id: Channel to delete
            reason: Reason shown in audit log

        Returns:
            {"success": bool}
        """
        channel_obj = api.get_channel("discord")
        if not channel_obj:
            return {"error": "Discord channel not available"}
        try:
            client = channel_obj._get_client()
            ch = client.get_channel(int(channel_id)) or await client.fetch_channel(int(channel_id))
            await ch.delete(reason=reason)
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}

    @api.tool("discord_set_channel_permissions")
    async def discord_set_channel_permissions(
        channel_id: str,
        target_id: str,
        target_type: str,
        allow: list[str] | None = None,
        deny: list[str] | None = None,
        reason: str | None = None,
    ) -> dict:
        """
        Set channel-level permission overwrites for a role or member.

        Args:
            channel_id: Channel to modify
            target_id: Role or user ID
            target_type: "role" or "member"
            allow: List of permission names to allow (e.g. ["send_messages", "view_channel"])
            deny: List of permission names to deny
            reason: Reason shown in audit log

        Returns:
            {"success": bool}
        """
        channel_obj = api.get_channel("discord")
        if not channel_obj:
            return {"error": "Discord channel not available"}
        try:
            import discord
            client = channel_obj._get_client()
            ch = client.get_channel(int(channel_id)) or await client.fetch_channel(int(channel_id))
            guild = ch.guild if hasattr(ch, "guild") else None

            if target_type == "role" and guild:
                target = guild.get_role(int(target_id))
            else:
                target = discord.Object(id=int(target_id))

            perms_allow = discord.Permissions(**{p: True for p in (allow or [])})
            perms_deny = discord.Permissions(**{p: True for p in (deny or [])})
            overwrite = discord.PermissionOverwrite.from_pair(perms_allow, perms_deny)
            await ch.set_permissions(target, overwrite=overwrite, reason=reason)
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}

    @api.tool("discord_move_channel")
    async def discord_move_channel(
        channel_id: str,
        position: int,
        category_id: str | None = None,
        reason: str | None = None,
    ) -> dict:
        """
        Move a channel to a new position or category.

        Args:
            channel_id: Channel to move
            position: New position
            category_id: New parent category ID (None to remove from category)
            reason: Reason shown in audit log

        Returns:
            {"success": bool}
        """
        channel_obj = api.get_channel("discord")
        if not channel_obj:
            return {"error": "Discord channel not available"}
        try:
            import discord
            client = channel_obj._get_client()
            ch = client.get_channel(int(channel_id)) or await client.fetch_channel(int(channel_id))
            kwargs: dict[str, Any] = {"position": position}
            if category_id:
                kwargs["category"] = discord.Object(id=int(category_id))
            if reason:
                kwargs["reason"] = reason
            await ch.edit(**kwargs)
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}
