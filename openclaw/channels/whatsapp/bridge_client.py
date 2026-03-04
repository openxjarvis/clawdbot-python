"""Async HTTP client for the Baileys bridge REST API."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class BridgeClient:
    """Async HTTP client wrapping the Baileys bridge REST API."""

    def __init__(self, base_url: str, secret: str = "") -> None:
        self._base_url = base_url.rstrip("/")
        self._secret = secret
        self._session: Any = None  # aiohttp.ClientSession

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {"Content-Type": "application/json"}
        if self._secret:
            h["Authorization"] = f"Bearer {self._secret}"
        return h

    async def _session_obj(self) -> Any:
        if self._session is None or self._session.closed:
            import aiohttp  # type: ignore
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _get(self, path: str) -> dict[str, Any]:
        import aiohttp  # type: ignore
        sess = await self._session_obj()
        async with sess.get(
            f"{self._base_url}{path}",
            headers=self._headers(),
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            resp.raise_for_status()
            return await resp.json()  # type: ignore

    async def _post(self, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        import aiohttp  # type: ignore
        sess = await self._session_obj()
        async with sess.post(
            f"{self._base_url}{path}",
            json=body or {},
            headers=self._headers(),
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            resp.raise_for_status()
            return await resp.json()  # type: ignore

    async def _delete(self, path: str) -> dict[str, Any]:
        import aiohttp  # type: ignore
        sess = await self._session_obj()
        async with sess.delete(
            f"{self._base_url}{path}",
            headers=self._headers(),
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            resp.raise_for_status()
            return await resp.json()  # type: ignore

    # ---- Sessions ----

    async def start_session(
        self,
        account_id: str,
        auth_dir: str,
        event_webhook_url: str,
    ) -> dict[str, Any]:
        """Create or reconnect a session."""
        return await self._post("/sessions", {
            "accountId": account_id,
            "authDir": auth_dir,
            "eventWebhookUrl": event_webhook_url,
        })

    async def stop_session(self, account_id: str) -> dict[str, Any]:
        """Disconnect a session."""
        return await self._delete(f"/sessions/{account_id}")

    async def get_sessions(self) -> dict[str, Any]:
        """List all sessions."""
        return await self._get("/sessions")

    # ---- QR ----

    async def get_qr(self, account_id: str) -> dict[str, Any]:
        """
        Get QR code data URL. Returns {"qr": "<data-url>"} or {"status": "pending"} (202).
        """
        import aiohttp  # type: ignore
        sess = await self._session_obj()
        async with sess.get(
            f"{self._base_url}/sessions/{account_id}/qr",
            headers=self._headers(),
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            return await resp.json()  # type: ignore

    # ---- Status ----

    async def get_status(self, account_id: str) -> dict[str, Any]:
        """Get session status."""
        return await self._get(f"/sessions/{account_id}/status")

    # ---- Send ----

    async def send_message(
        self,
        account_id: str,
        to: str,
        text: str,
        reply_to: str | None = None,
    ) -> dict[str, Any]:
        """Send a text message."""
        body: dict[str, Any] = {"to": to, "text": text}
        if reply_to:
            body["replyTo"] = reply_to
        return await self._post(f"/sessions/{account_id}/send", body)

    async def send_media(
        self,
        account_id: str,
        to: str,
        media_bytes: bytes,
        mime_type: str,
        caption: str | None = None,
        file_name: str | None = None,
    ) -> dict[str, Any]:
        """Send a media message (image, video, audio, document)."""
        import base64
        body: dict[str, Any] = {
            "to": to,
            "mediaBase64": base64.b64encode(media_bytes).decode(),
            "mimeType": mime_type,
        }
        if caption:
            body["caption"] = caption
        if file_name:
            body["fileName"] = file_name
        return await self._post(f"/sessions/{account_id}/send_media", body)

    async def send_reaction(
        self,
        account_id: str,
        to: str,
        message_id: str,
        emoji: str,
        remove: bool = False,
        from_me: bool = False,
    ) -> dict[str, Any]:
        """Send or remove an emoji reaction."""
        return await self._post(f"/sessions/{account_id}/react", {
            "to": to,
            "messageId": message_id,
            "emoji": emoji,
            "remove": remove,
            "fromMe": from_me,
        })

    async def send_poll(
        self,
        account_id: str,
        to: str,
        question: str,
        options: list[str],
        max_selections: int = 1,
    ) -> dict[str, Any]:
        """Send a poll."""
        return await self._post(f"/sessions/{account_id}/poll", {
            "to": to,
            "question": question,
            "options": options,
            "maxSelections": max_selections,
        })

    async def mark_read(
        self,
        account_id: str,
        keys: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Mark messages as read."""
        return await self._post(f"/sessions/{account_id}/read", {"keys": keys})

    async def logout(self, account_id: str) -> dict[str, Any]:
        """Logout and clear auth."""
        return await self._post(f"/sessions/{account_id}/logout")

    # ---- Health ----

    async def health_check(self) -> bool:
        """Return True if bridge is reachable."""
        try:
            import aiohttp  # type: ignore
            sess = await self._session_obj()
            async with sess.get(
                f"{self._base_url}/health",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                return resp.status == 200
        except Exception:
            return False
