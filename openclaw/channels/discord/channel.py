"""Discord channel implementation — aligned with TS monitorDiscordProvider/sendMessageDiscord"""
from __future__ import annotations


import asyncio
import base64
import logging
import time
from typing import Any

from ..base import ChannelCapabilities, ChannelPlugin, ChatAttachment, InboundMessage

logger = logging.getLogger(__name__)

# Dedup TTL in seconds — mirrors TS dedup window
_DEDUP_TTL = 30.0

# Reconnect backoff config
_RECONNECT_INITIAL = 2.0
_RECONNECT_MAX = 60.0
_RECONNECT_FACTOR = 2.0


class DiscordChannel(ChannelPlugin):
    """Discord bot channel — fully aligned with TS discordPlugin"""

    def __init__(self):
        super().__init__()
        self.id = "discord"
        self.label = "Discord"
        self.capabilities = ChannelCapabilities(
            chat_types=["direct", "group", "channel"],
            supports_media=True,
            supports_reactions=True,
            supports_threads=True,
            supports_polls=True,
            native_commands=True,
            supports_reply=True,
        )
        self._client: Any | None = None
        self._bot_token: str | None = None
        self._guild_id: str | None = None
        self._media_max_mb: int = 8
        # Message dedup: message_id -> expiry_time
        self._dedupe: dict[str, float] = {}

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    async def start(self, config: dict[str, Any]) -> None:
        """Start Discord bot"""
        self._bot_token = config.get("token") or config.get("botToken") or config.get("bot_token")
        self._guild_id = config.get("guildId") or config.get("guild_id")
        self._media_max_mb = int(config.get("mediaMaxMb") or config.get("media_max_mb") or 8)

        if not self._bot_token:
            raise ValueError("Discord bot token not provided (config key: token)")

        logger.info("Starting Discord channel...")

        try:
            import discord
            from discord.ext import commands

            intents = discord.Intents.default()
            intents.message_content = True
            intents.messages = True
            intents.reactions = True
            intents.guilds = True

            self._client = commands.Bot(command_prefix="!", intents=intents)

            @self._client.event
            async def on_ready():
                logger.info(f"Discord bot logged in as {self._client.user}")
                self._running = True

            @self._client.event
            async def on_message(message):
                if message.author == self._client.user:
                    return
                if message.content.startswith("!"):
                    return
                await self._handle_discord_message(message)

            @self._client.event
            async def on_reaction_add(reaction, user):
                if user == self._client.user:
                    return
                await self._handle_reaction(reaction, user, "add")

            @self._client.event
            async def on_reaction_remove(reaction, user):
                if user == self._client.user:
                    return
                await self._handle_reaction(reaction, user, "remove")

            @self._client.event
            async def on_disconnect():
                logger.warning("[discord] Bot disconnected")
                self._running = False

            @self._client.event
            async def on_resumed():
                logger.info("[discord] Bot connection resumed")
                self._running = True

            asyncio.create_task(self._run_with_reconnect())

        except ImportError:
            logger.error("discord.py not installed. Install with: pip install discord.py")
            raise

    async def _run_with_reconnect(self) -> None:
        """Run Discord bot with exponential backoff reconnect — mirrors TS botconnect logic"""
        backoff = _RECONNECT_INITIAL
        while True:
            try:
                await self._client.start(self._bot_token)
            except Exception as e:
                logger.warning(f"[discord] Connection error: {e}, reconnecting in {backoff:.1f}s")
                await asyncio.sleep(backoff)
                backoff = min(backoff * _RECONNECT_FACTOR, _RECONNECT_MAX)
                try:
                    self._client = self._client.__class__(
                        command_prefix=self._client.command_prefix,
                        intents=self._client.intents,
                    )
                except Exception:
                    pass
                continue
            break

    async def stop(self) -> None:
        """Stop Discord bot"""
        if self._client:
            logger.info("Stopping Discord channel...")
            await self._client.close()
        self._running = False

    # -------------------------------------------------------------------------
    # Message dedup
    # -------------------------------------------------------------------------

    def _is_duplicate(self, message_id: str) -> bool:
        """Check and register dedup for a message ID — mirrors TS dedupe logic"""
        now = time.monotonic()
        # Cleanup expired entries
        expired = [k for k, v in self._dedupe.items() if now > v]
        for k in expired:
            del self._dedupe[k]
        if message_id in self._dedupe:
            return True
        self._dedupe[message_id] = now + _DEDUP_TTL
        return False

    # -------------------------------------------------------------------------
    # Inbound handling
    # -------------------------------------------------------------------------

    async def _handle_discord_message(self, message: Any) -> None:
        """Handle incoming Discord message with dedup and attachment handling"""
        msg_id = str(message.id)
        if self._is_duplicate(msg_id):
            return

        import discord

        chat_type = "direct" if isinstance(message.channel, discord.DMChannel) else "group"
        thread_id: str | None = None
        if isinstance(message.channel, discord.Thread):
            thread_id = str(message.channel.id)
            chat_type = "group"

        # Download attachments as base64 — mirrors TS attachment handling
        attachments: list[ChatAttachment] = []
        for att in message.attachments:
            try:
                max_bytes = self._media_max_mb * 1024 * 1024
                if att.size and att.size > max_bytes:
                    logger.debug(f"[discord] Skipping large attachment {att.filename} ({att.size} bytes)")
                    continue
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(att.url) as resp:
                        data = await resp.read()
                content_b64 = base64.b64encode(data).decode()
                attachments.append(ChatAttachment(
                    type=_mime_to_type(att.content_type or ""),
                    mime_type=att.content_type,
                    content=content_b64,
                    filename=att.filename,
                    size=att.size,
                ))
            except Exception as e:
                logger.warning(f"[discord] Failed to download attachment: {e}")

        inbound = InboundMessage(
            channel_id=self.id,
            message_id=msg_id,
            sender_id=str(message.author.id),
            sender_name=message.author.display_name or str(message.author.name),
            chat_id=str(message.channel.id),
            chat_type=chat_type,
            text=message.content,
            timestamp=message.created_at.isoformat(),
            reply_to=str(message.reference.message_id) if message.reference else None,
            metadata={
                "guild_id": str(message.guild.id) if message.guild else None,
                "channel_name": message.channel.name if hasattr(message.channel, "name") else None,
                "thread_id": thread_id,
            },
            attachments=attachments,
        )

        await self._handle_message(inbound)

    async def _handle_reaction(self, reaction: Any, user: Any, action: str) -> None:
        """Handle reaction add/remove — mirrors TS reaction event handling"""
        msg_id = str(reaction.message.id)
        emoji_str = str(reaction.emoji)

        inbound = InboundMessage(
            channel_id=self.id,
            message_id=f"{msg_id}-reaction-{action}",
            sender_id=str(user.id),
            sender_name=user.display_name if hasattr(user, "display_name") else str(user.name),
            chat_id=str(reaction.message.channel.id),
            chat_type="direct" if not hasattr(reaction.message.guild, "id") else "group",
            text="",
            timestamp=reaction.message.created_at.isoformat(),
            metadata={
                "type": "reaction",
                "action": action,
                "emoji": emoji_str,
                "target_message_id": msg_id,
            },
        )

        await self._handle_message(inbound)

    # -------------------------------------------------------------------------
    # Outbound
    # -------------------------------------------------------------------------

    async def send_text(
        self,
        target: str,
        text: str,
        reply_to: str | None = None,
        thread_id: str | None = None,
    ) -> str:
        """Send text message, optionally in a thread — mirrors TS sendMessageDiscord"""
        if not self._client:
            raise RuntimeError("Discord channel not started")

        try:
            channel_id = int(thread_id or target)
            channel = self._client.get_channel(channel_id)
            if not channel:
                channel = await self._client.fetch_channel(channel_id)

            import discord

            if reply_to:
                ref = discord.MessageReference(message_id=int(reply_to), channel_id=channel_id)
                message = await channel.send(text, reference=ref)
            else:
                message = await channel.send(text)

            return str(message.id)

        except Exception as e:
            logger.error(f"Failed to send Discord message: {e}", exc_info=True)
            raise

    async def send_media(
        self,
        target: str,
        media_url: str,
        media_type: str,
        caption: str | None = None,
        thread_id: str | None = None,
    ) -> str:
        """Send media via URL or file — mirrors TS sendMessageDiscord with files"""
        if not self._client:
            raise RuntimeError("Discord channel not started")

        try:
            import discord

            channel_id = int(thread_id or target)
            channel = self._client.get_channel(channel_id)
            if not channel:
                channel = await self._client.fetch_channel(channel_id)

            if media_url.startswith("http"):
                # Download and re-upload
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(media_url) as resp:
                        data = await resp.read()
                import io
                filename = media_url.split("/")[-1] or "media"
                message = await channel.send(content=caption, file=discord.File(io.BytesIO(data), filename=filename))
            else:
                message = await channel.send(content=caption, file=discord.File(media_url))

            return str(message.id)

        except Exception as e:
            logger.error(f"Failed to send Discord media: {e}", exc_info=True)
            raise

    async def send_poll(
        self,
        target: str,
        question: str,
        answers: list[str],
        duration_hours: int = 24,
    ) -> str:
        """Send a Discord poll — mirrors TS Discord Poll API"""
        if not self._client:
            raise RuntimeError("Discord channel not started")

        try:
            import discord

            channel_id = int(target)
            channel = self._client.get_channel(channel_id)
            if not channel:
                channel = await self._client.fetch_channel(channel_id)

            poll = discord.Poll(
                question=discord.PollMedia(text=question),
                duration=duration_hours,
            )
            for answer in answers:
                poll.add_answer(text=answer)

            message = await channel.send(poll=poll)
            return str(message.id)

        except Exception as e:
            logger.error(f"Failed to send Discord poll: {e}", exc_info=True)
            raise


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mime_to_type(mime: str) -> str:
    """Map MIME type to ChatAttachment type string"""
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("audio/"):
        return "audio"
    if mime.startswith("video/"):
        return "video"
    return "file"
