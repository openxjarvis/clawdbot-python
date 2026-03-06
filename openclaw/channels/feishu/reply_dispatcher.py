"""Reply dispatcher for Feishu channel.

Manages the lifecycle of a single reply:
  - Starts typing indicator (Typing emoji reaction)
  - Either uses streaming card (CardKit) or direct message send
  - Sends any media URLs after text
  - Removes typing indicator when done

Key improvements vs previous version:
  - ``thread_reply=True`` disables streaming cards (not supported in topic threads)
  - ``root_id`` passed to streaming session for topic-group routing
  - Media URL sending integrated into the reply lifecycle
  - ``is_active()`` forwarded from streaming session

Mirrors TypeScript: extensions/feishu/src/reply-dispatcher.ts
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .outbound import FeishuOutboundAdapter, resolve_receive_id_type
from .send import send_feishu_message
from .streaming_card import FeishuStreamingSession, StreamingCardHeader
from .typing import FeishuTypingIndicator

if TYPE_CHECKING:
    from .config import ResolvedFeishuAccount

logger = logging.getLogger(__name__)


class FeishuReplyDispatcher:
    """
    Orchestrates typing indicator + streaming card for a single reply context.

    Usage pattern (mirrors TS createFeishuReplyDispatcher):
      dispatcher = FeishuReplyDispatcher(client, account, ...)
      await dispatcher.start()
      await dispatcher.send(text)    # or stream via update/finalize
      await dispatcher.send_media_urls(urls)   # optional
      # typing indicator removed automatically after send()
    """

    def __init__(
        self,
        client: Any,
        account: ResolvedFeishuAccount,
        *,
        receive_id: str,
        receive_id_type: str,
        reply_to_message_id: str | None,
        message_timestamp: float,
        reply_in_thread: bool = False,
        thread_reply: bool = False,
        root_id: str | None = None,
        header: StreamingCardHeader | None = None,
    ) -> None:
        self._client = client
        self._account = account
        self._receive_id = receive_id
        self._receive_id_type = receive_id_type
        self._reply_to_message_id = reply_to_message_id
        self._message_timestamp = message_timestamp
        self._reply_in_thread = reply_in_thread
        self._root_id = root_id
        self._header = header

        # Streaming is disabled for topic-thread replies (card streaming misses thread
        # affinity in topic contexts). Mirrors TS: ``!threadReplyMode && streaming !== false``
        self._thread_reply_mode = thread_reply
        self._streaming_enabled = (
            not thread_reply
            and getattr(account, "streaming", True)
            and getattr(account, "render_mode", "auto") != "raw"
        )

        self._typing: FeishuTypingIndicator | None = None
        self._streaming_session: FeishuStreamingSession | None = None
        self._outbound = FeishuOutboundAdapter(client, account)
        self._last_sent_id: str | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start_typing(self) -> None:
        """Begin the typing indicator if enabled and message is recent."""
        if not self._account.typing_indicator:
            return

        if self._reply_to_message_id:
            self._typing = FeishuTypingIndicator(
                self._client,
                self._reply_to_message_id,
                self._message_timestamp,
                self._account.account_id,
            )
            await self._typing.__aenter__()

    async def stop_typing(self) -> None:
        """Remove typing indicator."""
        if self._typing:
            await self._typing.__aexit__(None, None, None)
            self._typing = None

    # ------------------------------------------------------------------
    # Streaming card flow (incremental output)
    # ------------------------------------------------------------------

    async def start_streaming(self) -> bool:
        """
        Initialize a streaming card session.

        Returns True if streaming card was created successfully.
        Falls back to non-streaming if CardKit fails or streaming is disabled.
        Mirrors TS startStreaming().
        """
        if not self._streaming_enabled:
            return False

        # Pass block_coalesce from account config so that when streamingCoalesce
        # is enabled in the account settings, only the final text is sent (no
        # intermediate streaming updates). Mirrors TS blockStreamingCoalesce option.
        _bsc = getattr(self._account, "block_streaming_coalesce", None)
        _block_coalesce = getattr(_bsc, "enabled", False) if _bsc else False
        session = FeishuStreamingSession(
            self._client, self._account, block_coalesce=_block_coalesce
        )
        ok = await session.start(
            self._receive_id,
            self._receive_id_type,
            reply_to_message_id=self._reply_to_message_id,
            reply_in_thread=self._reply_in_thread,
            root_id=self._root_id,
            header=self._header,
        )
        if ok:
            self._streaming_session = session
        return ok

    async def stream_update(self, text: str) -> None:
        """Push incremental text to the streaming card."""
        if self._streaming_session:
            await self._streaming_session.update(text)

    async def stream_finalize(
        self,
        final_text: str,
        buttons: list[list[dict]] | None = None,
    ) -> str | None:
        """
        Finalize the streaming card and stop typing. Returns message_id.

        When buttons are provided, the streaming card is finalized with the
        text first, then PATCH-ed again with a button card so users can
        interact with the response (e.g. confirm / choose).
        """
        msg_id: str | None = None
        if self._streaming_session:
            msg_id = await self._streaming_session.finalize(final_text)
            self._last_sent_id = msg_id

            # If buttons are requested, patch the now-finalized card with a
            # full button card (includes both the markdown text and ActionSet).
            if buttons and msg_id:
                try:
                    from .card_builder import build_button_card
                    from .send import patch_feishu_card
                    button_card = build_button_card(final_text, buttons)
                    await patch_feishu_card(self._client, msg_id, button_card)
                except Exception as _be:
                    logger.debug("[feishu] Failed to patch button card after finalize: %s", _be)

        await self.stop_typing()
        return msg_id

    def is_streaming_active(self) -> bool:
        return self._streaming_session is not None and self._streaming_session.is_active()

    # ------------------------------------------------------------------
    # Non-streaming single send
    # ------------------------------------------------------------------

    async def send(
        self,
        text: str,
        buttons: list[list[dict]] | None = None,
    ) -> str | None:
        """
        Send a complete text reply (non-streaming).

        When buttons are provided, sends an interactive card with both the
        markdown text and an ActionSet (button card), instead of a plain
        post message. Button clicks are routed back as synthetic agent messages.

        Stops typing indicator when done.
        Returns message_id or None.
        """
        try:
            card_override = None
            if buttons:
                from .card_builder import build_button_card
                card_override = build_button_card(text, buttons)

            result = await send_feishu_message(
                self._client,
                receive_id=self._receive_id,
                receive_id_type=self._receive_id_type,
                text=text,
                render_mode=self._account.render_mode,
                reply_to_message_id=self._reply_to_message_id,
                reply_in_thread=self._reply_in_thread,
                card_override=card_override,
            )
            msg_id = result.message_id if result else None
            self._last_sent_id = msg_id
            return msg_id
        finally:
            await self.stop_typing()

    # ------------------------------------------------------------------
    # Media sending
    # ------------------------------------------------------------------

    async def send_media_urls(
        self,
        media_urls: list[str],
        *,
        media_type: str = "file",
    ) -> None:
        """
        Download and send one or more media URLs as Feishu file/image messages.

        Called after text send to attach media to the reply.
        Mirrors TS sendMediaFeishu() calls inside deliver().
        """
        import aiohttp
        from pathlib import Path

        for url in media_urls:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        if resp.status != 200:
                            logger.warning(
                                "[feishu] Failed to download media from %s: HTTP %s",
                                url, resp.status,
                            )
                            continue
                        data = await resp.read()

                filename = Path(url.split("?")[0]).name or "attachment"
                await self._outbound.send_media(
                    self._receive_id,
                    data,
                    filename,
                    media_type=media_type,
                    reply_to=self._reply_to_message_id,
                    reply_in_thread=self._reply_in_thread,
                )
            except Exception as exc:
                logger.warning("[feishu] send_media_urls error for %s: %s", url, exc)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def last_sent_id(self) -> str | None:
        return self._last_sent_id

    @property
    def streaming_enabled(self) -> bool:
        return self._streaming_enabled


def create_feishu_reply_dispatcher(
    client: Any,
    account: ResolvedFeishuAccount,
    *,
    chat_id: str,
    is_p2p: bool,
    reply_to_message_id: str | None,
    message_timestamp: float,
    reply_in_thread: bool = False,
    thread_reply: bool = False,
    root_id: str | None = None,
    header: StreamingCardHeader | None = None,
) -> FeishuReplyDispatcher:
    """
    Factory that creates a FeishuReplyDispatcher with correct receive_id_type.

    Mirrors TS createFeishuReplyDispatcher().
    """
    receive_id, receive_id_type = resolve_receive_id_type(chat_id)
    return FeishuReplyDispatcher(
        client,
        account,
        receive_id=receive_id,
        receive_id_type=receive_id_type,
        reply_to_message_id=reply_to_message_id,
        message_timestamp=message_timestamp,
        reply_in_thread=reply_in_thread,
        thread_reply=thread_reply,
        root_id=root_id,
        header=header,
    )
