"""
Enhanced Telegram channel with connection management.

Extends TelegramChannel with automatic reconnection, health checking,
and streaming state management — all pairing / dm_policy / allowlist
logic is inherited from TelegramChannel.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..connection import ReconnectConfig
from .channel import TelegramChannel

logger = logging.getLogger(__name__)


class EnhancedTelegramChannel(TelegramChannel):
    """
    Telegram channel with added:
    - Automatic reconnection via ConnectionManager
    - Health checking
    - Connection metrics
    - Streaming text update (edit-in-place) support

    All pairing, dm_policy, allowlist, group-policy, and command
    handling is inherited from TelegramChannel.
    """

    def __init__(self) -> None:
        super().__init__()  # TelegramChannel sets up id, capabilities, and all state

        # Streaming-edit state: {session_id: {"msg_id": str, "full_content": str}}
        self._streaming_states: dict[str, dict] = {}

        # Wrap with connection manager for auto-reconnect
        self._setup_connection_manager(
            reconnect_config=ReconnectConfig(
                enabled=True,
                max_attempts=10,
                base_delay=2.0,
                max_delay=300.0,
                exponential_backoff=True,
            )
        )

    # -------------------------------------------------------------------------
    # Connection management hooks (called by ConnectionManager)
    # -------------------------------------------------------------------------

    async def _do_connect(self) -> None:
        """Delegate to TelegramChannel's full start logic."""
        if self._config:
            await TelegramChannel.start(self, self._config)

    async def _do_disconnect(self) -> None:
        """Delegate to TelegramChannel's full stop logic."""
        await TelegramChannel.stop(self)

    # -------------------------------------------------------------------------
    # Overridden lifecycle — adds connection manager + health checker
    # -------------------------------------------------------------------------

    async def start(self, config: dict[str, Any]) -> None:
        """Start with reconnection support."""
        self._config = config
        self._bot_token = config.get("botToken") or config.get("bot_token")

        if not self._bot_token:
            raise ValueError("Telegram bot token not provided in config")

        logger.info(f"[{self.id}] Starting Enhanced Telegram channel...")

        if self._connection_manager:
            success = await self._connection_manager.connect()
            if success:
                self._setup_health_checker(interval=60.0, timeout=15.0)
                if self._health_checker:
                    self._health_checker.start()
        else:
            await self._do_connect()

    async def stop(self) -> None:
        """Stop and tear down health checker + connection manager."""
        logger.info(f"[{self.id}] Stopping Enhanced Telegram channel...")

        if self._health_checker:
            self._health_checker.stop()

        if self._connection_manager:
            await self._connection_manager.disconnect()
        else:
            await self._do_disconnect()

    # -------------------------------------------------------------------------
    # Health check
    # -------------------------------------------------------------------------

    async def _health_check(self) -> bool:
        """Check Telegram connectivity by fetching bot info."""
        if not self._app or not self._running:
            return False
        try:
            me = await asyncio.wait_for(self._app.bot.get_me(), timeout=10.0)
            return me is not None
        except Exception as e:
            logger.warning(f"[{self.id}] Health check failed: {e}")
            return False

    # -------------------------------------------------------------------------
    # Streaming edit-in-place support (not in base TelegramChannel)
    # -------------------------------------------------------------------------

    async def on_event(self, event: Any) -> None:
        """
        Handle agent streaming events to edit Telegram messages in-place.
        Mirrors TS draft-stream behaviour: accumulate delta text and keep
        editing the same message until the turn is complete.
        """
        event_type = str(getattr(event, "type", "")).lower()

        if event_type == "eventtype.agent_turn_complete":
            self._streaming_states.pop(getattr(event, "session_id", None), None)
            return

        if event_type != "eventtype.agent_text":
            return

        text = (getattr(event, "data", {}) or {}).get("delta", {}).get("text", "")
        session_id = getattr(event, "session_id", None)

        if not text or not session_id or not hasattr(self, "_last_chat_id"):
            return

        if session_id not in self._streaming_states:
            # First chunk — send a new message and record its ID
            msg_id = await self.send_text(self._last_chat_id, text)
            self._streaming_states[session_id] = {
                "msg_id": msg_id,
                "full_content": text,
            }
        else:
            state = self._streaming_states[session_id]
            state["full_content"] += text
            if self._app:
                try:
                    await self._app.bot.edit_message_text(
                        chat_id=int(self._last_chat_id),
                        message_id=int(state["msg_id"]),
                        text=state["full_content"],
                    )
                except Exception as e:
                    if "Message is not modified" not in str(e):
                        logger.warning(f"[{self.id}] Stream edit failed: {e}")
