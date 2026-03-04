"""
Discord agent tools — moderation (ban, kick, timeout, prune, audit log).
Mirrors src/agents/tools/discord-actions-moderation.ts.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

logger = logging.getLogger(__name__)


def register(api: Any) -> None:

    @api.tool("discord_ban_member")
    async def discord_ban_member(
        guild_id: str,
        user_id: str,
        reason: str | None = None,
        delete_message_days: int = 0,
    ) -> dict:
        """
        Ban a member from a Discord guild.

        Args:
            guild_id: Discord guild ID
            user_id: User to ban
            reason: Reason for the ban (shown in audit log)
            delete_message_days: Days of messages to delete (0-7)

        Returns:
            {"success": bool}
        """
        channel_obj = api.get_channel("discord")
        if not channel_obj:
            return {"error": "Discord channel not available"}
        try:
            client = channel_obj._get_client()
            guild = client.get_guild(int(guild_id)) or await client.fetch_guild(int(guild_id))
            await guild.ban(
                __import__("discord").Object(id=int(user_id)),
                reason=reason,
                delete_message_days=min(7, max(0, delete_message_days)),
            )
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}

    @api.tool("discord_unban_member")
    async def discord_unban_member(
        guild_id: str,
        user_id: str,
        reason: str | None = None,
    ) -> dict:
        """
        Unban a user from a Discord guild.

        Args:
            guild_id: Discord guild ID
            user_id: User to unban
            reason: Reason for the unban

        Returns:
            {"success": bool}
        """
        channel_obj = api.get_channel("discord")
        if not channel_obj:
            return {"error": "Discord channel not available"}
        try:
            client = channel_obj._get_client()
            guild = client.get_guild(int(guild_id)) or await client.fetch_guild(int(guild_id))
            await guild.unban(
                __import__("discord").Object(id=int(user_id)),
                reason=reason,
            )
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}

    @api.tool("discord_kick_member")
    async def discord_kick_member(
        guild_id: str,
        user_id: str,
        reason: str | None = None,
    ) -> dict:
        """
        Kick a member from a Discord guild.

        Args:
            guild_id: Discord guild ID
            user_id: User to kick
            reason: Reason for the kick

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
            await member.kick(reason=reason)
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}

    @api.tool("discord_timeout_member")
    async def discord_timeout_member(
        guild_id: str,
        user_id: str,
        duration_minutes: int,
        reason: str | None = None,
    ) -> dict:
        """
        Timeout (mute) a Discord member for a specified duration.

        Args:
            guild_id: Discord guild ID
            user_id: User to timeout
            duration_minutes: Timeout duration in minutes (0 to remove timeout)
            reason: Reason for the timeout

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
            if duration_minutes <= 0:
                await member.timeout(None, reason=reason)
            else:
                until = __import__("discord").utils.utcnow() + timedelta(minutes=duration_minutes)
                await member.timeout(until, reason=reason)
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}

    @api.tool("discord_bulk_delete_messages")
    async def discord_bulk_delete_messages(
        channel_id: str,
        limit: int = 10,
        author_id: str | None = None,
    ) -> dict:
        """
        Bulk delete recent messages in a channel (max 100, within 14 days).

        Args:
            channel_id: Channel to purge
            limit: Max messages to delete (1-100)
            author_id: If set, only delete messages from this user

        Returns:
            {"deleted_count": int}
        """
        channel_obj = api.get_channel("discord")
        if not channel_obj:
            return {"error": "Discord channel not available"}
        try:
            client = channel_obj._get_client()
            ch = client.get_channel(int(channel_id)) or await client.fetch_channel(int(channel_id))
            limit = min(100, max(1, limit))

            if author_id:
                messages = [m async for m in ch.history(limit=min(200, limit * 4)) if str(m.author.id) == author_id][:limit]
            else:
                messages = [m async for m in ch.history(limit=limit)]

            if not messages:
                return {"deleted_count": 0}

            await ch.delete_messages(messages)
            return {"deleted_count": len(messages)}
        except Exception as e:
            return {"error": str(e)}

    @api.tool("discord_get_audit_log")
    async def discord_get_audit_log(
        guild_id: str,
        limit: int = 10,
        action: str | None = None,
    ) -> dict:
        """
        Get recent audit log entries for a guild.

        Args:
            guild_id: Discord guild ID
            limit: Max entries to return (1-100)
            action: Filter by action type (e.g. "ban", "kick", "message_delete")

        Returns:
            {"entries": [{"id", "action", "user", "target", "reason", "created_at"}]}
        """
        channel_obj = api.get_channel("discord")
        if not channel_obj:
            return {"error": "Discord channel not available"}
        try:
            import discord
            client = channel_obj._get_client()
            guild = client.get_guild(int(guild_id)) or await client.fetch_guild(int(guild_id))

            action_type = None
            if action:
                action_map = {
                    "ban": discord.AuditLogAction.ban,
                    "kick": discord.AuditLogAction.kick,
                    "unban": discord.AuditLogAction.unban,
                    "message_delete": discord.AuditLogAction.message_delete,
                    "channel_create": discord.AuditLogAction.channel_create,
                    "channel_delete": discord.AuditLogAction.channel_delete,
                    "member_update": discord.AuditLogAction.member_update,
                    "role_create": discord.AuditLogAction.role_create,
                }
                action_type = action_map.get(action.lower())

            kwargs: dict[str, Any] = {"limit": min(100, max(1, limit))}
            if action_type:
                kwargs["action"] = action_type

            entries = []
            async for entry in guild.audit_logs(**kwargs):
                entries.append({
                    "id": str(entry.id),
                    "action": str(entry.action),
                    "user": str(entry.user) if entry.user else None,
                    "target": str(entry.target) if entry.target else None,
                    "reason": entry.reason,
                    "created_at": entry.created_at.isoformat(),
                })
            return {"entries": entries}
        except Exception as e:
            return {"error": str(e)}
