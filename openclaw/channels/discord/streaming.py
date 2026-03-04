"""
Discord block/partial streaming — mirrors src/discord/draft-stream.ts,
draft-chunking.ts, and config.discord-preview-streaming.ts.

Stream modes:
  "off"      — no preview; only send the final reply
  "partial"  — edit a single placeholder message as content grows
  "block"    — chunked edits (coalesce small increments, flush idle)
  "progress" — alias for "partial"
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from .config import BlockStreamingCoalesceConfig, StreamingMode

logger = logging.getLogger(__name__)


class DiscordStreamingSession:
    """
    Manages incremental preview updates for a single agent reply in a Discord channel.

    Usage::

        session = DiscordStreamingSession(channel, mode="block", coalesce=...)
        await session.start()
        async for chunk in agent_stream:
            await session.append(chunk)
        final_msg = await session.finish(final_text)
    """

    def __init__(
        self,
        channel: Any,
        mode: StreamingMode,
        coalesce: BlockStreamingCoalesceConfig | None = None,
        reply_to_id: int | None = None,
        ephemeral: bool = False,
    ) -> None:
        self._channel = channel
        self._mode = mode if mode != "progress" else "partial"
        self._coalesce = coalesce or BlockStreamingCoalesceConfig()
        self._reply_to_id = reply_to_id
        self._ephemeral = ephemeral

        self._preview_msg: Any | None = None
        self._buffer: str = ""
        self._last_flush_chars: int = 0
        self._idle_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Send an initial placeholder message for partial/block modes."""
        if self._mode == "off":
            return
        try:
            import discord
            kwargs: dict[str, Any] = {"content": "\u2026"}  # ellipsis placeholder
            if self._reply_to_id:
                kwargs["reference"] = discord.MessageReference(
                    message_id=self._reply_to_id,
                    channel_id=self._channel.id,
                )
            self._preview_msg = await self._channel.send(**kwargs)
        except Exception as exc:
            logger.debug("[discord][stream] Failed to send placeholder: %s", exc)
            self._preview_msg = None

    async def append(self, chunk: str) -> None:
        """Append a text chunk to the buffer and flush if thresholds are met."""
        if self._mode == "off" or self._preview_msg is None:
            return

        async with self._lock:
            self._buffer += chunk
            new_chars = len(self._buffer) - self._last_flush_chars

            if self._mode == "partial":
                await self._flush()
                return

            # block mode: flush when min_chars threshold reached
            if new_chars >= self._coalesce.min_chars:
                await self._flush()
                self._cancel_idle()
            else:
                # Start/reset idle timer
                self._reset_idle()

    async def _flush(self) -> None:
        """Edit the preview message with the current buffer (truncated to 2000 chars)."""
        if self._preview_msg is None or not self._buffer:
            return
        text = self._buffer[:2000]
        try:
            await self._preview_msg.edit(content=text)
            self._last_flush_chars = len(self._buffer)
        except Exception as exc:
            logger.debug("[discord][stream] Edit failed: %s", exc)

    def _reset_idle(self) -> None:
        self._cancel_idle()
        idle_secs = self._coalesce.idle_ms / 1000.0
        self._idle_task = asyncio.create_task(self._idle_flush(idle_secs))

    def _cancel_idle(self) -> None:
        if self._idle_task and not self._idle_task.done():
            self._idle_task.cancel()
        self._idle_task = None

    async def _idle_flush(self, delay: float) -> None:
        await asyncio.sleep(delay)
        async with self._lock:
            await self._flush()

    async def finish(self, final_text: str) -> Any:
        """
        Cancel idle flush, edit preview to final text (or delete + resend for long replies).
        Returns the final Discord message object.
        """
        self._cancel_idle()

        if self._mode == "off" or self._preview_msg is None:
            # Send fresh message
            return await self._send_fresh(final_text)

        if len(final_text) <= 2000:
            try:
                await self._preview_msg.edit(content=final_text)
                return self._preview_msg
            except Exception:
                pass

        # Final text > 2000 chars — delete preview and send chunked
        try:
            await self._preview_msg.delete()
        except Exception:
            pass
        return await self._send_fresh(final_text)

    async def _send_fresh(self, text: str) -> Any:
        """Send text without a pre-existing preview message (off mode or fallback)."""
        import discord

        chunks = _chunk_text(text)
        last_msg: Any = None
        for i, chunk in enumerate(chunks):
            kwargs: dict[str, Any] = {"content": chunk}
            if i == 0 and self._reply_to_id:
                kwargs["reference"] = discord.MessageReference(
                    message_id=self._reply_to_id,
                    channel_id=self._channel.id,
                )
            last_msg = await self._channel.send(**kwargs)
        return last_msg


# ---------------------------------------------------------------------------
# Text chunking — mirrors src/discord/chunk.ts
# ---------------------------------------------------------------------------

_MAX_DISCORD_MSG_LEN = 2000
_DEFAULT_MAX_LINES = 17


def _chunk_text(
    text: str,
    chunk_limit: int = _MAX_DISCORD_MSG_LEN,
    max_lines: int = _DEFAULT_MAX_LINES,
    mode: str = "length",
) -> list[str]:
    """
    Split text into Discord-safe chunks.

    mode="length": split at chunk_limit characters, preferring newline boundaries.
    mode="newline": split every max_lines lines.
    Mirrors discordChunkText() in src/discord/chunk.ts.
    """
    if not text:
        return [""]

    if mode == "newline":
        return _chunk_by_lines(text, max_lines)

    return _chunk_by_length(text, chunk_limit)


def _chunk_by_length(text: str, limit: int) -> list[str]:
    chunks: list[str] = []
    while len(text) > limit:
        # Try to split at a newline within the limit
        split_at = text.rfind("\n", 0, limit)
        if split_at <= 0:
            split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    if text:
        chunks.append(text)
    return chunks


def _chunk_by_lines(text: str, max_lines: int) -> list[str]:
    lines = text.split("\n")
    chunks: list[str] = []
    current: list[str] = []
    for line in lines:
        current.append(line)
        if len(current) >= max_lines:
            chunks.append("\n".join(current))
            current = []
    if current:
        chunks.append("\n".join(current))
    return chunks
