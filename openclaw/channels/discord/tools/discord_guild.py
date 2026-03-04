"""
Discord agent tools — guild, member, role, events, voice status.
Mirrors src/agents/tools/discord-actions-guild.ts.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def register(api: Any) -> None:

    @api.tool("discord_get_member_info")
    async def discord_get_member_info(guild_id: str, user_id: str) -> dict:
        """
        Get information about a guild member.

        Args:
            guild_id: Discord guild (server) ID
            user_id: Discord user ID

        Returns:
            {"id", "name", "display_name", "roles", "joined_at", "is_bot"}
        """
        channel_obj = api.get_channel("discord")
        if not channel_obj:
            return {"error": "Discord channel not available"}
        try:
            client = channel_obj._get_client()
            guild = client.get_guild(int(guild_id)) or await client.fetch_guild(int(guild_id))
            member = guild.get_member(int(user_id)) or await guild.fetch_member(int(user_id))
            return {
                "id": str(member.id),
                "name": str(member.name),
                "display_name": member.display_name,
                "roles": [{"id": str(r.id), "name": r.name} for r in member.roles[1:]],  # skip @everyone
                "joined_at": member.joined_at.isoformat() if member.joined_at else None,
                "is_bot": member.bot,
                "avatar_url": str(member.display_avatar.url) if member.display_avatar else None,
            }
        except Exception as e:
            return {"error": str(e)}

    @api.tool("discord_list_roles")
    async def discord_list_roles(guild_id: str) -> dict:
        """
        List all roles in a guild.

        Args:
            guild_id: Discord guild ID

        Returns:
            {"roles": [{"id", "name", "color", "position", "member_count"}]}
        """
        channel_obj = api.get_channel("discord")
        if not channel_obj:
            return {"error": "Discord channel not available"}
        try:
            client = channel_obj._get_client()
            guild = client.get_guild(int(guild_id)) or await client.fetch_guild(int(guild_id))
            return {
                "roles": [
                    {
                        "id": str(r.id),
                        "name": r.name,
                        "color": str(r.color),
                        "position": r.position,
                        "mentionable": r.mentionable,
                    }
                    for r in sorted(guild.roles, key=lambda x: x.position, reverse=True)
                ]
            }
        except Exception as e:
            return {"error": str(e)}

    @api.tool("discord_assign_role")
    async def discord_assign_role(
        guild_id: str,
        user_id: str,
        role_id: str,
        remove: bool = False,
    ) -> dict:
        """
        Assign or remove a role from a guild member.

        Args:
            guild_id: Discord guild ID
            user_id: Target user ID
            role_id: Role ID to assign/remove
            remove: If True, remove the role instead

        Returns:
            {"success": bool}
        """
        channel_obj = api.get_channel("discord")
        if not channel_obj:
            return {"error": "Discord channel not available"}
        try:
            client = channel_obj._get_client()
            guild = client.get_guild(int(guild_id)) or await client.fetch_guild(int(guild_id))
            member = guild.get_member(int(user_id)) or await guild.fetch_member(int(user_id))
            role = guild.get_role(int(role_id))
            if role is None:
                return {"error": f"Role {role_id} not found"}
            if remove:
                await member.remove_roles(role)
            else:
                await member.add_roles(role)
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}

    @api.tool("discord_list_guild_events")
    async def discord_list_guild_events(guild_id: str) -> dict:
        """
        List scheduled events in a guild.

        Args:
            guild_id: Discord guild ID

        Returns:
            {"events": [{"id", "name", "description", "start_time", "status", "creator"}]}
        """
        channel_obj = api.get_channel("discord")
        if not channel_obj:
            return {"error": "Discord channel not available"}
        try:
            client = channel_obj._get_client()
            guild = client.get_guild(int(guild_id)) or await client.fetch_guild(int(guild_id))
            events = await guild.fetch_scheduled_events()
            return {
                "events": [
                    {
                        "id": str(e.id),
                        "name": e.name,
                        "description": e.description,
                        "start_time": e.start_time.isoformat() if e.start_time else None,
                        "status": str(e.status),
                        "creator_id": str(e.creator_id) if e.creator_id else None,
                    }
                    for e in events
                ]
            }
        except Exception as e:
            return {"error": str(e)}

    @api.tool("discord_get_voice_status")
    async def discord_get_voice_status(guild_id: str) -> dict:
        """
        Get current voice channel status for a guild.

        Args:
            guild_id: Discord guild ID

        Returns:
            {"voice_channels": [{"id", "name", "members": [...]}]}
        """
        channel_obj = api.get_channel("discord")
        if not channel_obj:
            return {"error": "Discord channel not available"}
        try:
            client = channel_obj._get_client()
            guild = client.get_guild(int(guild_id)) or await client.fetch_guild(int(guild_id))
            result = []
            for ch in guild.voice_channels:
                members = [
                    {
                        "id": str(m.id),
                        "name": m.display_name,
                        "muted": m.voice.mute or m.voice.self_mute,
                        "deafened": m.voice.deaf or m.voice.self_deaf,
                    }
                    for m in ch.members
                ]
                result.append({"id": str(ch.id), "name": ch.name, "members": members})
            return {"voice_channels": result}
        except Exception as e:
            return {"error": str(e)}

    @api.tool("discord_list_channels")
    async def discord_list_channels(guild_id: str) -> dict:
        """
        List all channels in a guild.

        Args:
            guild_id: Discord guild ID

        Returns:
            {"channels": [{"id", "name", "type", "category", "position"}]}
        """
        channel_obj = api.get_channel("discord")
        if not channel_obj:
            return {"error": "Discord channel not available"}
        try:
            client = channel_obj._get_client()
            guild = client.get_guild(int(guild_id)) or await client.fetch_guild(int(guild_id))
            channels = await guild.fetch_channels()
            return {
                "channels": [
                    {
                        "id": str(ch.id),
                        "name": getattr(ch, "name", str(ch.id)),
                        "type": str(ch.type),
                        "category": getattr(getattr(ch, "category", None), "name", None),
                        "position": getattr(ch, "position", 0),
                    }
                    for ch in sorted(channels, key=lambda c: getattr(c, "position", 0))
                ]
            }
        except Exception as e:
            return {"error": str(e)}
