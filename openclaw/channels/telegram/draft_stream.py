"""Telegram draft streaming with throttling and edits

Provides live preview of agent responses by creating a message and editing it
as new content becomes available. Includes throttling to avoid API rate limits.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)

TELEGRAM_STREAM_MAX_CHARS = 4096
DEFAULT_THROTTLE_MS = 1000


class TelegramDraftStream:
    """Draft stream for Telegram with throttling and edit support"""
    
    def __init__(
        self,
        bot_api: Any,
        chat_id: int | str,
        max_chars: int | None = None,
        thread_params: dict | None = None,
        reply_to_message_id: int | None = None,
        throttle_ms: int | None = None,
        min_initial_chars: int | None = None,
    ):
        """
        Initialize draft stream
        
        Args:
            bot_api: Telegram bot API instance
            chat_id: Target chat ID
            max_chars: Maximum characters (default 4096)
            thread_params: Thread parameters for forum topics
            reply_to_message_id: Message ID to reply to
            throttle_ms: Throttle interval in milliseconds (default 1000)
            min_initial_chars: Minimum chars before sending first message (debounce)
        """
        self._api = bot_api
        self._chat_id = chat_id
        self._max_chars = min(max_chars or TELEGRAM_STREAM_MAX_CHARS, TELEGRAM_STREAM_MAX_CHARS)
        self._thread_params = thread_params or {}
        self._reply_to_message_id = reply_to_message_id
        self._throttle_ms = max(250, throttle_ms or DEFAULT_THROTTLE_MS)
        self._min_initial_chars = min_initial_chars
        
        self._stream_message_id: int | None = None
        self._last_sent_text = ""
        self._stopped = False
        self._is_final = False
        
        self._pending_text = ""
        self._last_sent_at = 0.0
        self._timer: asyncio.Task | None = None
        self._in_flight: asyncio.Task | None = None
        
        logger.debug(
            "Telegram draft stream ready (maxChars=%d, throttleMs=%d)",
            self._max_chars, self._throttle_ms
        )
    
    def update(self, text: str) -> None:
        """Queue text update for streaming"""
        if self._stopped or self._is_final:
            return
        
        self._pending_text = text
        
        if self._in_flight:
            self._schedule()
            return
        
        now = time.time()
        elapsed_ms = (now - self._last_sent_at) * 1000
        
        if not self._timer and elapsed_ms >= self._throttle_ms:
            asyncio.create_task(self._flush_internal())
            return
        
        self._schedule()
    
    def _schedule(self) -> None:
        """Schedule next flush after throttle delay"""
        if self._timer:
            return
        
        now = time.time()
        elapsed_ms = (now - self._last_sent_at) * 1000
        delay_ms = max(0, self._throttle_ms - elapsed_ms)
        
        async def _delayed_flush():
            await asyncio.sleep(delay_ms / 1000)
            await self._flush_internal()
        
        self._timer = asyncio.create_task(_delayed_flush())
    
    async def _flush_internal(self) -> None:
        """Internal flush implementation"""
        if self._timer:
            try:
                self._timer.cancel()
            except Exception:
                pass
            self._timer = None
        
        while not self._stopped or self._is_final:
            if self._in_flight:
                await self._in_flight
                continue
            
            text = self._pending_text
            if not text.strip():
                self._pending_text = ""
                return
            
            self._pending_text = ""
            
            async def _send_or_edit():
                return await self._send_or_edit_stream_message(text)
            
            self._in_flight = asyncio.create_task(_send_or_edit())
            
            try:
                sent = await self._in_flight
            finally:
                self._in_flight = None
            
            if sent is False:
                self._pending_text = text
                return
            
            self._last_sent_at = time.time()
            
            if not self._pending_text:
                return
    
    async def _send_or_edit_stream_message(self, text: str) -> bool:
        """Send or edit stream message"""
        if self._stopped and not self._is_final:
            return False
        
        trimmed = text.rstrip()
        if not trimmed:
            return False
        
        if len(trimmed) > self._max_chars:
            self._stopped = True
            logger.warning(
                "Telegram stream preview stopped (text length %d > %d)",
                len(trimmed), self._max_chars
            )
            return False
        
        if trimmed == self._last_sent_text:
            return True
        
        # Debounce first preview send
        if (
            self._stream_message_id is None
            and self._min_initial_chars is not None
            and not self._is_final
        ):
            if len(trimmed) < self._min_initial_chars:
                return False
        
        self._last_sent_text = trimmed
        
        try:
            if self._stream_message_id is not None:
                # Edit existing message
                await self._api.edit_message_text(
                    chat_id=self._chat_id,
                    message_id=self._stream_message_id,
                    text=trimmed,
                )
                return True
            else:
                # Send new message
                reply_params = {}
                if self._reply_to_message_id is not None:
                    reply_params["reply_to_message_id"] = self._reply_to_message_id
                
                # Add thread params (for forum topics)
                reply_params.update(self._thread_params)
                
                sent = await self._api.send_message(
                    chat_id=self._chat_id,
                    text=trimmed,
                    **reply_params,
                )
                
                if not sent or not hasattr(sent, "message_id"):
                    self._stopped = True
                    logger.warning("Telegram stream preview stopped (missing message_id)")
                    return False
                
                self._stream_message_id = sent.message_id
                return True
        
        except Exception as exc:
            self._stopped = True
            logger.warning("Telegram stream preview failed: %s", exc)
            return False
    
    async def flush(self) -> None:
        """Flush any pending updates immediately"""
        await self._flush_internal()
    
    def message_id(self) -> int | None:
        """Get the preview message ID"""
        return self._stream_message_id
    
    async def clear(self) -> None:
        """Clear the preview message (delete it)"""
        self._stopped = True
        
        if self._timer:
            try:
                self._timer.cancel()
            except Exception:
                pass
            self._timer = None
        
        if self._in_flight:
            await self._in_flight
        
        message_id = self._stream_message_id
        self._stream_message_id = None
        
        if message_id is None:
            return
        
        try:
            await self._api.delete_message(
                chat_id=self._chat_id,
                message_id=message_id,
            )
        except Exception as exc:
            logger.warning("Telegram stream preview cleanup failed: %s", exc)
    
    async def stop(self) -> None:
        """Stop streaming and flush final content"""
        self._is_final = True
        await self._flush_internal()
    
    def force_new_message(self) -> None:
        """Reset internal state so next update creates a new message"""
        self._stream_message_id = None
        self._last_sent_text = ""
        self._pending_text = ""


def create_telegram_draft_stream(
    bot_api: Any,
    chat_id: int | str,
    max_chars: int | None = None,
    thread_params: dict | None = None,
    reply_to_message_id: int | None = None,
    throttle_ms: int | None = None,
    min_initial_chars: int | None = None,
) -> TelegramDraftStream:
    """
    Create a Telegram draft stream
    
    Args:
        bot_api: Telegram bot API instance
        chat_id: Target chat ID
        max_chars: Maximum characters (default 4096)
        thread_params: Thread parameters for forum topics
        reply_to_message_id: Message ID to reply to
        throttle_ms: Throttle interval in milliseconds (default 1000)
        min_initial_chars: Minimum chars before sending first message
    
    Returns:
        TelegramDraftStream instance
    """
    return TelegramDraftStream(
        bot_api=bot_api,
        chat_id=chat_id,
        max_chars=max_chars,
        thread_params=thread_params,
        reply_to_message_id=reply_to_message_id,
        throttle_ms=throttle_ms,
        min_initial_chars=min_initial_chars,
    )
