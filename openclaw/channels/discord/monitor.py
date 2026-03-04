"""
Discord gateway monitor — bot lifecycle, event routing, reconnect.
Mirrors src/discord/monitor/provider.ts.

Responsibilities:
  - Create discord.Client with correct Intents
  - Register all event listeners (on_message, on_reaction_add/remove, on_interaction)
  - Mount CommandTree (slash commands)
  - Initialize presence on bot ready
  - Initialize VoiceManager and auto-join voice channels
  - Reconnect with exponential backoff (2s → 60s)
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)

_RECONNECT_INITIAL = 2.0
_RECONNECT_MAX = 60.0
_RECONNECT_FACTOR = 2.0


class DiscordMonitor:
    """
    Manages the lifecycle of a single Discord bot account.
    Encapsulates the discord.Client, command tree, inbound processor,
    voice manager, and reconnect logic.
    """

    def __init__(
        self,
        account: Any,
        on_inbound: Callable[[Any], Awaitable[None]],
        on_command: Callable[[str, Any, dict], Awaitable[None]],
        persist_dir: Path | None = None,
        tts_fn: Callable[[str], Awaitable[str | None]] | None = None,
    ) -> None:
        from .dedup import DiscordDedup
        from .inbound import DiscordInboundProcessor
        from .policy import PairingStore
        from .threading import ThreadBindingStore

        self._account = account
        self._on_inbound = on_inbound
        self._on_command = on_command
        self._persist_dir = persist_dir
        self._tts_fn = tts_fn

        self._client: Any | None = None
        self._tree: Any | None = None
        self._voice_manager: Any | None = None
        self._stop_event = asyncio.Event()

        # Per-channel message queue — serializes messages within the same channel
        # but allows different channels to proceed in parallel (mirrors TS KeyedAsyncQueue).
        self._channel_queue: dict[str, asyncio.Task] = {}

        # Sub-components
        self._dedup = DiscordDedup(persist_dir, account.account_id)
        self._pairing = PairingStore(persist_dir, account.account_id)
        self._thread_bindings = ThreadBindingStore(
            persist_dir,
            account.account_id,
            idle_hours=account.thread_bindings.idle_hours,
            max_age_hours=account.thread_bindings.max_age_hours,
        )

        self._inbound_processor = DiscordInboundProcessor(
            account=account,
            dispatch=on_inbound,
            dedup=self._dedup,
            pairing_store=self._pairing,
            thread_bindings=self._thread_bindings,
            send_pairing_dm=self._send_pairing_dm,
        )

    # ---------------------------------------------------------------------------
    # Client construction
    # ---------------------------------------------------------------------------

    def _build_client(self) -> Any:
        import discord

        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True
        intents.reactions = True
        intents.guilds = True
        intents.dm_messages = True

        # Optional privileged intents (must be enabled in Discord Developer Portal)
        if self._account.intents.presence:
            intents.presences = True
        if self._account.intents.guild_members:
            intents.members = True

        client = discord.Client(intents=intents)
        return client

    # ---------------------------------------------------------------------------
    # Start / Stop
    # ---------------------------------------------------------------------------

    async def start(self) -> None:
        self._stop_event.clear()
        backoff = _RECONNECT_INITIAL

        while not self._stop_event.is_set():
            try:
                self._client = self._build_client()
                self._register_events()
                # Voice must be set up BEFORE commands so that _setup_commands
                # can pass the voice_manager into the command tree (including /voice).
                if self._account.voice.enabled:
                    self._setup_voice()
                self._setup_commands()

                logger.info("[discord][monitor] Connecting account '%s'...", self._account.account_id)
                await self._client.start(self._account.token)
                # start() returns when the bot disconnects — reset backoff on clean exit
                backoff = _RECONNECT_INITIAL

            except asyncio.CancelledError:
                break
            except Exception as exc:
                if self._stop_event.is_set():
                    break
                logger.warning(
                    "[discord][monitor] Connection error for '%s': %s — reconnecting in %.1fs",
                    self._account.account_id,
                    exc,
                    backoff,
                )
                try:
                    await asyncio.wait_for(
                        asyncio.shield(self._stop_event.wait()),
                        timeout=backoff,
                    )
                    break  # stop was requested during wait
                except asyncio.TimeoutError:
                    pass
                backoff = min(backoff * _RECONNECT_FACTOR, _RECONNECT_MAX)

    async def stop(self) -> None:
        self._stop_event.set()
        if self._client:
            try:
                await self._client.close()
            except Exception:
                pass

    def get_client(self) -> Any | None:
        return self._client

    # ---------------------------------------------------------------------------
    # Event registration
    # ---------------------------------------------------------------------------

    def _register_events(self) -> None:
        client = self._client
        account = self._account

        @client.event
        async def on_ready() -> None:
            logger.info(
                "[discord][monitor] Logged in as %s (account: %s)",
                client.user,
                account.account_id,
            )
            # Set initial presence
            from .presence import init_presence_from_config
            await init_presence_from_config(client, account)

            # Sync slash commands
            if self._tree:
                await _safe_sync_commands(self._tree, client)

            # Auto-join voice channels
            if self._voice_manager:
                await self._voice_manager.auto_join_on_ready()

        @client.event
        async def on_message(message: Any) -> None:
            # Release Discord's dispatch lane immediately, but serialize messages
            # within the same channel to preserve ordering.  Different channels
            # proceed in parallel so one slow channel doesn't block others.
            # Mirrors TS DiscordMessageListener with KeyedAsyncQueue.
            channel_id = str(getattr(message, "channel", None) and getattr(message.channel, "id", None) or "")
            self._enqueue_channel_message(
                channel_id,
                lambda: self._inbound_processor.handle_message(message, client),
            )

        @client.event
        async def on_reaction_add(reaction: Any, user: Any) -> None:
            if user == client.user:
                return
            # Build a minimal payload-like object for the inbound processor
            payload = _ReactionPayload(
                user_id=user.id,
                channel_id=reaction.message.channel.id,
                guild_id=getattr(reaction.message.guild, "id", None),
                emoji=reaction.emoji,
                message_id=reaction.message.id,
            )
            await self._inbound_processor.handle_reaction(payload, "add", client)

        @client.event
        async def on_reaction_remove(reaction: Any, user: Any) -> None:
            if user == client.user:
                return
            payload = _ReactionPayload(
                user_id=user.id,
                channel_id=reaction.message.channel.id,
                guild_id=getattr(reaction.message.guild, "id", None),
                emoji=reaction.emoji,
                message_id=reaction.message.id,
            )
            await self._inbound_processor.handle_reaction(payload, "remove", client)

        @client.event
        async def on_interaction(interaction: Any) -> None:
            # Route to the command tree for slash commands
            if self._tree:
                await self._tree.process_interaction(interaction)

        @client.event
        async def on_disconnect() -> None:
            logger.warning("[discord][monitor] Account '%s' disconnected", account.account_id)

        @client.event
        async def on_resumed() -> None:
            logger.info("[discord][monitor] Account '%s' connection resumed", account.account_id)

    # ---------------------------------------------------------------------------
    # Per-channel message serialization (mirrors TS KeyedAsyncQueue)
    # ---------------------------------------------------------------------------

    def _enqueue_channel_message(
        self,
        channel_id: str,
        fn: Callable[[], Awaitable[None]],
    ) -> None:
        """Enqueue a message handler for a specific channel.

        Messages within the same channel are serialized; different channels run in parallel.
        Mirrors TS DiscordMessageListener.channelQueue (KeyedAsyncQueue).
        """
        prev_task = self._channel_queue.get(channel_id)

        async def _run() -> None:
            if prev_task and not prev_task.done():
                try:
                    await prev_task
                except Exception:
                    pass
            try:
                await fn()
            except Exception as exc:
                logger.error(
                    "[discord][monitor] message handler failed for channel=%s: %s",
                    channel_id,
                    exc,
                )

        task = asyncio.ensure_future(_run())
        self._channel_queue[channel_id] = task

        # Clean up completed tasks to avoid unbounded dict growth
        done_keys = [k for k, t in self._channel_queue.items() if t.done() and k != channel_id]
        for k in done_keys:
            del self._channel_queue[k]

    # ---------------------------------------------------------------------------
    # Command setup
    # ---------------------------------------------------------------------------

    def _setup_commands(self) -> None:
        from .commands import setup_command_tree
        self._tree = setup_command_tree(
            client=self._client,
            account=self._account,
            on_command=self._on_command,
            voice_manager=self._voice_manager,
            thread_bindings=self._thread_bindings,
        )

    # ---------------------------------------------------------------------------
    # Voice setup
    # ---------------------------------------------------------------------------

    def _setup_voice(self) -> None:
        from .voice import VoiceManager

        async def on_transcript(guild_id: str, channel_id: str, text: str) -> None:
            from ..base import InboundMessage
            inbound = InboundMessage(
                channel_id="discord",
                message_id=f"voice-{guild_id}-{channel_id}-{id(text)}",
                sender_id="",
                sender_name="",
                chat_id=channel_id,
                chat_type="channel",
                text=text,
                timestamp="",
                metadata={"guild_id": guild_id, "type": "voice_transcript"},
            )
            await self._on_inbound(inbound)

        self._voice_manager = VoiceManager(
            client=self._client,
            account=self._account,
            on_transcript=on_transcript,
            tts_fn=self._tts_fn,
            persist_dir=self._persist_dir,
        )

    # ---------------------------------------------------------------------------
    # Pairing DM helper
    # ---------------------------------------------------------------------------

    async def _send_pairing_dm(
        self,
        channel: Any,
        user_id: str,
        username: str,
        pairing_code: str,
    ) -> None:
        """Send a pairing code to the user who DMed the bot."""
        try:
            await channel.send(
                f"Hi **{username}**! This bot requires approval before you can use it.\n\n"
                f"Your pairing code is: `{pairing_code}`\n\n"
                "Please share this code with an administrator to get access.",
            )
        except Exception as exc:
            logger.debug("[discord][monitor] Failed to send pairing DM: %s", exc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _ReactionPayload:
    """Minimal reaction payload for the inbound processor."""

    def __init__(
        self,
        user_id: Any,
        channel_id: Any,
        guild_id: Any | None,
        emoji: Any,
        message_id: Any,
    ) -> None:
        self.user_id = user_id
        self.channel_id = channel_id
        self.guild_id = guild_id
        self.emoji = emoji
        self.message_id = message_id


async def _safe_sync_commands(tree: Any, client: Any) -> None:
    try:
        from .commands import sync_commands
        await sync_commands(tree, client)
    except Exception as exc:
        logger.warning("[discord][monitor] Command sync failed: %s", exc)


# ---------------------------------------------------------------------------
# Multi-account monitor launcher
# ---------------------------------------------------------------------------

async def start_discord_monitors(
    accounts: list[Any],
    on_inbound: Callable[[Any], Awaitable[None]],
    on_command: Callable[[str, Any, dict], Awaitable[None]] | None = None,
    persist_dir: Path | None = None,
    tts_fn: Callable[[str], Awaitable[str | None]] | None = None,
) -> list[DiscordMonitor]:
    """
    Start monitors for all configured Discord accounts.
    Returns the list of DiscordMonitor instances (for later stop()).
    """
    async def _noop_command(name: str, interaction: Any, data: dict) -> None:
        pass

    cmd_handler = on_command or _noop_command
    monitors: list[DiscordMonitor] = []

    for account in accounts:
        monitor = DiscordMonitor(
            account=account,
            on_inbound=on_inbound,
            on_command=cmd_handler,
            persist_dir=persist_dir,
            tts_fn=tts_fn,
        )
        monitors.append(monitor)
        asyncio.create_task(
            monitor.start(),
            name=f"discord_monitor_{account.account_id}",
        )
        logger.info("[discord][monitor] Started account '%s'", account.account_id)

    return monitors
