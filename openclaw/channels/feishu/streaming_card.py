"""Feishu streaming card session using the CardKit API.

Provides real-time incremental text output via Feishu's Card Kit streaming API.

Flow:
  1. POST /cardkit/v1/cards          — create streaming card with placeholder
  2. send card reference to chat     — via client.im.v1.message.create/reply
  3. PUT  /cardkit/v1/cards/{id}/elements/content/content  — incremental updates (≤10/s)
  4. PATCH /cardkit/v1/cards/{id}/settings                 — finalize (close streaming)

Protocol (mirrors TS streaming-card.ts exactly):
  - Create body: ``{"type": "card_json", "data": "<JSON string>"}``
  - Card reference in chat: ``{"type": "card", "data": {"card_id": ...}}``
  - Updates use per-update uuid ``s_{cardId}_{sequence}`` (NOT a fixed session UUID)
  - Finalize PATCH body: ``{"settings": "<JSON string>", "sequence": N, "uuid": "c_{cardId}_N"}``
  - Card config contains ``summary``, ``streaming_config`` fields
  - Element has ``element_id: "content"`` for targeted PUT
  - Updates are serialized via asyncio.Queue to prevent out-of-order delivery
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .config import ResolvedFeishuAccount

logger = logging.getLogger(__name__)

# CardKit API throttle: at most 10 updates/second, minimum 100ms between updates
_MIN_UPDATE_INTERVAL = 0.10    # seconds

_THINKING_PLACEHOLDER = "⏳ Thinking..."
_CARDKIT_PATH_CARDS = "/cardkit/v1/cards"

# Default streaming animation params (mirrors TS defaults)
_DEFAULT_PRINT_FREQUENCY_MS = 50   # ms between character renders
_DEFAULT_PRINT_STEP = 2            # chars displayed per animation frame

_SUMMARY_MAX_LEN = 50


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

@dataclass
class StreamingCardHeader:
    """Optional header for streaming cards (title bar with color template).

    Mirrors TS StreamingCardHeader.
    template values: blue, green, red, orange, purple, indigo, wathet,
                     turquoise, yellow, grey, carmine, violet, lime
    """
    title: str
    template: str = "blue"


# ---------------------------------------------------------------------------
# mergeStreamingText — exported utility (mirrors TS)
# ---------------------------------------------------------------------------

def merge_streaming_text(
    previous_text: str | None,
    next_text: str | None,
) -> str:
    """Merge two streaming text chunks, preferring the longer/newer content.

    Mirrors TS ``mergeStreamingText()``:
      - If next is empty → return previous
      - If previous is empty, or next already contains previous → return next
      - If previous contains next (regression) → return previous
      - Otherwise append: ``previous + next``
    """
    previous = previous_text or ""
    next_ = next_text or ""
    if not next_:
        return previous
    if not previous or next_ == previous or next_.find(previous) != -1:
        return next_
    if previous.find(next_) != -1:
        return previous
    return f"{previous}{next_}"


def _truncate_summary(text: str, max_len: int = _SUMMARY_MAX_LEN) -> str:
    """Truncate text for card summary field. Mirrors TS truncateSummary()."""
    if not text:
        return ""
    clean = text.replace("\n", " ").strip()
    return clean if len(clean) <= max_len else clean[: max_len - 3] + "..."


# ---------------------------------------------------------------------------
# Tenant access token (for CardKit API — not covered by SDK auto-token)
# ---------------------------------------------------------------------------

_token_cache: dict[str, tuple[str, float]] = {}   # key → (token, expire_at)


async def _get_tenant_token(
    app_id: str,
    app_secret: str,
    domain_url: str,
) -> str | None:
    """Fetch and cache a tenant_access_token. Mirrors TS getToken()."""
    import aiohttp

    cache_key = f"{domain_url}:{app_id}"
    cached = _token_cache.get(cache_key)
    if cached:
        token, expire_at = cached
        if time.time() < expire_at - 60:
            return token

    url = f"{domain_url}/auth/v3/tenant_access_token/internal"
    payload = {"app_id": app_id, "app_secret": app_secret}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    logger.warning("[feishu] Failed to get tenant token: HTTP %s", resp.status)
                    return None
                data = await resp.json()
                token = data.get("tenant_access_token")
                expire = int(data.get("expire", 7200))
                if token:
                    _token_cache[cache_key] = (token, time.time() + expire)
                    return token
    except Exception as e:
        logger.warning("[feishu] Exception fetching tenant token: %s", e)
    return None


# ---------------------------------------------------------------------------
# CardKit REST helpers
# ---------------------------------------------------------------------------

async def _cardkit_request(
    method: str,
    path: str,
    *,
    token: str,
    domain_url: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Make an authenticated request to the CardKit REST API."""
    import aiohttp

    url = f"{domain_url}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
    }

    try:
        async with aiohttp.ClientSession() as session:
            fn = getattr(session, method.lower())
            kwargs: dict[str, Any] = {
                "headers": headers,
                "timeout": aiohttp.ClientTimeout(total=15),
            }
            if data is not None:
                kwargs["json"] = data

            async with fn(url, **kwargs) as resp:
                if resp.status not in {200, 201, 204}:
                    body = await resp.text()
                    logger.debug(
                        "[feishu] CardKit %s %s → %s: %s", method, path, resp.status, body[:200]
                    )
                    return None
                if resp.status == 204:
                    return {}
                return await resp.json()
    except Exception as e:
        logger.debug("[feishu] CardKit %s %s error: %s", method, path, e)
        return None


