"""FeishuChannel — main channel plugin class.

Integrates all Feishu sub-modules and implements the ChannelPlugin interface.

Mirrors TypeScript: extensions/feishu/src/channel.ts + index.ts
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..base import ChannelCapabilities, ChannelPlugin, InboundMessage
from .accounts import get_default_account, resolve_feishu_accounts
from .client import create_feishu_client
from .monitor import start_feishu_monitor
from .outbound import FeishuOutboundAdapter, resolve_receive_id_type
from .send import edit_feishu_message

logger = logging.getLogger(__name__)


class FeishuChannel(ChannelPlugin):
    """
    Feishu/Lark channel for openclaw-python.

    Supports:
      - WebSocket (default) and Webhook connection modes
      - DM + group messaging
      - Streaming cards (CardKit API)
      - Typing indicator (Typing emoji reaction)
      - Multi-account configuration
      - Media upload/download
      - @mention handling and group policies

    Configuration (channels.feishu in openclaw.json):
      appId, appSecret, domain, connectionMode, dmPolicy, groupPolicy,
      requireMention, allowFrom, groupAllowFrom, renderMode, streaming, ...
    """

    def __init__(self) -> None:
        super().__init__()
        self.id = "feishu"
        self.label = "Feishu"
        self.capabilities = ChannelCapabilities(
            chat_types=["direct", "group"],
            supports_media=True,
            supports_reactions=True,
            supports_threads=True,
            supports_edit=True,
            supports_reply=True,
            block_streaming=False,   # streaming cards supported
        )

        self._cfg: dict[str, Any] = {}
        self._stop_event: asyncio.Event | None = None
        self._monitor_task: asyncio.Task | None = None
        self._default_outbound: FeishuOutboundAdapter | None = None
        # {message_id: reaction_id} — tracks pending "Typing" reactions
        self._typing_reactions: dict[str, str] = {}
        # Channel silence watchdog
        self._heartbeat_monitor = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def on_start(self, config: dict[str, Any]) -> None:
        """Start all account monitors."""
        self._cfg = config
        self._stop_event = asyncio.Event()

        if not self._message_handler:
            raise RuntimeError("FeishuChannel: message handler not set before start()")

        # Validate at least one account is configured
        accounts = resolve_feishu_accounts(config)
        if not accounts:
            logger.warning(
                "[feishu] No valid credentials found. "
                "Set channels.feishu.appId and channels.feishu.appSecret."
            )
            return

        # Set up default outbound adapter (uses first/default account)
        default_account = get_default_account(config)
        if default_account:
            client = create_feishu_client(default_account)
            self._default_outbound = FeishuOutboundAdapter(client, default_account)

        # Channel silence watchdog — mirrors TS DEFAULT_STALE_EVENT_THRESHOLD_MS (30 min)
        try:
            from openclaw.auto_reply.heartbeat_monitor import HeartbeatMonitor
            from openclaw.infra.heartbeat_wake import request_heartbeat_now

            async def _on_feishu_silence(channel_id: str) -> None:
                logger.info("Feishu channel silence detected — requesting heartbeat wake")
                request_heartbeat_now(reason="wake", agent_id=None, session_key=None)

            self._heartbeat_monitor = HeartbeatMonitor(
                channel_id=self.id,
                timeout_seconds=30 * 60,
                health_check_callback=_on_feishu_silence,
            )
            await self._heartbeat_monitor.start()
        except Exception as _exc:
            logger.debug("Feishu heartbeat monitor init failed: %s", _exc)
            self._heartbeat_monitor = None

        # Wrap message handler to reset the silence watchdog on each message
        _base_handler = self._message_handler
        _monitor_ref = self._heartbeat_monitor

        async def _monitored_handler(msg: "InboundMessage") -> None:
            if _monitor_ref is not None:
                _monitor_ref.reset()
            await _base_handler(msg)

        # Start monitor in background
        self._monitor_task = asyncio.create_task(
            start_feishu_monitor(
                config,
                _monitored_handler,
                self.id,
                self._stop_event,
            ),
            name="feishu-monitor",
        )

        logger.info("[feishu] Channel started with %d account(s)", len(accounts))

    async def on_stop(self) -> None:
        """Stop all account monitors."""
        if self._stop_event:
            self._stop_event.set()

        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await asyncio.wait_for(self._monitor_task, timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass

        if self._heartbeat_monitor and getattr(self._heartbeat_monitor, "is_running", lambda: False)():
            try:
                await self._heartbeat_monitor.stop()
            except Exception:
                pass
        self._heartbeat_monitor = None

        self._monitor_task = None
        self._stop_event = None
        logger.info("[feishu] Channel stopped")

    # ------------------------------------------------------------------
    # ChannelPlugin abstract methods
    # ------------------------------------------------------------------

    async def send_text(
        self,
        target: str,
        text: str,
        reply_to: str | None = None,
    ) -> str:
        """
        Send a text message to a Feishu chat or user.

        target: chat_id (oc_xxx), open_id (ou_xxx), or user_id
        reply_to: message_id to reply to (optional)
        Returns sent message_id.
        """
        if not self._default_outbound:
            raise RuntimeError("FeishuChannel not started or no valid account")

        reply_in_thread = False
        # Check if we should reply in thread (from metadata stored during inbound)
        if reply_to and self._cfg:
            default_account = get_default_account(self._cfg)
            if default_account:
                reply_in_thread = default_account.reply_in_thread == "enabled"

        return await self._default_outbound.send_text(
            target,
            text,
            reply_to=reply_to,
            reply_in_thread=reply_in_thread,
        )

    async def send_media(
        self,
        target: str,
        media_url: str,
        media_type: str,
        caption: str | None = None,
        reply_to: str | None = None,
    ) -> str:
        """
        Send a media file to Feishu.

        Accepts local file paths (agent-generated files) and HTTP/HTTPS URLs.
        Reads local files directly; downloads remote URLs via aiohttp.
        reply_to is accepted for API parity.
        """
        if not self._default_outbound:
            raise RuntimeError("FeishuChannel not started or no valid account")

        import os
        from pathlib import Path

        # Feishu upload size limit: 30 MB for files, 10 MB for images
        _MAX_BYTES = 30 * 1024 * 1024

        is_local = not media_url.startswith(("http://", "https://", "file://"))

        if is_local:
            file_path = Path(media_url).expanduser()
            if not file_path.exists() or not file_path.is_file():
                raise RuntimeError(f"Local file not found: {media_url}")
            file_size = file_path.stat().st_size
            if file_size > _MAX_BYTES:
                size_mb = file_size / (1024 * 1024)
                raise ValueError(
                    f"File too large for Feishu ({size_mb:.1f} MB > 30 MB limit): {file_path.name}"
                )
            loop = asyncio.get_running_loop()
            data = await loop.run_in_executor(None, file_path.read_bytes)
            filename = file_path.name
        else:
            import aiohttp
            async with aiohttp.ClientSession() as http_session:
                async with http_session.get(media_url) as resp:
                    if resp.status != 200:
                        raise RuntimeError(
                            f"Failed to download media from {media_url}: HTTP {resp.status}"
                        )
                    data = await resp.read()
            filename = Path(media_url.split("?")[0]).name or "attachment"

        return await self._default_outbound.send_media(
            target,
            data,
            filename,
            media_type=media_type,
            caption=caption,
            reply_to=reply_to,
        )

    # ------------------------------------------------------------------
    # Typing indicator — "Typing" emoji reaction (no native typing API)
    # ------------------------------------------------------------------

    async def send_typing(self, target: str, message_id: str | None = None) -> None:
        """
        Add a 'Typing' emoji reaction to the message to signal processing.

        Feishu has no native typing-status API, so we use an emoji reaction
        as a visual indicator.  The reaction is added once (idempotent) and
        must be removed by calling stop_typing() when processing is done.
        """
        if not message_id or not self._default_outbound:
            return
        if message_id in self._typing_reactions:
            return  # already added — idempotent
        from .typing import _add_reaction
        client = self._default_outbound._client
        account_id = self._default_outbound._account.account_id
        reaction_id = await _add_reaction(client, message_id, account_id)
        if reaction_id:
            self._typing_reactions[message_id] = reaction_id

    async def stop_typing(self, target: str, message_id: str | None = None) -> None:
        """Remove the 'Typing' reaction once processing is done."""
        if not message_id:
            return
        reaction_id = self._typing_reactions.pop(message_id, None)
        if reaction_id and self._default_outbound:
            from .typing import _remove_reaction
            client = self._default_outbound._client
            account_id = self._default_outbound._account.account_id
            await _remove_reaction(client, message_id, reaction_id, account_id)

    # ------------------------------------------------------------------
    # Extended capabilities
    # ------------------------------------------------------------------

    async def edit_message(self, message_id: str, new_text: str) -> bool:
        """Edit an existing Feishu message (24-hour window)."""
        if not self._default_outbound:
            return False
        client = self._default_outbound._client
        default_account = get_default_account(self._cfg) if self._cfg else None
        render_mode = default_account.render_mode if default_account else "auto"
        return await edit_feishu_message(client, message_id, text=new_text, render_mode=render_mode)

    async def get_account_for_chat(self, chat_id: str) -> Any | None:
        """Return the resolved account for a given chat_id (default account)."""
        return get_default_account(self._cfg) if self._cfg else None

    def get_outbound_for_account(self, account_id: str) -> FeishuOutboundAdapter | None:
        """Get outbound adapter for a specific account."""
        if not self._cfg:
            return None
        from .accounts import resolve_feishu_account
        account = resolve_feishu_account(self._cfg, account_id)
        if not account:
            return None
        client = create_feishu_client(account)
        return FeishuOutboundAdapter(client, account)

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def check_health(self) -> tuple[bool, str]:
        if not self._running:
            return False, "Channel not running"

        if self._monitor_task and self._monitor_task.done():
            exc = self._monitor_task.exception()
            if exc:
                return False, f"Monitor failed: {exc}"

        accounts = resolve_feishu_accounts(self._cfg) if self._cfg else []
        if not accounts:
            return False, "No valid accounts configured"

        # Probe Feishu API — mirrors TS checkHealth() calling bot.info
        from .accounts import get_default_account
        default = get_default_account(self._cfg) if self._cfg else None
        if default:
            try:
                import asyncio as _asyncio
                client = create_feishu_client(default)
                from lark_oapi.api.bot.v3 import GetBotInfoRequest
                loop = _asyncio.get_running_loop()
                request = GetBotInfoRequest.builder().build()
                response = await _asyncio.wait_for(
                    loop.run_in_executor(None, lambda: client.bot.v3.bot.get(request)),
                    timeout=10.0,
                )
                if not response.success():
                    return False, f"Feishu API probe failed: code={response.code} msg={response.msg}"
            except Exception as probe_err:
                return False, f"Feishu API probe exception: {probe_err}"

        return True, f"OK ({len(accounts)} account(s))"

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        if self._cfg:
            accounts = resolve_feishu_accounts(self._cfg)
            result["feishu"] = {
                "accounts": [a.account_id for a in accounts],
                "connection_modes": [a.connection_mode for a in accounts],
            }
        return result
