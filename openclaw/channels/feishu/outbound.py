"""Outbound adapter for Feishu channel.

Adapts the abstract send_text / send_media interface to Feishu-specific sending,
handling ID normalization (chat_id → receive_id_type) and text chunking.

Mirrors TypeScript: extensions/feishu/src/outbound.ts
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .media import send_media_feishu
from .send import SendResult, chunk_text, send_feishu_message
from .targets import resolve_receive_id_type as _resolve_id_type

if TYPE_CHECKING:
    from .config import ResolvedFeishuAccount

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ID type resolution (delegates to targets.py for full prefix support)
# ---------------------------------------------------------------------------

def resolve_receive_id_type(target: str) -> tuple[str, str]:
    """
    Determine the receive_id_type for a given target string.

    Handles routing prefixes (chat:, user:, dm:, group:, open_id:) and raw IDs.
    Delegates to targets.resolve_receive_id_type() for full normalization.

    Returns (receive_id, receive_id_type).
    """
    return _resolve_id_type(target)


# ---------------------------------------------------------------------------
# Feishu outbound adapter
# ---------------------------------------------------------------------------

class FeishuOutboundAdapter:
    """
    Handles sending text and media for a single Feishu account.

    Mirrors TS ChannelOutboundAdapter in outbound.ts.
    """

    def __init__(
        self,
        client: Any,
        account: ResolvedFeishuAccount,
    ) -> None:
        self._client = client
        self._account = account

    async def send_text(
        self,
        target: str,
        text: str,
        *,
        reply_to: str | None = None,
        reply_in_thread: bool = False,
    ) -> str:
        """
        Send text to target (chat_id or user open_id).

        Splits into chunks if text exceeds textChunkLimit.
        Returns the last sent message_id.
        """
        receive_id, receive_id_type = resolve_receive_id_type(target)
        render_mode = self._account.render_mode
        chunk_limit = self._account.text_chunk_limit
        chunk_mode = self._account.chunk_mode
        markdown_mode = getattr(self._account.markdown, "mode", "native")

        chunks = chunk_text(text, chunk_limit, chunk_mode)
        last_msg_id = ""

        for i, chunk in enumerate(chunks):
            result: SendResult | None = await send_feishu_message(
                self._client,
                receive_id=receive_id,
                receive_id_type=receive_id_type,
                text=chunk,
                render_mode=render_mode,
                reply_to_message_id=reply_to if i == 0 else None,
                reply_in_thread=reply_in_thread if i == 0 else False,
                markdown_mode=markdown_mode,
            )
            if result:
                last_msg_id = result.message_id

        return last_msg_id

    async def send_media(
        self,
        target: str,
        data: bytes,
        filename: str,
        *,
        media_type: str = "file",
        caption: str | None = None,
        reply_to: str | None = None,
        reply_in_thread: bool = False,
    ) -> str:
        """Send a media file. Returns message_id or empty string on failure."""
        logger.info(f"[feishu outbound] send_media: target={target}, filename={filename}, media_type={media_type}, size={len(data)} bytes")
        receive_id, receive_id_type = resolve_receive_id_type(target)
        logger.info(f"[feishu outbound] send_media: receive_id={receive_id}, receive_id_type={receive_id_type}")

        msg_id = await send_media_feishu(
            self._client,
            receive_id=receive_id,
            receive_id_type=receive_id_type,
            data=data,
            filename=filename,
            media_type=media_type,
            reply_to_message_id=reply_to,
            reply_in_thread=reply_in_thread,
        )

        logger.info(f"[feishu outbound] send_media: msg_id={msg_id}")

        # If caption was provided and media was sent successfully, also send the caption
        if caption and msg_id:
            logger.info(f"[feishu outbound] send_media: sending caption")
            await self.send_text(target, caption)

        return msg_id or ""
