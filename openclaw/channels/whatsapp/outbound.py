"""WhatsApp outbound message adapter.

Handles text chunking, Markdown→WhatsApp conversion, media loading,
reaction and poll sending, with 3× retry on connection errors.

Mirrors TypeScript: src/web/auto-reply/deliver-reply.ts and src/web/outbound.ts
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import ResolvedWhatsAppAccount
    from .bridge_client import BridgeClient

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_BASE_MS = 500


# ---------------------------------------------------------------------------
# Text chunking (mirrors TS chunkMode logic)
# ---------------------------------------------------------------------------

def chunk_text(text: str, limit: int = 4000, mode: str = "length") -> list[str]:
    """
    Split text into chunks for WhatsApp delivery.

    mode="length": hard split at `limit` characters
    mode="newline": split on paragraph/newline boundaries, stay under `limit`
    """
    if not text or len(text) <= limit:
        return [text] if text else []

    if mode == "newline":
        return _chunk_by_newline(text, limit)

    # length mode: simple character-based chunking
    chunks: list[str] = []
    while len(text) > limit:
        chunks.append(text[:limit])
        text = text[limit:]
    if text:
        chunks.append(text)
    return chunks


def _chunk_by_newline(text: str, limit: int) -> list[str]:
    """Split on paragraph boundaries, accumulating up to `limit` chars."""
    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        candidate = f"{current}\n\n{para}" if current else para
        if len(candidate) <= limit:
            current = candidate
        else:
            if current:
                chunks.append(current)
            # If single paragraph exceeds limit, force-split it
            if len(para) > limit:
                for i in range(0, len(para), limit):
                    chunks.append(para[i : i + limit])
                current = ""
            else:
                current = para
    if current:
        chunks.append(current)
    return chunks or [text]


# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------

async def _with_retry(coro_factory, retries: int = _MAX_RETRIES) -> any:
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            return await coro_factory()
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                delay_ms = _RETRY_BASE_MS * (attempt + 1)
                logger.debug("[whatsapp] Retry %d after error: %s", attempt + 1, e)
                await asyncio.sleep(delay_ms / 1000.0)
    raise last_err  # type: ignore


# ---------------------------------------------------------------------------
# Outbound adapter
# ---------------------------------------------------------------------------

class WhatsAppOutboundAdapter:
    """
    Wraps BridgeClient with WhatsApp-specific sending logic.

    Per-account config controls markdown conversion, chunking, and media limits.
    """

    def __init__(
        self,
        bridge_client: "BridgeClient",
        account: "ResolvedWhatsAppAccount",
    ) -> None:
        self._client = bridge_client
        self._account = account

    async def send_text(
        self,
        to: str,
        text: str,
        reply_to: str | None = None,
    ) -> str:
        """
        Send one or more text chunks after Markdown→WhatsApp conversion.
        Returns the message ID of the last chunk.
        """
        from .markdown import markdown_to_whatsapp, convert_markdown_tables

        converted = convert_markdown_tables(text, self._account.markdown.table_mode)
        converted = markdown_to_whatsapp(converted)

        chunks = chunk_text(
            converted,
            limit=self._account.text_chunk_limit,
            mode=self._account.chunk_mode,
        )
        if not chunks:
            chunks = [converted or ""]

        last_id = "unknown"
        for i, chunk in enumerate(chunks):
            # Only pass reply_to for the first chunk
            chunk_reply = reply_to if i == 0 else None
            try:
                result = await _with_retry(
                    lambda c=chunk, r=chunk_reply: self._client.send_message(
                        self._account.account_id, to, c, r
                    )
                )
                last_id = result.get("messageId", "unknown")
            except Exception as e:
                logger.error("[whatsapp] Failed to send text chunk %d: %s", i, e, exc_info=True)
                raise

        return last_id

    async def send_media(
        self,
        to: str,
        media_url: str,
        media_type: str,
        caption: str | None = None,
    ) -> str:
        """Load and send media (with image optimization)."""
        from .media import load_outbound_media

        try:
            loaded = load_outbound_media(media_url, self._account.media_max_mb)
        except Exception as e:
            logger.warning("[whatsapp] Media load failed: %s; sending text fallback", e)
            return await self.send_text(to, caption or f"[media: {media_url}]")

        # Convert markdown in caption
        if caption:
            from .markdown import markdown_to_whatsapp
            caption = markdown_to_whatsapp(caption)

        try:
            result = await _with_retry(
                lambda: self._client.send_media(
                    self._account.account_id,
                    to,
                    loaded.buffer,
                    loaded.content_type,
                    caption,
                    loaded.file_name,
                )
            )
            return result.get("messageId", "unknown")
        except Exception as e:
            logger.error("[whatsapp] Failed to send media: %s", e, exc_info=True)
            # Fallback: send caption as text
            if caption:
                return await self.send_text(to, caption)
            raise

    async def send_reaction(
        self,
        to: str,
        message_id: str,
        emoji: str,
        remove: bool = False,
    ) -> None:
        """Send or remove an emoji reaction."""
        try:
            await _with_retry(
                lambda: self._client.send_reaction(
                    self._account.account_id, to, message_id, emoji, remove
                )
            )
        except Exception as e:
            logger.warning("[whatsapp] Reaction failed: %s", e)

    async def send_poll(
        self,
        to: str,
        question: str,
        options: list[str],
        max_selections: int = 1,
    ) -> str:
        """Send a native WhatsApp poll (up to 12 options)."""
        trimmed_options = [o.strip() for o in options[:12] if o.strip()]
        result = await _with_retry(
            lambda: self._client.send_poll(
                self._account.account_id, to, question, trimmed_options, max_selections
            )
        )
        return result.get("messageId", "unknown")