# ---------------------------------------------------------------------------
# Streaming card session
# ---------------------------------------------------------------------------

class FeishuStreamingSession:
    """
    Manages a streaming card session for a single reply.

    Protocol (mirrors TS FeishuStreamingSession exactly):
      - POST body: ``{"type": "card_json", "data": "<JSON string>"}``
      - Chat send: ``{"type": "card", "data": {"card_id": ...}}``
      - Update uuid: ``s_{cardId}_{sequence}`` per update
      - Finalize PATCH: ``{"settings": "<JSON string>", "sequence": N, "uuid": "c_{cardId}_N"}``
      - Updates serialized via asyncio.Queue (ordered delivery)

    Usage:
        session = FeishuStreamingSession(client, account)
        await session.start(receive_id, receive_id_type, reply_to_message_id=..., root_id=...)
        await session.update(partial_text)   # call multiple times
        await session.finalize(final_text)
    """

    def __init__(
        self,
        client: Any,
        account: ResolvedFeishuAccount,
        *,
        print_frequency_ms: int = _DEFAULT_PRINT_FREQUENCY_MS,
        print_step: int = _DEFAULT_PRINT_STEP,
        block_coalesce: bool = False,
    ) -> None:
        self._client = client
        self._account = account
        self._card_id: str | None = None
        self._message_id: str | None = None
        self._finalized: bool = False
        self._current_text: str = ""

        # Per-session UUID is not used for update/finalize; we use per-op UUIDs
        self._sequence: int = 0

        # Animation params
        self._print_frequency_ms = print_frequency_ms
        self._print_step = print_step

        # Serialized update queue — guarantees no out-of-order delivery
        self._update_queue: asyncio.Queue[str | None] = asyncio.Queue()
        self._worker_task: asyncio.Task | None = None
        self._last_update_at: float = 0.0

        # blockStreamingCoalesce: if True, sends a single final message instead
        self._block_coalesce = block_coalesce

    async def start(
        self,
        receive_id: str,
        receive_id_type: str,
        *,
        reply_to_message_id: str | None = None,
        reply_in_thread: bool = False,
        root_id: str | None = None,
        header: StreamingCardHeader | None = None,
    ) -> bool:
        """
        Create a streaming card and send it to the chat.

        Returns True on success.
        Mirrors TS FeishuStreamingSession.start() — including root_id and header support.
        """
        token = await _get_tenant_token(
            self._account.app_id,
            self._account.app_secret,
            self._account.domain_url,
        )
        if not token:
            return False

        # Step 1: Create card entity via CardKit API
        # Body shape: {"type": "card_json", "data": "<JSON string>"} — mirrors TS exactly
        card_body = _build_streaming_card_body(
            _THINKING_PLACEHOLDER,
            streaming=True,
            header=header,
        )
        result = await _cardkit_request(
            "POST",
            _CARDKIT_PATH_CARDS,
            token=token,
            domain_url=self._account.domain_url,
            data=card_body,
        )
        # Response shape: {"code": 0, "data": {"card_id": "..."}}
        if not result or not (result.get("data") or {}).get("card_id"):
            logger.warning("[feishu] Failed to create streaming card: %s", result)
            return False

        self._card_id = result["data"]["card_id"]

        # Step 2: Send card reference to chat
        # Reference shape: {"type": "card", "data": {"card_id": "..."}} — NOT "template"
        card_content = json.dumps({"type": "card", "data": {"card_id": self._card_id}})
        msg_id = await _send_card_to_chat(
            self._client,
            receive_id=receive_id,
            receive_id_type=receive_id_type,
            card_content=card_content,
            reply_to_message_id=reply_to_message_id,
            reply_in_thread=reply_in_thread,
            root_id=root_id,
        )
        if not msg_id:
            return False

        self._message_id = msg_id

        # Start background worker to drain update queue serially
        self._worker_task = asyncio.create_task(self._update_worker())
        return True

    async def update(self, text: str) -> None:
        """
        Enqueue an incremental text update.

        Updates are processed serially by the background worker.
        Mirrors TS FeishuStreamingSession.update().
        """
        if self._finalized or not self._card_id:
            return
        if self._block_coalesce:
            return
        merged = merge_streaming_text(self._current_text, text)
        if not merged or merged == self._current_text:
            return
        await self._update_queue.put(merged)

    async def finalize(self, final_text: str) -> str | None:
        """
        Flush queued updates, push final text, and close the streaming session.

        Returns the sent message_id.
        Mirrors TS FeishuStreamingSession.close().
        """
        if self._finalized:
            return self._message_id

        self._finalized = True

        if not self._card_id:
            return None

        # Signal worker to stop after draining
        await self._update_queue.put(None)

        if self._worker_task:
            try:
                await asyncio.wait_for(self._worker_task, timeout=10.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._worker_task.cancel()

        # Merge any remaining pending text into final
        merged_final = merge_streaming_text(self._current_text, final_text)

        # Push final content if it differs from current displayed text
        if merged_final and merged_final != self._current_text:
            await self._push_update(merged_final)

        # Close streaming mode via PATCH /settings
        # Body: {"settings": "<JSON string>", "sequence": N, "uuid": "c_{cardId}_N"}
        token = await _get_tenant_token(
            self._account.app_id,
            self._account.app_secret,
            self._account.domain_url,
        )
        if token and self._card_id:
            self._sequence += 1
            settings_config = {
                "config": {
                    "streaming_mode": False,
                    "summary": {"content": _truncate_summary(self._current_text)},
                }
            }
            await _cardkit_request(
                "PATCH",
                f"{_CARDKIT_PATH_CARDS}/{self._card_id}/settings",
                token=token,
                domain_url=self._account.domain_url,
                data={
                    "settings": json.dumps(settings_config),
                    "sequence": self._sequence,
                    "uuid": f"c_{self._card_id}_{self._sequence}",
                },
            )

        return self._message_id

    def is_active(self) -> bool:
        return self._card_id is not None and not self._finalized

    async def _update_worker(self) -> None:
        """Background task: drain update queue, enforcing rate-limit."""
        while True:
            try:
                text = await self._update_queue.get()
                if text is None:
                    break

                # Rate-limit: ensure at least _MIN_UPDATE_INTERVAL between sends
                now = time.monotonic()
                elapsed = now - self._last_update_at
                if elapsed < _MIN_UPDATE_INTERVAL:
                    await asyncio.sleep(_MIN_UPDATE_INTERVAL - elapsed)

                await self._push_update(text)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug("[feishu] Streaming update worker error: %s", exc)

    async def _push_update(self, text: str) -> None:
        """PUT incremental content to CardKit.

        uuid format: ``s_{cardId}_{sequence}`` — per-update (NOT a fixed session UUID).
        Mirrors TS updateCardContent().
        """
        if not self._card_id:
            return

        token = await _get_tenant_token(
            self._account.app_id,
            self._account.app_secret,
            self._account.domain_url,
        )
        if not token:
            return

        self._sequence += 1
        content_body = {
            "content": text,
            "sequence": self._sequence,
            "uuid": f"s_{self._card_id}_{self._sequence}",  # per-update uuid — mirrors TS
        }
        await _cardkit_request(
            "PUT",
            f"{_CARDKIT_PATH_CARDS}/{self._card_id}/elements/content/content",
            token=token,
            domain_url=self._account.domain_url,
            data=content_body,
        )
        self._current_text = text
        self._last_update_at = time.monotonic()


# ---------------------------------------------------------------------------
# Card builders
# ---------------------------------------------------------------------------

def _build_streaming_card_body(
    text: str,
    *,
    streaming: bool = True,
    header: StreamingCardHeader | None = None,
) -> dict[str, Any]:
    """Build a CardKit card creation body.

    Returns ``{"type": "card_json", "data": "<JSON string>"}`` — mirrors TS exactly.
    The ``data`` field is a JSON-encoded string, not a nested object.
    """
    card_json: dict[str, Any] = {
        "schema": "2.0",
        "config": {
            "streaming_mode": streaming,
            "summary": {"content": "[Generating...]" if streaming else _truncate_summary(text)},
            "streaming_config": {
                "print_frequency_ms": {"default": _DEFAULT_PRINT_FREQUENCY_MS},
                "print_step": {"default": _DEFAULT_PRINT_STEP},
            },
        },
        "body": {
            "elements": [
                {"tag": "markdown", "content": text, "element_id": "content"}
            ]
        },
    }
    if header:
        card_json["header"] = {
            "title": {"tag": "plain_text", "content": header.title},
            "template": header.template or "blue",
        }
    return {
        "type": "card_json",
        "data": json.dumps(card_json),
    }


def build_markdown_card(text: str) -> dict[str, Any]:
    """
    Build a Feishu interactive card with a markdown body element.

    Used when streaming is disabled or render_mode='card'.
    Mirrors TS buildMarkdownCard().
    """
    return {
        "schema": "2.0",
        "config": {"wide_screen_mode": True},
        "body": {
            "elements": [
                {"tag": "markdown", "content": text}
            ]
        },
    }


# ---------------------------------------------------------------------------
# Send card to chat helper
# ---------------------------------------------------------------------------

async def _send_card_to_chat(
    client: Any,
    *,
    receive_id: str,
    receive_id_type: str,
    card_content: str,
    reply_to_message_id: str | None = None,
    reply_in_thread: bool = False,
    root_id: str | None = None,
) -> str | None:
    """Send an interactive card message to a chat or thread.

    Supports root_id routing for topic-group replies (mirrors TS).
    Returns message_id or None.
    """
    from lark_oapi.api.im.v1 import (
        CreateMessageRequest, CreateMessageRequestBody,
        ReplyMessageRequest, ReplyMessageRequestBody,
    )

    loop = asyncio.get_running_loop()

    try:
        # Topic-group thread reply: use root_id routing
        if root_id:
            request = (
                CreateMessageRequest.builder()
                .receive_id_type(receive_id_type)
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(receive_id)
                    .content(card_content)
                    .msg_type("interactive")
                    .build()
                )
                .build()
            )
            # lark_oapi builder may not expose root_id directly; set via dict path
            try:
                req_body = request.request_body
                if hasattr(req_body, "root_id"):
                    req_body.root_id = root_id
            except Exception:
                pass
            response = await loop.run_in_executor(None, lambda: client.im.v1.message.create(request))
        elif reply_to_message_id:
            request = (
                ReplyMessageRequest.builder()
                .message_id(reply_to_message_id)
                .request_body(
                    ReplyMessageRequestBody.builder()
                    .content(card_content)
                    .msg_type("interactive")
                    .reply_in_thread(reply_in_thread)
                    .build()
                )
                .build()
            )
            response = await loop.run_in_executor(None, lambda: client.im.v1.message.reply(request))
        else:
            request = (
                CreateMessageRequest.builder()
                .receive_id_type(receive_id_type)
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(receive_id)
                    .content(card_content)
                    .msg_type("interactive")
                    .build()
                )
                .build()
            )
            response = await loop.run_in_executor(None, lambda: client.im.v1.message.create(request))

        if not response.success():
            logger.warning(
                "[feishu] Failed to send card: code=%s msg=%s", response.code, response.msg
            )
            return None

        return response.data.message_id if response.data else None

    except Exception as e:
        logger.warning("[feishu] Exception sending card: %s", e)
        return None
