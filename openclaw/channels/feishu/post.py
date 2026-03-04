"""Parse Feishu rich-text 'post' message format into plain text.

The Feishu 'post' message type uses a JSON structure with paragraphs and inline tags.
This module flattens it to a clean text string for the agent.

Mirrors TypeScript: extensions/feishu/src/post.ts
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class PostMediaRef:
    """An embedded image or video reference found in a post message."""
    type: str           # "image" | "video"
    image_key: str = ""
    file_key: str = ""


@dataclass
class PostParseResult:
    """Result of parsing a Feishu post message."""
    text: str
    media_refs: list[PostMediaRef]


# ---------------------------------------------------------------------------
# Tag handlers
# ---------------------------------------------------------------------------

def _tag_to_text(element: dict[str, Any]) -> tuple[str, PostMediaRef | None]:
    """Convert a single post tag element to (text_contribution, optional_media_ref)."""
    tag = element.get("tag", "")

    if tag == "text":
        style = element.get("style") or []
        text = element.get("text", "")
        if "bold" in style:
            text = f"**{text}**"
        if "italic" in style:
            text = f"*{text}*"
        if "strikethrough" in style:
            text = f"~~{text}~~"
        return text, None

    if tag == "a":
        text = element.get("text", "")
        href = element.get("href", "")
        if href:
            return f"[{text}]({href})", None
        return text, None

    if tag == "at":
        user_id = element.get("user_id", "")
        user_name = element.get("user_name", "")
        name = user_name or user_id
        return f"@{name}", None

    if tag == "img":
        image_key = element.get("image_key", "")
        return "", PostMediaRef(type="image", image_key=image_key)

    if tag == "media":
        image_key = element.get("image_key", "")
        file_key = element.get("file_key", "")
        return "", PostMediaRef(type="video", image_key=image_key, file_key=file_key)

    if tag == "emotion":
        # Emoji
        emoji = element.get("emoji_type", "")
        return f":{emoji}:", None

    if tag == "code_block":
        code = element.get("code", "") or element.get("text", "")
        language = element.get("language", "")
        return f"\n```{language}\n{code}\n```\n", None

    if tag == "md":
        # Markdown inline content (used in some message types)
        return element.get("text", ""), None

    # Unknown tag — try to extract any text
    return element.get("text", ""), None


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

def parse_post_content(content_raw: str | dict[str, Any] | None) -> PostParseResult:
    """
    Parse a Feishu 'post' message content into plain text + media refs.

    The post format is:
    {
      "zh_cn": {
        "title": "...",
        "content": [
          [  // paragraph
            {"tag": "text", "text": "Hello"},
            {"tag": "a", "href": "...", "text": "link"},
          ],
        ]
      }
    }

    Mirrors TS parsePostContent().
    """
    if not content_raw:
        return PostParseResult(text="", media_refs=[])

    try:
        if isinstance(content_raw, str):
            data = json.loads(content_raw)
        else:
            data = content_raw
    except (json.JSONDecodeError, TypeError):
        return PostParseResult(text=str(content_raw), media_refs=[])

    # Try zh_cn first, then any available locale
    locale_data = data.get("zh_cn") or data.get("en_us") or next(iter(data.values()), {})
    if not isinstance(locale_data, dict):
        return PostParseResult(text="", media_refs=[])

    title = locale_data.get("title", "")
    paragraphs: list[list[dict[str, Any]]] = locale_data.get("content") or []

    parts: list[str] = []
    media_refs: list[PostMediaRef] = []

    if title:
        parts.append(f"**{title}**\n")

    for paragraph in paragraphs:
        if not isinstance(paragraph, list):
            continue
        para_parts: list[str] = []
        for element in paragraph:
            if not isinstance(element, dict):
                continue
            text_part, media_ref = _tag_to_text(element)
            if text_part:
                para_parts.append(text_part)
            if media_ref:
                media_refs.append(media_ref)
        if para_parts:
            parts.append("".join(para_parts))

    return PostParseResult(
        text="\n".join(parts).strip(),
        media_refs=media_refs,
    )


def parse_text_content(content_raw: str | None) -> str:
    """Parse a plain text message content (msg_type='text')."""
    if not content_raw:
        return ""
    try:
        data = json.loads(content_raw)
        return str(data.get("text", ""))
    except (json.JSONDecodeError, TypeError):
        return str(content_raw)
