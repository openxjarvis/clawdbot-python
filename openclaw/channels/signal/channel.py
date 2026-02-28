"""Signal channel implementation — aligned with TS signalPlugin

Uses signal-cli REST API:
  - SSE listener: GET {base_url}/v1/receive/{account}
  - Send text:    POST {base_url}/v2/send
  - Send media:   POST {base_url}/v2/send with attachments

Account fields align with TS ResolvedSignalAccount:
    account  — E.164 phone number (e.g. +14155552671)
    base_url — signal-cli REST API base URL (default: http://127.0.0.1:8080)
"""
from __future__ import annotations


import asyncio
import base64
import json
import logging
from datetime import UTC, datetime
from typing import Any

from ..base import ChannelCapabilities, ChannelPlugin, ChatAttachment, InboundMessage

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "http://127.0.0.1:8080"
_SSE_RECONNECT_DELAY = 5.0


class SignalChannel(ChannelPlugin):
    """Signal messaging channel via signal-cli REST API — aligned with TS signalPlugin

    Requires signal-cli running with REST API enabled:
        signal-cli -a +YOUR_PHONE daemon --http localhost:8080
    """

    def __init__(self):
        super().__init__()
        self.id = "signal"
        self.label = "Signal"
        self.capabilities = ChannelCapabilities(
            chat_types=["direct", "group"],
            supports_media=True,
            supports_reactions=True,
            supports_threads=False,
            supports_polls=False,
            supports_reply=True,
        )
        # TS ResolvedSignalAccount fields
        self._account: str = ""   # E.164 phone number
        self._base_url: str = _DEFAULT_BASE_URL
        self._sse_task: asyncio.Task | None = None

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    async def start(self, config: dict[str, Any]) -> None:
        """Start Signal channel — mirrors TS signalPlugin.start()"""
        import os

        self._account = (
            config.get("account")
            or config.get("phoneNumber")
            or config.get("phone_number")
            or os.environ.get("SIGNAL_ACCOUNT")
            or ""
        )
        if not self._account:
            raise ValueError(
                "Signal account (E.164 phone number) not provided "
                "(config key: account or env SIGNAL_ACCOUNT)"
            )

        self._base_url = (
            config.get("baseUrl")
            or config.get("base_url")
            or os.environ.get("SIGNAL_BASE_URL")
            or _DEFAULT_BASE_URL
        ).rstrip("/")

        logger.info(f"[signal] Starting channel for {self._account} at {self._base_url}")

        # Verify API is reachable
        await self._check_api_health()

        self._running = True
        self._sse_task = asyncio.create_task(self._sse_listen_loop())
        logger.info("[signal] Channel started, listening for messages")

    async def _check_api_health(self) -> None:
        """Check signal-cli REST API is running"""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self._base_url}/v1/about",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status == 200:
                        logger.info("[signal] signal-cli REST API is healthy")
                    else:
                        logger.warning(f"[signal] API health check returned {resp.status}")
        except Exception as e:
            logger.warning(
                f"[signal] Could not reach signal-cli REST API at {self._base_url}: {e}\n"
                "Ensure signal-cli daemon is running: "
                "signal-cli -a +PHONE daemon --http 127.0.0.1:8080"
            )

    async def stop(self) -> None:
        """Stop Signal channel"""
        logger.info("[signal] Stopping channel...")
        self._running = False
        if self._sse_task:
            self._sse_task.cancel()
            try:
                await self._sse_task
            except asyncio.CancelledError:
                pass
            self._sse_task = None

    # -------------------------------------------------------------------------
    # SSE listener — mirrors TS monitorSignalProvider
    # -------------------------------------------------------------------------

    async def _sse_listen_loop(self) -> None:
        """Reconnecting SSE listener for /v1/receive/{account}"""
        while self._running:
            try:
                await self._sse_listen()
            except asyncio.CancelledError:
                break
            except Exception as e:
                if not self._running:
                    break
                logger.warning(f"[signal] SSE error: {e}, reconnecting in {_SSE_RECONNECT_DELAY}s")
                await asyncio.sleep(_SSE_RECONNECT_DELAY)

    async def _sse_listen(self) -> None:
        """Open SSE stream from signal-cli REST API /v1/receive/{account}"""
        import aiohttp

        url = f"{self._base_url}/v1/receive/{self._account}"
        logger.info(f"[signal] Connecting to SSE stream: {url}")

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers={"Accept": "text/event-stream"},
                timeout=aiohttp.ClientTimeout(total=None, connect=10),
            ) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"SSE endpoint returned {resp.status}")

                buffer = ""
                async for chunk in resp.content:
                    if not self._running:
                        break
                    buffer += chunk.decode("utf-8", errors="replace")
                    while "\n\n" in buffer:
                        event_str, buffer = buffer.split("\n\n", 1)
                        await self._process_sse_event(event_str)

    async def _process_sse_event(self, event_str: str) -> None:
        """Parse and dispatch an SSE event — mirrors TS signal message handling"""
        data_lines = []
        for line in event_str.splitlines():
            if line.startswith("data: "):
                data_lines.append(line[6:])

        if not data_lines:
            return

        raw = "\n".join(data_lines)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            logger.debug(f"[signal] Non-JSON SSE data: {raw[:80]}")
            return

        envelope = payload.get("envelope") or payload
        source = envelope.get("source") or envelope.get("sourceNumber") or "unknown"
        source_name = envelope.get("sourceName") or source
        timestamp_ms = envelope.get("timestamp") or int(datetime.now(UTC).timestamp() * 1000)

        data_msg = envelope.get("dataMessage") or {}
        text = data_msg.get("message") or ""
        group_info = data_msg.get("groupInfo") or data_msg.get("groupV2Info") or {}

        if group_info:
            chat_id = group_info.get("groupId") or group_info.get("id") or source
            chat_type = "group"
        else:
            chat_id = source
            chat_type = "direct"

        # Handle reactions
        reaction_info = data_msg.get("reaction")
        if reaction_info:
            inbound = InboundMessage(
                channel_id=self.id,
                message_id=f"signal-reaction-{timestamp_ms}",
                sender_id=source,
                sender_name=source_name,
                chat_id=chat_id,
                chat_type=chat_type,
                text="",
                timestamp=datetime.fromtimestamp(timestamp_ms / 1000, UTC).isoformat(),
                metadata={
                    "type": "reaction",
                    "emoji": reaction_info.get("emoji", ""),
                    "target_message_id": str(reaction_info.get("targetSentTimestamp", "")),
                    "remove": reaction_info.get("isRemove", False),
                },
            )
            await self._handle_message(inbound)
            return

        # Attachments
        attachments: list[ChatAttachment] = []
        for att in (data_msg.get("attachments") or []):
            att_type = att.get("contentType") or ""
            attachments.append(ChatAttachment(
                type=_mime_to_type(att_type),
                mime_type=att_type or None,
                content=att.get("data"),
                filename=att.get("filename"),
                size=att.get("size"),
            ))

        if not text and not attachments:
            return

        msg_id = f"signal-{timestamp_ms}"
        inbound = InboundMessage(
            channel_id=self.id,
            message_id=msg_id,
            sender_id=source,
            sender_name=source_name,
            chat_id=chat_id,
            chat_type=chat_type,
            text=text,
            timestamp=datetime.fromtimestamp(timestamp_ms / 1000, UTC).isoformat(),
            metadata={
                "group_id": group_info.get("groupId") or group_info.get("id"),
                "quote": data_msg.get("quote"),
            },
            attachments=attachments,
        )
        await self._handle_message(inbound)

    # -------------------------------------------------------------------------
    # Outbound — mirrors TS sendSignalMessage
    # -------------------------------------------------------------------------

    async def send_text(
        self,
        target: str,
        text: str,
        reply_to: str | None = None,
    ) -> str:
        """Send text via POST /v2/send — mirrors TS signalPlugin send"""
        if not self._running:
            raise RuntimeError("Signal channel not started")

        payload: dict[str, Any] = {
            "message": text,
            "number": self._account,
        }
        if target.startswith("group."):
            payload["recipients"] = []
            payload["group_id"] = target[len("group."):]
        else:
            payload["recipients"] = [target]

        if reply_to:
            payload["quote_timestamp"] = int(reply_to) if reply_to.isdigit() else None

        return await self._post_send(payload)

    async def send_media(
        self,
        target: str,
        media_url: str,
        media_type: str,
        caption: str | None = None,
    ) -> str:
        """Send media with optional caption — mirrors TS signalPlugin send with attachments"""
        if not self._running:
            raise RuntimeError("Signal channel not started")

        # Download media and encode as base64
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(media_url) as resp:
                    data = await resp.read()
            b64 = base64.b64encode(data).decode()
            attachment_str = f"data:{media_type};base64,{b64}"
        except Exception as e:
            logger.error(f"[signal] Media download error: {e}")
            attachment_str = media_url

        payload: dict[str, Any] = {
            "message": caption or "",
            "number": self._account,
            "base64_attachments": [attachment_str],
        }
        if target.startswith("group."):
            payload["recipients"] = []
            payload["group_id"] = target[len("group."):]
        else:
            payload["recipients"] = [target]

        return await self._post_send(payload)

    async def _post_send(self, payload: dict[str, Any]) -> str:
        """POST to /v2/send — mirrors TS signal-cli REST API call"""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self._base_url}/v2/send",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    resp.raise_for_status()
                    result = await resp.json()
                    ts = result.get("timestamp") or int(datetime.now(UTC).timestamp() * 1000)
                    return str(ts)
        except Exception as e:
            logger.error(f"[signal] Send error: {e}", exc_info=True)
            raise


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mime_to_type(mime: str) -> str:
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("audio/"):
        return "audio"
    if mime.startswith("video/"):
        return "video"
    return "file"
