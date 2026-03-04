"""Outbound message sending for Feishu channel.

Handles: text (post format), interactive cards (markdown), renderMode logic,
reply fallback on withdrawn messages, message edit, card update.

Mirrors TypeScript: extensions/feishu/src/send.ts
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .streaming_card import build_markdown_card

if TYPE_CHECKING:
    from .config import ResolvedFeishuAccount

logger = logging.getLogger(__name__)

# Error codes returned when the reply target message has been withdrawn
_WITHDRAWN_MESSAGE_CODES = {230011, 231003}


# ---------------------------------------------------------------------------
# Render mode detection
# ---------------------------------------------------------------------------

def apply_markdown_mode(text: str, mode: str) -> str:
    """Pre-process text according to markdown config mode.

    - "native"  (default): pass through unchanged
    - "escape":  escape markdown special characters so Feishu shows plain text
    - "strip":   remove all markdown formatting entirely

    Mirrors TS applyMarkdownMode() in send.ts.
    """
    if not mode or mode == "native":
        return text

    if mode == "escape":
        # Escape Feishu markdown special chars: * _ ` ~ [ ] ( )
        import re as _re
        return _re.sub(r"([*_`~\[\]()])", r"\\\1", text)

    if mode == "strip":
        import re as _re
        # Strip bold/italic/code inline
        text = _re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        text = _re.sub(r"\*(.+?)\*", r"\1", text)
        text = _re.sub(r"__(.+?)__", r"\1", text)
        text = _re.sub(r"_(.+?)_", r"\1", text)
        text = _re.sub(r"`{3}[^\n]*\n(.*?)`{3}", r"\1", text, flags=_re.DOTALL)
        text = _re.sub(r"`(.+?)`", r"\1", text)
        # Strip headers
        text = _re.sub(r"^#+\s+", "", text, flags=_re.MULTILINE)
        # Strip table pipes
        text = _re.sub(r"^\|.*\|$", "", text, flags=_re.MULTILINE)
        # Strip blockquotes
        text = _re.sub(r"^>\s*", "", text, flags=_re.MULTILINE)
        return text.strip()

    return text


def _should_use_card(text: str, render_mode: str) -> bool:
    """
    Determine whether to render as an interactive card.

    - "auto":  use card if text contains code fences (```) or markdown tables
    - "card":  always use card
    - "raw":   always use post text

    Mirrors TS auto-render logic.
    """
    if render_mode == "raw":
        return False
    if render_mode == "card":
        return True
    # auto
    if "```" in text:
        return True
    if re.search(r"^\|.+\|", text, re.MULTILINE):
        return True
    return False


# ---------------------------------------------------------------------------
# Content builders
# ---------------------------------------------------------------------------

def build_post_message_payload(text: str) -> dict[str, Any]:
    """
    Build a Feishu 'post' message content dict.

    Uses the zh_cn locale with a single md-tagged paragraph.
    Mirrors TS buildFeishuPostMessagePayload().
    """
    return {
        "zh_cn": {
            "content": [[{"tag": "md", "text": text}]]
        }
    }


def build_interactive_card_content(text: str) -> str:
    """
    Build a JSON string for an interactive card message.

    Mirrors TS buildMarkdownCard() + JSON.stringify.
    """
    card = build_markdown_card(text)
    return json.dumps(card)


# ---------------------------------------------------------------------------
# Send helpers
# ---------------------------------------------------------------------------

@dataclass
class SendResult:
    message_id: str
    was_fallback: bool = False   # True if reply fell back to create


async def send_feishu_message(
    client: Any,
    *,
    receive_id: str,
    receive_id_type: str,
    text: str,
    render_mode: str = "auto",
    reply_to_message_id: str | None = None,
    reply_in_thread: bool = False,
    markdown_mode: str = "native",
) -> SendResult | None:
    """
    Send a text message to Feishu.

    Chooses post vs interactive card based on render_mode.
    Falls back from reply to create on withdrawn-message errors.

    Mirrors TS sendMessageFeishu().
    """
    from lark_oapi.api.im.v1 import (
        CreateMessageRequest, CreateMessageRequestBody,
        ReplyMessageRequest, ReplyMessageRequestBody,
    )

    # Apply markdown mode preprocessing (mirrors TS applyMarkdownMode)
    processed_text = apply_markdown_mode(text, markdown_mode)

    use_card = _should_use_card(processed_text, render_mode)

    if use_card:
        msg_type = "interactive"
        content = build_interactive_card_content(processed_text)
    else:
        msg_type = "post"
        content = json.dumps(build_post_message_payload(processed_text))

    loop = asyncio.get_running_loop()

    async def _do_reply(mid: str) -> Any:
        request = (
            ReplyMessageRequest.builder()
            .message_id(mid)
            .request_body(
                ReplyMessageRequestBody.builder()
                .content(content)
                .msg_type(msg_type)
                .reply_in_thread(reply_in_thread)
                .build()
            )
            .build()
        )
        return await loop.run_in_executor(None, lambda: client.im.v1.message.reply(request))

    async def _do_create() -> Any:
        request = (
            CreateMessageRequest.builder()
            .receive_id_type(receive_id_type)
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(receive_id)
                .content(content)
                .msg_type(msg_type)
                .build()
            )
            .build()
        )
        return await loop.run_in_executor(None, lambda: client.im.v1.message.create(request))

    was_fallback = False

    if reply_to_message_id:
        response = await _do_reply(reply_to_message_id)
        if not response.success():
            if response.code in _WITHDRAWN_MESSAGE_CODES:
                # Reply target was withdrawn — fall back to create
                logger.debug(
                    "[feishu] Reply target withdrawn (code=%s), falling back to create",
                    response.code,
                )
                response = await _do_create()
                was_fallback = True
            else:
                logger.warning(
                    "[feishu] Failed to reply: code=%s msg=%s", response.code, response.msg
                )
                return None
    else:
        response = await _do_create()

    if not response.success():
        logger.warning("[feishu] Failed to send message: code=%s msg=%s", response.code, response.msg)
        return None

    msg_id = response.data.message_id if response.data else ""
    return SendResult(message_id=msg_id, was_fallback=was_fallback)


