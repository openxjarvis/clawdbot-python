"""Telegram reply threading with tags and replyToMode

Parses reply tags like [[reply_to_current]] and [[reply_to:<id>]] and applies
replyToMode filtering (off/first/all) for threaded conversations.
"""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

AUDIO_TAG_RE = re.compile(r"\[\[\s*audio_as_voice\s*\]\]", re.IGNORECASE)
REPLY_TAG_RE = re.compile(
    r"\[\[\s*(?:reply_to_current|reply_to\s*:\s*([^\]\n]+))\s*\]\]",
    re.IGNORECASE
)


def normalize_directive_whitespace(text: str) -> str:
    """Normalize whitespace in directive text"""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"[ \t]*\n[ \t]*", "\n", text)
    return text.strip()


def parse_inline_directives(
    text: str | None = None,
    current_message_id: str | None = None,
    strip_audio_tag: bool = True,
    strip_reply_tags: bool = True,
) -> dict[str, Any]:
    """
    Parse inline directive tags from text.
    
    Supports:
    - [[audio_as_voice]]: Send audio as voice message
    - [[reply_to_current]]: Reply to current message
    - [[reply_to:<id>]]: Reply to specific message ID
    
    Args:
        text: Input text with possible directive tags
        current_message_id: Current message ID for reply_to_current
        strip_audio_tag: Whether to remove audio tag from text
        strip_reply_tags: Whether to remove reply tags from text
    
    Returns:
        Dict with:
            - text: Cleaned text
            - audio_as_voice: Whether to send audio as voice
            - reply_to_id: Resolved reply message ID
            - reply_to_explicit_id: Explicit reply ID from tag
            - reply_to_current: Whether reply_to_current was present
            - has_audio_tag: Whether audio tag was present
            - has_reply_tag: Whether reply tag was present
    """
    if not text:
        return {
            "text": "",
            "audio_as_voice": False,
            "reply_to_id": None,
            "reply_to_explicit_id": None,
            "reply_to_current": False,
            "has_audio_tag": False,
            "has_reply_tag": False,
        }
    
    cleaned = text
    audio_as_voice = False
    has_audio_tag = False
    has_reply_tag = False
    saw_current = False
    last_explicit_id: str | None = None
    
    # Parse audio tag
    def audio_replacer(match):
        nonlocal audio_as_voice, has_audio_tag
        audio_as_voice = True
        has_audio_tag = True
        return " " if strip_audio_tag else match.group(0)
    
    cleaned = AUDIO_TAG_RE.sub(audio_replacer, cleaned)
    
    # Parse reply tags
    def reply_replacer(match):
        nonlocal has_reply_tag, saw_current, last_explicit_id
        has_reply_tag = True
        id_raw = match.group(1)
        
        if id_raw is None:
            # This is [[reply_to_current]]
            saw_current = True
        else:
            # This is [[reply_to:<id>]]
            explicit_id = id_raw.strip()
            if explicit_id:
                last_explicit_id = explicit_id
        
        return " " if strip_reply_tags else match.group(0)
    
    cleaned = REPLY_TAG_RE.sub(reply_replacer, cleaned)
    
    # Normalize whitespace
    cleaned = normalize_directive_whitespace(cleaned)
    
    # Resolve reply_to_id
    reply_to_id = None
    if last_explicit_id:
        reply_to_id = last_explicit_id
    elif saw_current and current_message_id:
        reply_to_id = current_message_id.strip()
    
    return {
        "text": cleaned,
        "audio_as_voice": audio_as_voice,
        "reply_to_id": reply_to_id,
        "reply_to_explicit_id": last_explicit_id,
        "reply_to_current": saw_current,
        "has_audio_tag": has_audio_tag,
        "has_reply_tag": has_reply_tag,
    }


def apply_reply_threading(
    text: str,
    mode: str,
    current_msg_id: str | None = None,
    has_replied: bool = False,
) -> dict[str, Any]:
    """
    Apply reply threading mode to extract reply parameters.
    
    Args:
        text: Message text (may contain reply tags)
        mode: Reply mode ("off", "first", "all")
        current_msg_id: Current message ID (for reply_to_current)
        has_replied: Whether we've already replied in this chain
    
    Returns:
        Dict with:
            - cleaned_text: Text with tags stripped
            - reply_to_message_id: Resolved reply message ID (or None)
            - audio_as_voice: Whether to send audio as voice
    """
    # Parse directives
    parsed = parse_inline_directives(
        text=text,
        current_message_id=current_msg_id,
        strip_audio_tag=True,
        strip_reply_tags=True,
    )
    
    # Determine reply target based on mode
    reply_to_message_id = None
    
    if mode != "off" and parsed["reply_to_id"]:
        # Mode is "first" or "all"
        if mode == "all":
            # Always reply
            reply_to_message_id = parsed["reply_to_id"]
        elif mode == "first" and not has_replied:
            # Only first reply
            reply_to_message_id = parsed["reply_to_id"]
    
    return {
        "cleaned_text": parsed["text"],
        "reply_to_message_id": reply_to_message_id,
        "audio_as_voice": parsed["audio_as_voice"],
    }


def build_reply_parameters(
    reply_to_message_id: int | None = None,
    quote_text: str | None = None,
) -> dict[str, Any]:
    """
    Build Telegram reply_parameters for API calls.
    
    Supports quoting specific text from the replied message.
    
    Args:
        reply_to_message_id: Message ID to reply to
        quote_text: Optional text to quote
    
    Returns:
        Dict with reply_parameters or empty dict
    """
    if reply_to_message_id is None:
        return {}
    
    reply_params: dict[str, Any] = {
        "reply_to_message_id": reply_to_message_id,
    }
    
    # Add quote if provided (Telegram API feature)
    if quote_text:
        reply_params["quote"] = quote_text
    
    return {"reply_parameters": reply_params}
