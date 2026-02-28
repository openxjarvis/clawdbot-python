"""WhatsApp channel implementation — aligned with TS whatsAppPlugin

Aligns with TS loginWithQrStart / loginWithQrWait / heartbeatCheckReady.
Supports two backends:
  1. "web"  — uses whatsapp-web.py (Selenium-based, unofficial)
  2. "business-api" — uses WhatsApp Business API (official HTTP)
"""
from __future__ import annotations


import asyncio
import logging
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from ..base import ChannelCapabilities, ChannelPlugin, InboundMessage

logger = logging.getLogger(__name__)

# Heartbeat check interval (seconds) — mirrors TS heartbeatInterval
_HEARTBEAT_INTERVAL = 30.0


class WhatsAppProvider(str, Enum):
    WEB = "web"
    BUSINESS_API = "business-api"


class WhatsAppChannel(ChannelPlugin):
    """WhatsApp channel — framework aligned with TS whatsAppPlugin

    Account fields (TS ResolvedWhatsAppAccount):
        auth_dir   — directory to persist Baileys/web session (TS: authDir)
        provider   — "web" | "business-api"
        media_max_mb — max attachment size in MB
        phone_number — E.164 phone for Business API

    QR login flow (mirrors TS):
        1. call login_with_qr_start() -> returns QR data string
        2. call login_with_qr_wait(qr) -> waits for scan
        3. heartbeat_check_ready() -> checks auth + listener active

    Note: Full "web" implementation requires whatsapp-web.py or a Baileys bridge.
          "business-api" uses Meta's Cloud API (requires Meta approval).
    """

    def __init__(self):
        super().__init__()
        self.id = "whatsapp"
        self.label = "WhatsApp"
        self.capabilities = ChannelCapabilities(
            chat_types=["direct", "group"],
            supports_media=True,
            supports_reactions=True,
            supports_threads=False,
            supports_polls=False,
            supports_reply=True,
        )
        self._client: Any | None = None
        # Account fields
        self._provider: WhatsAppProvider = WhatsAppProvider.WEB
        self._auth_dir: str = ".whatsapp-auth"
        self._media_max_mb: int = 16
        self._phone_number: str = ""
        self._api_token: str = ""
        self._api_base_url: str = "https://graph.facebook.com/v18.0"
        # QR login state
        self._qr_data: str | None = None
        self._qr_event: asyncio.Event = asyncio.Event()
        self._authenticated: bool = False
        self._listener_active: bool = False
        self._heartbeat_task: asyncio.Task | None = None

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    async def start(self, config: dict[str, Any]) -> None:
        """Start WhatsApp client — mirrors TS whatsAppPlugin.start()"""
        provider_str = config.get("provider") or "web"
        try:
            self._provider = WhatsAppProvider(provider_str)
        except ValueError:
            logger.warning(f"[whatsapp] Unknown provider '{provider_str}', using 'web'")
            self._provider = WhatsAppProvider.WEB

        self._auth_dir = config.get("authDir") or config.get("auth_dir") or ".whatsapp-auth"
        self._media_max_mb = int(config.get("mediaMaxMb") or config.get("media_max_mb") or 16)
        self._phone_number = config.get("phoneNumber") or config.get("phone_number") or ""
        self._api_token = config.get("apiToken") or config.get("api_token") or ""
        self._api_base_url = (
            config.get("apiBaseUrl") or config.get("api_base_url")
            or "https://graph.facebook.com/v18.0"
        )

        logger.info(f"[whatsapp] Starting channel (provider={self._provider.value})")

        if self._provider == WhatsAppProvider.BUSINESS_API:
            await self._start_business_api()
        else:
            await self._start_web()

        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("[whatsapp] Channel started")

    async def _start_web(self) -> None:
        """Initialize whatsapp-web.py client"""
        try:
            from webwhatsapi import WhatsAPIDriver  # type: ignore
            logger.info("[whatsapp] Using whatsapp-web.py (web provider)")
            # Actual initialization requires Selenium + browser
            # This is a framework skeleton — full implementation needs webwhatsapi
            self._authenticated = False
            self._listener_active = False
        except ImportError:
            logger.warning(
                "[whatsapp] whatsapp-web.py not installed. "
                "Install with: pip install webwhatsapi  (requires Selenium + Chrome)"
            )
            self._authenticated = False
            self._listener_active = False

    async def _start_business_api(self) -> None:
        """Initialize WhatsApp Business Cloud API client"""
        if not self._api_token:
            logger.warning("[whatsapp] Business API token not set (config key: apiToken)")
        # Business API is stateless HTTP — mark as authenticated if token present
        self._authenticated = bool(self._api_token)
        self._listener_active = False  # Requires webhook endpoint to be configured

    async def stop(self) -> None:
        """Stop WhatsApp client"""
        logger.info("[whatsapp] Stopping channel...")
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        if self._client:
            try:
                if hasattr(self._client, "close"):
                    await self._client.close()
            except Exception:
                pass
        self._authenticated = False
        self._listener_active = False

    # -------------------------------------------------------------------------
    # QR Login flow — mirrors TS loginWithQrStart / loginWithQrWait
    # -------------------------------------------------------------------------

    async def login_with_qr_start(self) -> str:
        """Start QR login flow — mirrors TS loginWithQrStart().

        Returns the QR code data string for the caller to render.
        """
        logger.info("[whatsapp] Starting QR login flow")
        self._qr_event.clear()
        self._qr_data = None

        if self._provider == WhatsAppProvider.WEB:
            try:
                qr_data = await self._generate_web_qr()
                self._qr_data = qr_data
                return qr_data
            except Exception as e:
                logger.error(f"[whatsapp] QR generation failed: {e}")
                return "QR_CODE_UNAVAILABLE"
        else:
            logger.warning("[whatsapp] QR login not supported for business-api provider")
            return "QR_NOT_SUPPORTED"

    async def _generate_web_qr(self) -> str:
        """Generate QR code via whatsapp-web.py — framework stub"""
        # Actual implementation with webwhatsapi:
        #   qr_code = self._client.get_qr()
        #   return qr_code
        logger.warning("[whatsapp] QR generation requires whatsapp-web.py + Selenium")
        return "QR_CODE_PLACEHOLDER"

    async def login_with_qr_wait(self, qr_data: str, timeout: float = 60.0) -> bool:
        """Wait for QR code to be scanned — mirrors TS loginWithQrWait().

        Returns True if authenticated, False on timeout.
        """
        logger.info(f"[whatsapp] Waiting for QR scan (timeout={timeout}s)")
        try:
            await asyncio.wait_for(self._qr_event.wait(), timeout=timeout)
            return self._authenticated
        except asyncio.TimeoutError:
            logger.warning("[whatsapp] QR scan timed out")
            return False

    def on_qr_authenticated(self) -> None:
        """Call this when QR authentication succeeds (from web driver callback)"""
        logger.info("[whatsapp] QR authentication successful")
        self._authenticated = True
        self._qr_event.set()

    # -------------------------------------------------------------------------
    # Heartbeat — mirrors TS heartbeatCheckReady (three checks)
    # -------------------------------------------------------------------------

    async def heartbeat_check_ready(self) -> dict[str, bool]:
        """Check channel readiness — mirrors TS heartbeatCheckReady three checks.

        Returns dict with:
            authenticated: bool   — auth credentials valid
            listener_active: bool — message listener is running
            ready: bool           — overall ready state
        """
        checks = {
            "authenticated": self._authenticated,
            "listener_active": self._listener_active,
            "ready": self._authenticated and self._listener_active,
        }

        if self._provider == WhatsAppProvider.BUSINESS_API and self._api_token:
            # For Business API: verify token via lightweight API call
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{self._api_base_url}/me",
                        headers={"Authorization": f"Bearer {self._api_token}"},
                        timeout=aiohttp.ClientTimeout(total=5),
                    ) as resp:
                        checks["authenticated"] = resp.status == 200
            except Exception:
                checks["authenticated"] = False

        checks["ready"] = checks["authenticated"] and (
            checks["listener_active"] or self._provider == WhatsAppProvider.BUSINESS_API
        )
        return checks

    async def _heartbeat_loop(self) -> None:
        """Periodic heartbeat check — mirrors TS heartbeat polling"""
        while self._running:
            try:
                await asyncio.sleep(_HEARTBEAT_INTERVAL)
                if not self._running:
                    break
                status = await self.heartbeat_check_ready()
                if not status["ready"]:
                    logger.warning(f"[whatsapp] Heartbeat check failed: {status}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"[whatsapp] Heartbeat error: {e}")

    # -------------------------------------------------------------------------
    # Outbound
    # -------------------------------------------------------------------------

    async def send_text(
        self,
        target: str,
        text: str,
        reply_to: str | None = None,
    ) -> str:
        """Send text message"""
        if not self._running:
            raise RuntimeError("WhatsApp channel not started")

        if self._provider == WhatsAppProvider.BUSINESS_API:
            return await self._send_business_api_text(target, text, reply_to)

        # Web provider — framework stub
        logger.warning(f"[whatsapp] send_text (web) not fully implemented: {target}")
        return f"whatsapp-msg-{int(datetime.now(UTC).timestamp() * 1000)}"

    async def _send_business_api_text(
        self,
        to: str,
        text: str,
        reply_to: str | None = None,
    ) -> str:
        """Send via WhatsApp Business Cloud API"""
        if not self._api_token or not self._phone_number:
            raise RuntimeError("WhatsApp Business API: apiToken and phoneNumber required")

        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text},
        }
        if reply_to:
            payload["context"] = {"message_id": reply_to}

        try:
            import aiohttp
            url = f"{self._api_base_url}/{self._phone_number}/messages"
            headers = {
                "Authorization": f"Bearer {self._api_token}",
                "Content-Type": "application/json",
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                    messages = data.get("messages") or []
                    if messages:
                        return messages[0].get("id", "")
                    return f"whatsapp-{int(datetime.now(UTC).timestamp() * 1000)}"
        except Exception as e:
            logger.error(f"[whatsapp] Business API send error: {e}", exc_info=True)
            raise

    async def send_media(
        self,
        target: str,
        media_url: str,
        media_type: str,
        caption: str | None = None,
    ) -> str:
        """Send media message"""
        if not self._running:
            raise RuntimeError("WhatsApp channel not started")

        if self._provider == WhatsAppProvider.BUSINESS_API:
            return await self._send_business_api_media(target, media_url, media_type, caption)

        logger.warning(f"[whatsapp] send_media (web) not fully implemented: {target}")
        return f"whatsapp-media-{int(datetime.now(UTC).timestamp() * 1000)}"

    async def _send_business_api_media(
        self,
        to: str,
        media_url: str,
        media_type: str,
        caption: str | None = None,
    ) -> str:
        """Send media via WhatsApp Business Cloud API"""
        if not self._api_token or not self._phone_number:
            raise RuntimeError("WhatsApp Business API: apiToken and phoneNumber required")

        msg_type = "image" if media_type.startswith("image/") else (
            "video" if media_type.startswith("video/") else (
                "audio" if media_type.startswith("audio/") else "document"
            )
        )

        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": msg_type,
            msg_type: {"link": media_url},
        }
        if caption and msg_type in ("image", "video", "document"):
            payload[msg_type]["caption"] = caption

        try:
            import aiohttp
            url = f"{self._api_base_url}/{self._phone_number}/messages"
            headers = {
                "Authorization": f"Bearer {self._api_token}",
                "Content-Type": "application/json",
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                    messages = data.get("messages") or []
                    return messages[0].get("id", "") if messages else ""
        except Exception as e:
            logger.error(f"[whatsapp] Business API media send error: {e}", exc_info=True)
            raise