async def edit_feishu_message(
    client: Any,
    message_id: str,
    *,
    text: str,
    render_mode: str = "auto",
) -> bool:
    """
    Edit an existing Feishu message (24-hour edit window).

    Mirrors TS editMessageFeishu() / client.im.message.update.
    """
    from lark_oapi.api.im.v1 import UpdateMessageRequest, UpdateMessageRequestBody

    use_card = _should_use_card(text, render_mode)
    if use_card:
        msg_type = "interactive"
        content = build_interactive_card_content(text)
    else:
        msg_type = "post"
        content = json.dumps(build_post_message_payload(text))

    loop = asyncio.get_running_loop()
    try:
        request = (
            UpdateMessageRequest.builder()
            .message_id(message_id)
            .request_body(
                UpdateMessageRequestBody.builder()
                .content(content)
                .msg_type(msg_type)
                .build()
            )
            .build()
        )
        response = await loop.run_in_executor(None, lambda: client.im.v1.message.update(request))
        if not response.success():
            logger.warning(
                "[feishu] Failed to edit message %s: code=%s msg=%s",
                message_id, response.code, response.msg,
            )
            return False
        return True
    except Exception as e:
        logger.warning("[feishu] Exception editing message %s: %s", message_id, e)
        return False


async def patch_feishu_card(
    client: Any,
    message_id: str,
    card: dict[str, Any],
) -> bool:
    """
    Patch (update) an interactive card message.

    Mirrors TS client.im.message.patch.
    """
    from lark_oapi.api.im.v1 import PatchMessageRequest, PatchMessageRequestBody

    loop = asyncio.get_running_loop()
    try:
        request = (
            PatchMessageRequest.builder()
            .message_id(message_id)
            .request_body(
                PatchMessageRequestBody.builder()
                .content(json.dumps(card))
                .build()
            )
            .build()
        )
        response = await loop.run_in_executor(None, lambda: client.im.v1.message.patch(request))
        if not response.success():
            logger.warning(
                "[feishu] Failed to patch card %s: code=%s msg=%s",
                message_id, response.code, response.msg,
            )
            return False
        return True
    except Exception as e:
        logger.warning("[feishu] Exception patching card %s: %s", message_id, e)
        return False


async def get_feishu_message(client: Any, message_id: str) -> dict[str, Any] | None:
    """Fetch a single message by ID."""
    from lark_oapi.api.im.v1 import GetMessageRequest

    loop = asyncio.get_running_loop()
    try:
        request = GetMessageRequest.builder().message_id(message_id).build()
        response = await loop.run_in_executor(None, lambda: client.im.v1.message.get(request))
        if not response.success():
            return None
        if response.data and response.data.items:
            item = response.data.items[0]
            return {
                "message_id": getattr(item, "message_id", ""),
                "chat_id": getattr(item, "chat_id", ""),
                "msg_type": getattr(item, "msg_type", ""),
                "content": getattr(item, "body", {}).get("content", "") if isinstance(getattr(item, "body", None), dict) else "",
            }
        return None
    except Exception as e:
        logger.debug("[feishu] Exception fetching message %s: %s", message_id, e)
        return None


# ---------------------------------------------------------------------------
# Text chunking
# ---------------------------------------------------------------------------

def chunk_text(text: str, limit: int, mode: str = "length") -> list[str]:
    """
    Split text into chunks at the given character limit.

    mode='length':  split purely by character count
    mode='newline': prefer splitting at newlines

    Mirrors TS textChunkLimit + chunkMode logic.
    """
    if len(text) <= limit:
        return [text]

    if mode == "newline":
        parts: list[str] = []
        current: list[str] = []
        current_len = 0
        for line in text.splitlines(keepends=True):
            if current_len + len(line) > limit and current:
                parts.append("".join(current))
                current = []
                current_len = 0
            current.append(line)
            current_len += len(line)
        if current:
            parts.append("".join(current))
        return parts

    # length mode
    chunks = []
    while text:
        chunks.append(text[:limit])
        text = text[limit:]
    return chunks
