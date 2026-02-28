"""Google Chat channel implementation — aligned with TS googleChatPlugin

Authentication: Service Account (google-auth)
Inbound:  Google Cloud Pub/Sub subscription OR webhook endpoint
Outbound: POST /v1/spaces/{spaceId}/messages (Google Chat REST API)

Account fields:
    service_account_key — path to JSON key file (or dict)
    project_id          — GCP project ID
    space_id            — default space (e.g. "spaces/AAAAABBBBB")
    subscription_name   — Pub/Sub subscription (e.g. "projects/proj/subscriptions/sub")
    webhook_path        — optional webhook path for push delivery
"""
from __future__ import annotations


import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

from ..base import ChannelCapabilities, ChannelPlugin, ChatAttachment, InboundMessage

logger = logging.getLogger(__name__)

_CHAT_API_BASE = "https://chat.googleapis.com"
_CHAT_SCOPES = [
    "https://www.googleapis.com/auth/chat.bot",
    "https://www.googleapis.com/auth/chat.messages",
    "https://www.googleapis.com/auth/chat.spaces.readonly",
]
_PUBSUB_PULL_INTERVAL = 2.0


class GoogleChatChannel(ChannelPlugin):
    """Google Chat channel — aligned with TS googleChatPlugin

    Supports Pub/Sub pull-based message monitoring and
    REST API message sending with spaces/{spaceId} target format.
    """

    def __init__(self):
        super().__init__()
        self.id = "googlechat"
        self.label = "Google Chat"
        self.capabilities = ChannelCapabilities(
            chat_types=["direct", "group"],
            supports_media=True,
            supports_reactions=False,
            supports_threads=True,
            supports_polls=False,
            supports_reply=True,
        )
        self._credentials: Any | None = None
        self._project_id: str = ""
        self._space_id: str = ""
        self._subscription_name: str = ""
        self._webhook_path: str = ""
        self._pubsub_task: asyncio.Task | None = None
        self._http_session: Any | None = None

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    async def start(self, config: dict[str, Any]) -> None:
        """Start Google Chat channel — mirrors TS googleChatPlugin.start()"""
        import os

        service_account_key = (
            config.get("serviceAccountKey")
            or config.get("service_account_key")
            or config.get("credentialsFile")
            or config.get("credentials_file")
            or os.environ.get("GOOGLE_CHAT_SERVICE_ACCOUNT")
        )
        self._project_id = (
            config.get("projectId")
            or config.get("project_id")
            or os.environ.get("GOOGLE_CLOUD_PROJECT")
            or ""
        )
        self._space_id = config.get("spaceId") or config.get("space_id") or ""
        self._subscription_name = (
            config.get("subscriptionName")
            or config.get("subscription_name")
            or ""
        )
        self._webhook_path = config.get("webhookPath") or config.get("webhook_path") or ""

        if not service_account_key:
            logger.warning(
                "[googlechat] No service account key provided — running in framework mode. "
                "Set config.serviceAccountKey or env GOOGLE_CHAT_SERVICE_ACCOUNT"
            )
            self._running = True
            return

        await self._init_credentials(service_account_key)

        self._running = True
        logger.info(f"[googlechat] Channel started (project={self._project_id})")

        # Start Pub/Sub listener if subscription configured
        if self._subscription_name:
            self._pubsub_task = asyncio.create_task(self._pubsub_pull_loop())
            logger.info(f"[googlechat] Pub/Sub listener started: {self._subscription_name}")

    async def _init_credentials(self, key_source: Any) -> None:
        """Load Google service account credentials"""
        try:
            from google.oauth2 import service_account  # type: ignore

            if isinstance(key_source, dict):
                self._credentials = service_account.Credentials.from_service_account_info(
                    key_source, scopes=_CHAT_SCOPES
                )
            elif isinstance(key_source, str) and key_source.startswith("{"):
                info = json.loads(key_source)
                self._credentials = service_account.Credentials.from_service_account_info(
                    info, scopes=_CHAT_SCOPES
                )
            else:
                from pathlib import Path
                path = Path(key_source).expanduser()
                if not path.exists():
                    logger.warning(f"[googlechat] Service account key not found: {key_source}")
                    return
                self._credentials = service_account.Credentials.from_service_account_file(
                    str(path), scopes=_CHAT_SCOPES
                )
            logger.info("[googlechat] Service account credentials loaded")
        except ImportError:
            logger.warning(
                "[googlechat] google-auth not installed. "
                "Install with: pip install google-auth google-cloud-pubsub google-api-python-client"
            )
        except Exception as e:
            logger.error(f"[googlechat] Failed to load credentials: {e}")

    async def stop(self) -> None:
        """Stop Google Chat channel"""
        logger.info("[googlechat] Stopping channel...")
        self._running = False
        if self._pubsub_task:
            self._pubsub_task.cancel()
            try:
                await self._pubsub_task
            except asyncio.CancelledError:
                pass
        if self._http_session:
            try:
                await self._http_session.close()
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # Pub/Sub pull listener — mirrors TS googleChatPlugin inbound monitoring
    # -------------------------------------------------------------------------

    async def _pubsub_pull_loop(self) -> None:
        """Poll Pub/Sub subscription for incoming messages"""
        while self._running:
            try:
                await self._pull_messages()
                await asyncio.sleep(_PUBSUB_PULL_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"[googlechat] Pub/Sub pull error: {e}")
                await asyncio.sleep(_PUBSUB_PULL_INTERVAL * 2)

    async def _pull_messages(self) -> None:
        """Pull and acknowledge Pub/Sub messages"""
        if not self._credentials or not self._subscription_name:
            return

        try:
            from google.cloud import pubsub_v1  # type: ignore
            from google.api_core import exceptions as gapi_exceptions

            subscriber = pubsub_v1.SubscriberClient(credentials=self._credentials)
            response = subscriber.pull(
                request={
                    "subscription": self._subscription_name,
                    "max_messages": 10,
                },
                timeout=5,
            )

            ack_ids = []
            for msg in response.received_messages:
                ack_ids.append(msg.ack_id)
                await self._process_pubsub_message(msg.message.data)

            if ack_ids:
                subscriber.acknowledge(
                    request={"subscription": self._subscription_name, "ack_ids": ack_ids}
                )
        except ImportError:
            logger.warning("[googlechat] google-cloud-pubsub not installed")
        except Exception as e:
            logger.debug(f"[googlechat] Pull error (may be empty): {e}")

    async def _process_pubsub_message(self, data: bytes) -> None:
        """Parse a Pub/Sub message payload — mirrors TS Google Chat event format"""
        try:
            payload = json.loads(data.decode("utf-8"))
        except Exception:
            logger.debug("[googlechat] Non-JSON Pub/Sub message")
            return

        msg_type = payload.get("type")
        if msg_type not in ("MESSAGE", "DIRECT_MESSAGE"):
            return

        message = payload.get("message") or {}
        space = payload.get("space") or {}
        sender = (payload.get("user") or message.get("sender") or {})

        text = message.get("text") or message.get("argumentText") or ""
        thread = message.get("thread") or {}
        space_id = space.get("name") or self._space_id

        msg_id = message.get("name") or f"gchat-{int(datetime.now(UTC).timestamp() * 1000)}"
        sender_id = sender.get("name") or sender.get("displayName") or "unknown"
        sender_name = sender.get("displayName") or sender_id

        chat_type = "direct" if space.get("type") == "DM" else "group"

        # Attachments
        attachments: list[ChatAttachment] = []
        for att in (message.get("attachment") or []):
            mime = att.get("contentType") or ""
            attachments.append(ChatAttachment(
                type=_mime_to_type(mime),
                mime_type=mime or None,
                url=att.get("downloadUri"),
                filename=att.get("name"),
            ))

        inbound = InboundMessage(
            channel_id=self.id,
            message_id=msg_id,
            sender_id=sender_id,
            sender_name=sender_name,
            chat_id=space_id,
            chat_type=chat_type,
            text=text,
            timestamp=message.get("createTime") or datetime.now(UTC).isoformat(),
            reply_to=thread.get("name") or None,
            metadata={
                "space_name": space_id,
                "thread_name": thread.get("name"),
                "message_name": msg_id,
            },
            attachments=attachments,
        )
        await self._handle_message(inbound)

    # -------------------------------------------------------------------------
    # Webhook handler (call from your HTTP server)
    # -------------------------------------------------------------------------

    async def handle_webhook(self, payload: dict[str, Any]) -> None:
        """Process a webhook push from Google Chat.

        Call this from your HTTP framework's webhook endpoint handler.
        The payload is the JSON body of the POST request.
        """
        data = json.dumps(payload).encode("utf-8")
        await self._process_pubsub_message(data)

    # -------------------------------------------------------------------------
    # Outbound — mirrors TS googleChatPlugin send (spaces/{spaceId}/messages)
    # -------------------------------------------------------------------------

    async def send_text(
        self,
        target: str,
        text: str,
        reply_to: str | None = None,
    ) -> str:
        """Send message to a space — mirrors TS Google Chat send

        target format: "spaces/XXXXXX" or bare space ID
        """
        if not self._running:
            raise RuntimeError("Google Chat channel not started")

        space_name = _normalize_space(target or self._space_id)
        if not space_name:
            logger.warning("[googlechat] No target space specified")
            return f"gchat-msg-{int(datetime.now(UTC).timestamp() * 1000)}"

        message_body: dict[str, Any] = {"text": text}
        if reply_to:
            message_body["thread"] = {"name": reply_to}
            message_body["messageReplyOption"] = "REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD"

        try:
            result = await self._chat_api_request(
                "POST",
                f"/v1/{space_name}/messages",
                json=message_body,
            )
            return result.get("name") or f"gchat-{int(datetime.now(UTC).timestamp() * 1000)}"
        except Exception as e:
            logger.error(f"[googlechat] send_text error: {e}", exc_info=True)
            raise

    async def send_media(
        self,
        target: str,
        media_url: str,
        media_type: str,
        caption: str | None = None,
    ) -> str:
        """Send message with media card (Google Chat cards v2 API)"""
        if not self._running:
            raise RuntimeError("Google Chat channel not started")

        space_name = _normalize_space(target or self._space_id)
        if not space_name:
            return f"gchat-media-{int(datetime.now(UTC).timestamp() * 1000)}"

        message_body: dict[str, Any] = {
            "cardsV2": [{
                "cardId": "media-card",
                "card": {
                    "sections": [{
                        "widgets": [{
                            "image": {"imageUrl": media_url, "altText": caption or ""},
                        }]
                    }]
                },
            }]
        }
        if caption:
            message_body["text"] = caption

        try:
            result = await self._chat_api_request(
                "POST",
                f"/v1/{space_name}/messages",
                json=message_body,
            )
            return result.get("name") or f"gchat-{int(datetime.now(UTC).timestamp() * 1000)}"
        except Exception as e:
            logger.error(f"[googlechat] send_media error: {e}", exc_info=True)
            raise

    # -------------------------------------------------------------------------
    # API request helper
    # -------------------------------------------------------------------------

    async def _chat_api_request(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an authenticated request to the Google Chat REST API"""
        if not self._credentials:
            raise RuntimeError("Google Chat: credentials not loaded")

        try:
            import aiohttp
            from google.auth.transport.requests import Request  # type: ignore

            # Refresh credentials if needed
            if not self._credentials.valid:
                self._credentials.refresh(Request())

            headers = {
                "Authorization": f"Bearer {self._credentials.token}",
                "Content-Type": "application/json",
            }

            url = f"{_CHAT_API_BASE}{path}"
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method,
                    url,
                    json=json,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    resp.raise_for_status()
                    return await resp.json()
        except ImportError:
            raise RuntimeError(
                "google-auth not installed. "
                "Install with: pip install google-auth google-api-python-client"
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_space(space: str) -> str:
    """Ensure space ID is in 'spaces/XXXX' format"""
    if not space:
        return ""
    if space.startswith("spaces/"):
        return space
    return f"spaces/{space}"


def _mime_to_type(mime: str) -> str:
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("audio/"):
        return "audio"
    if mime.startswith("video/"):
        return "video"
    return "file"
