"""
Discord agent tools — messaging operations.
Mirrors src/agents/tools/discord-actions-messaging.ts.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def register(api: Any) -> None:
    """Register all Discord messaging tools with the openclaw tool API."""

    @api.tool("discord_send_message")
    async def discord_send_message(
        target: str,
        text: str,
        reply_to: str | None = None,
        silent: bool = False,
    ) -> dict:
        """
        Send a text message to a Discord channel or user.

        Args:
            target: Channel ID, "channel:<id>", or "user:<id>" (opens DM)
            text: Message content (auto-chunked at 2000 chars)
            reply_to: Message ID to reply to
            silent: If True, suppress notifications

        Returns:
            {"message_id": str, "channel_id": str}
        """
        channel_obj = api.get_channel("discord")
        if not channel_obj:
            return {"error": "Discord channel not available"}
        try:
            from openclaw.channels.discord.outbound import send_discord_text
            client = channel_obj._get_client()
            msgs = await send_discord_text(
                client=client,
                target=target,
                text=text,
                reply_to=int(reply_to) if reply_to else None,
                silent=silent,
            )
            return {"message_id": str(msgs[-1].id) if msgs else "", "channel_id": target}
        except Exception as e:
            return {"error": str(e)}

    @api.tool("discord_edit_message")
    async def discord_edit_message(
        channel_id: str,
        message_id: str,
        new_content: str,
    ) -> dict:
        """
        Edit an existing Discord message.

        Args:
            channel_id: Channel containing the message
            message_id: Message to edit
            new_content: New message content

        Returns:
            {"success": bool}
        """
        channel_obj = api.get_channel("discord")
        if not channel_obj:
            return {"error": "Discord channel not available"}
        try:
            from openclaw.channels.discord.outbound import edit_discord_message
            client = channel_obj._get_client()
            msg = await edit_discord_message(client, channel_id, message_id, new_content)
            return {"success": msg is not None}
        except Exception as e:
            return {"error": str(e)}

    @api.tool("discord_delete_message")
    async def discord_delete_message(
        channel_id: str,
        message_id: str,
    ) -> dict:
        """
        Delete a Discord message.

        Args:
            channel_id: Channel containing the message
            message_id: Message to delete

        Returns:
            {"success": bool}
        """
        channel_obj = api.get_channel("discord")
        if not channel_obj:
            return {"error": "Discord channel not available"}
        try:
            from openclaw.channels.discord.outbound import delete_discord_message
            client = channel_obj._get_client()
            ok = await delete_discord_message(client, channel_id, message_id)
            return {"success": ok}
        except Exception as e:
            return {"error": str(e)}

    @api.tool("discord_pin_message")
    async def discord_pin_message(
        channel_id: str,
        message_id: str,
        unpin: bool = False,
    ) -> dict:
        """
        Pin or unpin a Discord message.

        Args:
            channel_id: Channel containing the message
            message_id: Message to pin/unpin
            unpin: If True, unpin the message

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
            if unpin:
                await msg.unpin()
            else:
                await msg.pin()
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}

    @api.tool("discord_send_embed")
    async def discord_send_embed(
        target: str,
        title: str | None = None,
        description: str | None = None,
        color: str | None = None,
        fields: list[dict] | None = None,
        footer: str | None = None,
        thumbnail_url: str | None = None,
        reply_to: str | None = None,
    ) -> dict:
        """
        Send a Discord rich embed.

        Args:
            target: Channel or user target
            title: Embed title
            description: Embed description (markdown supported)
            color: Hex color string like "#FF0000"
            fields: List of {"name": str, "value": str, "inline": bool}
            footer: Footer text
            thumbnail_url: Thumbnail image URL
            reply_to: Message ID to reply to

        Returns:
            {"message_id": str}
        """
        channel_obj = api.get_channel("discord")
        if not channel_obj:
            return {"error": "Discord channel not available"}
        try:
            from openclaw.channels.discord.outbound import send_discord_embed
            client = channel_obj._get_client()
            msg = await send_discord_embed(
                client, target, title=title, description=description,
                color=color, fields=fields, footer=footer,
                thumbnail_url=thumbnail_url,
                reply_to=int(reply_to) if reply_to else None,
            )
            return {"message_id": str(msg.id) if msg else ""}
        except Exception as e:
            return {"error": str(e)}

    @api.tool("discord_send_poll")
    async def discord_send_poll(
        target: str,
        question: str,
        answers: list[str],
        duration_hours: int = 24,
        allow_multiselect: bool = False,
    ) -> dict:
        """
        Send a Discord native poll.

        Args:
            target: Channel target
            question: Poll question
            answers: List of answer options (max 10)
            duration_hours: Poll duration in hours (max 168)
            allow_multiselect: Allow multiple selections

        Returns:
            {"message_id": str}
        """
        channel_obj = api.get_channel("discord")
        if not channel_obj:
            return {"error": "Discord channel not available"}
        try:
            from openclaw.channels.discord.outbound import send_discord_poll
            client = channel_obj._get_client()
            msg = await send_discord_poll(
                client, target, question, answers, duration_hours, allow_multiselect
            )
            return {"message_id": str(msg.id) if msg else ""}
        except Exception as e:
            return {"error": str(e)}

    @api.tool("discord_create_thread")
    async def discord_create_thread(
        channel_id: str,
        name: str,
        message_id: str | None = None,
        auto_archive_minutes: int = 1440,
    ) -> dict:
        """
        Create a Discord thread.

        Args:
            channel_id: Parent channel
            name: Thread name (max 100 chars)
            message_id: If provided, create a thread from this message
            auto_archive_minutes: Auto-archive after inactivity (60/1440/4320/10080)

        Returns:
            {"thread_id": str, "thread_name": str}
        """
        channel_obj = api.get_channel("discord")
        if not channel_obj:
            return {"error": "Discord channel not available"}
        try:
            from openclaw.channels.discord.threading import (
                create_thread_from_message, create_thread_in_channel
            )
            client = channel_obj._get_client()
            ch = client.get_channel(int(channel_id)) or await client.fetch_channel(int(channel_id))
            if message_id:
                msg = await ch.fetch_message(int(message_id))
                thread = await create_thread_from_message(msg, name, auto_archive_minutes)
            else:
                thread = await create_thread_in_channel(ch, name, auto_archive_minutes)
            if thread:
                return {"thread_id": str(thread.id), "thread_name": thread.name}
            return {"error": "Failed to create thread"}
        except Exception as e:
            return {"error": str(e)}

    @api.tool("discord_search_messages")
    async def discord_search_messages(
        guild_id: str,
        query: str,
        channel_id: str | None = None,
        author_id: str | None = None,
        limit: int = 25,
    ) -> dict:
        """
        Search messages in a Discord guild.
        Note: Requires Discord Nitro or special access; uses REST API search.

        Args:
            guild_id: Guild to search
            query: Search query string
            channel_id: Limit to this channel
            author_id: Limit to this author
            limit: Max results (max 25)

        Returns:
            {"messages": [{"id", "content", "author", "channel_id", "timestamp"}]}
        """
        channel_obj = api.get_channel("discord")
        if not channel_obj:
            return {"error": "Discord channel not available"}
        try:
            client = channel_obj._get_client()
            guild = client.get_guild(int(guild_id)) or await client.fetch_guild(int(guild_id))
            results = []
            search_ch = None
            if channel_id:
                search_ch = client.get_channel(int(channel_id)) or await client.fetch_channel(int(channel_id))
            channels = [search_ch] if search_ch else guild.text_channels
            for ch in channels[:5]:
                async for msg in ch.history(limit=100):
                    if query.lower() in (msg.content or "").lower():
                        if author_id and str(msg.author.id) != author_id:
                            continue
                        results.append({
                            "id": str(msg.id),
                            "content": msg.content,
                            "author": msg.author.display_name,
                            "channel_id": str(msg.channel.id),
                            "timestamp": msg.created_at.isoformat(),
                        })
                        if len(results) >= limit:
                            break
                if len(results) >= limit:
                    break
            return {"messages": results}
        except Exception as e:
            return {"error": str(e)}
