"""Telegram voice and video note handling

Determines whether audio should be sent as voice message or audio file,
and handles video notes (circular video bubbles).
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

TELEGRAM_VOICE_AUDIO_EXTENSIONS = {".oga", ".ogg", ".opus", ".mp3", ".m4a"}

TELEGRAM_VOICE_MIME_TYPES = {
    "audio/ogg",
    "audio/opus",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/x-m4a",
    "audio/m4a",
}


def is_telegram_voice_compatible_audio(
    content_type: str | None = None,
    file_name: str | None = None,
) -> bool:
    """
    Check if audio is compatible with Telegram voice messages.
    
    Telegram sendVoice supports OGG/Opus, MP3, and M4A.
    https://core.telegram.org/bots/api#sendvoice
    
    Args:
        content_type: MIME type
        file_name: File name (for extension check)
    
    Returns:
        True if compatible with voice messages
    """
    # Check MIME type
    if content_type:
        mime = content_type.strip().lower()
        if mime in TELEGRAM_VOICE_MIME_TYPES:
            return True
    
    # Check file extension
    if file_name:
        file_name = file_name.strip()
        if file_name:
            ext = Path(file_name).suffix.lower()
            if ext in TELEGRAM_VOICE_AUDIO_EXTENSIONS:
                return True
    
    return False


def resolve_telegram_voice_decision(
    wants_voice: bool,
    content_type: str | None = None,
    file_name: str | None = None,
) -> dict[str, bool | str]:
    """
    Resolve whether to send as voice message or audio file.
    
    Args:
        wants_voice: Whether voice message is requested
        content_type: MIME type
        file_name: File name
    
    Returns:
        Dict with useVoice (bool) and optional reason (str)
    """
    if not wants_voice:
        return {"use_voice": False}
    
    if is_telegram_voice_compatible_audio(content_type, file_name):
        return {"use_voice": True}
    
    content_type_str = content_type or "unknown"
    file_name_str = file_name or "unknown"
    
    return {
        "use_voice": False,
        "reason": f"media is {content_type_str} ({file_name_str})",
    }


def resolve_telegram_voice_send(
    wants_voice: bool,
    content_type: str | None = None,
    file_name: str | None = None,
) -> dict[str, bool]:
    """
    Resolve whether to send as voice message.
    
    Logs fallback reason if voice is requested but not compatible.
    
    Args:
        wants_voice: Whether voice message is requested
        content_type: MIME type
        file_name: File name
    
    Returns:
        Dict with use_voice (bool)
    """
    decision = resolve_telegram_voice_decision(wants_voice, content_type, file_name)
    
    if decision.get("reason"):
        logger.info(
            "Telegram voice requested but %s; sending as audio file instead.",
            decision["reason"]
        )
    
    return {"use_voice": decision["use_voice"]}
