"""Slack channel implementation — aligned with TS monitorSlackProvider/sendMessageSlack"""
from __future__ import annotations


import base64
import logging
from datetime import datetime
from typing import Any

from ..base import ChannelCapabilities, ChannelPlugin, ChatAttachment, InboundMessage

logger = logging.getLogger(__name__)

# Default reply-to mode: "thread" sends replies in thread, "channel" in channel
_DEFAULT_REPLY_MODE = "thread"


class SlackChannel(ChannelPlugin):
    """Slack bot channel — fully aligned with TS slackPlugin"""

    def __init__(self):
        super().__init__()
        self.id = "slack"
        self.label = "Slack"
        self.capabilities = ChannelCapabilities(
            chat_types=["direct", "group", "channel"],
            supports_media=True,
            supports_reactions=True,
            supports_threads=True,
            supports_polls=False,
            native_commands=True,
            supports_reply=True,
        )
        self._app: Any | None = None
        self._bot_token: str | None = None
        # TS ResolvedSlackAccount fields
        self._app_token: str | None = None
        self._reply_to_mode: str = _DEFAULT_REPLY_MODE
        self._reply_to_mode_by_chat_type: dict[str, str] = {}
        self._text_chunk_limit: int = 4000
        self._media_max_mb: int = 8
        self._reaction_notifications: bool = True

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    async def start(self, config: dict[str, Any]) -> None:
        """Start Slack bot using Socket Mode — aligns with TS slackPlugin.start()"""
        self._bot_token = config.get("botToken") or config.get("bot_token")
        signing_secret = config.get("signingSecret") or config.get("signing_secret")
        self._app_token = config.get("appToken") or config.get("app_token")

        # ResolvedSlackAccount field alignment
        self._reply_to_mode = (
            config.get("replyToMode") or config.get("reply_to_mode") or _DEFAULT_REPLY_MODE
        )
        self._reply_to_mode_by_chat_type = (
            config.get("replyToModeByChatType") or config.get("reply_to_mode_by_chat_type") or {}
        )
        self._text_chunk_limit = int(
            config.get("textChunkLimit") or config.get("text_chunk_limit") or 4000
        )
        self._media_max_mb = int(
            config.get("mediaMaxMb") or config.get("media_max_mb") or 8
        )
        self._reaction_notifications = bool(
            config.get("reactionNotifications", config.get("reaction_notifications", True))
        )

        if not self._bot_token or not signing_secret:
            raise ValueError("Slack botToken and signingSecret are required")

        logger.info("Starting Slack channel...")

        try:
            from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
            from slack_bolt.async_app import AsyncApp

            self._app = AsyncApp(token=self._bot_token, signing_secret=signing_secret)

            @self._app.message("")
            async def handle_message(message, say):
                await self._handle_slack_message(message, say)

            if self._reaction_notifications:
                @self._app.event("reaction_added")
                async def handle_reaction_added(event, say):
                    await self._handle_reaction_event(event, "add")

                @self._app.event("reaction_removed")
                async def handle_reaction_removed(event, say):
                    await self._handle_reaction_event(event, "remove")

            if self._app_token:
                handler = AsyncSocketModeHandler(self._app, self._app_token)
                await handler.start_async()

            self._running = True
            logger.info("Slack channel started")

        except ImportError:
            logger.error("slack-sdk not installed. Install with: pip install slack-sdk slack-bolt")
            raise

    async def stop(self) -> None:
        """Stop Slack bot"""
        logger.info("Stopping Slack channel...")
        self._running = False

    # -------------------------------------------------------------------------
    # Inbound handling
    # -------------------------------------------------------------------------

    async def _handle_slack_message(self, message: dict[str, Any], say: Any) -> None:
        """Handle incoming Slack message — mirrors TS monitorSlackProvider"""
        if message.get("bot_id"):
            return

        attachments: list[ChatAttachment] = await self._download_attachments(message)

        chat_type_raw = message.get("channel_type", "")
        chat_type = "direct" if chat_type_raw == "im" else "group"

        inbound = InboundMessage(
            channel_id=self.id,
            message_id=message.get("ts", ""),
            sender_id=message.get("user", ""),
            sender_name=message.get("user", ""),
            chat_id=message.get("channel", ""),
            chat_type=chat_type,
            text=message.get("text", ""),
            timestamp=_slack_ts_to_iso(message.get("ts", "0")),
            reply_to=message.get("thread_ts") if message.get("thread_ts") != message.get("ts") else None,
            metadata={
                "channel_type": chat_type_raw,
                "team": message.get("team"),
                "thread_ts": message.get("thread_ts"),
            },
            attachments=attachments,
        )

        await self._handle_message(inbound)

    async def _handle_reaction_event(self, event: dict[str, Any], action: str) -> None:
        """Handle Slack reaction_added / reaction_removed events"""
        item = event.get("item", {})
        inbound = InboundMessage(
            channel_id=self.id,
            message_id=f"{item.get('ts', '')}-reaction-{action}",
            sender_id=event.get("user", ""),
            sender_name=event.get("user", ""),
            chat_id=item.get("channel", ""),
            chat_type="group",
            text="",
            timestamp=_slack_ts_to_iso(event.get("event_ts", "0")),
            metadata={
                "type": "reaction",
                "action": action,
                "emoji": event.get("reaction", ""),
                "target_message_id": item.get("ts"),
            },
        )
        await self._handle_message(inbound)

    async def _download_attachments(self, message: dict[str, Any]) -> list[ChatAttachment]:
        """Download Slack file attachments as base64 — mirrors TS attachment handling"""
        result: list[ChatAttachment] = []
        files = message.get("files") or []
        for f in files:
            try:
                url = f.get("url_private_download") or f.get("url_private")
                if not url:
                    continue
                size = f.get("size", 0)
                max_bytes = self._media_max_mb * 1024 * 1024
                if size > max_bytes:
                    logger.debug(f"[slack] Skipping large file {f.get('name')} ({size} bytes)")
                    continue
                import aiohttp
                headers = {"Authorization": f"Bearer {self._bot_token}"}
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers) as resp:
                        data = await resp.read()
                content_b64 = base64.b64encode(data).decode()
                mime = f.get("mimetype", "")
                result.append(ChatAttachment(
                    type=_mime_to_type(mime),
                    mime_type=mime or None,
                    content=content_b64,
                    filename=f.get("name"),
                    size=size or None,
                ))
            except Exception as e:
                logger.warning(f"[slack] Failed to download attachment: {e}")
        return result

    # -------------------------------------------------------------------------
    # Outbound
    # -------------------------------------------------------------------------

    async def send_text(
        self,
        target: str,
        text: str,
        reply_to: str | None = None,
        thread_ts: str | None = None,
    ) -> str:
        """Send text message with replyToMode support — mirrors TS sendMessageSlack"""
        if not self._app:
            raise RuntimeError("Slack channel not started")

        try:
            effective_thread_ts = thread_ts or reply_to
            if effective_thread_ts:
                mode = self._reply_to_mode_by_chat_type.get("group") or self._reply_to_mode
                if mode == "channel":
                    effective_thread_ts = None

            result = await self._app.client.chat_postMessage(
                channel=target,
                text=text,
                thread_ts=effective_thread_ts,
            )
            return result["ts"]

        except Exception as e:
            logger.error(f"Failed to send Slack message: {e}", exc_info=True)
            raise

    async def send_media(
        self,
        target: str,
        media_url: str,
        media_type: str,
        caption: str | None = None,
        thread_ts: str | None = None,
    ) -> str:
        """Upload media to Slack — mirrors TS Slack file upload"""
        if not self._app:
            raise RuntimeError("Slack channel not started")

        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(media_url) as resp:
                    data = await resp.read()

            filename = media_url.split("/")[-1] or "media"
            result = await self._app.client.files_upload_v2(
                channel=target,
                file=data,
                filename=filename,
                initial_comment=caption or "",
                thread_ts=thread_ts,
            )
            return result.get("file", {}).get("id", "")

        except Exception as e:
            logger.error(f"Failed to send Slack media: {e}", exc_info=True)
            raise


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slack_ts_to_iso(ts: str) -> str:
    """Convert Slack timestamp (e.g. '1234567890.123456') to ISO format"""
    try:
        epoch = float(ts)
        return datetime.fromtimestamp(epoch).isoformat()
    except (ValueError, OSError):
        return ts


def _mime_to_type(mime: str) -> str:
    """Map MIME type to ChatAttachment type string"""
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("audio/"):
        return "audio"
    if mime.startswith("video/"):
        return "video"
    return "file"
