"""
Discord media handling — attachment download/upload and voice messages.
Mirrors src/discord/send.outbound.ts (sendDiscordMedia, sendVoiceMessageDiscord)
and the inbound attachment pipeline.
"""
from __future__ import annotations

import asyncio
import base64
import io
import logging
import mimetypes
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import aiohttp

if TYPE_CHECKING:
    import discord as _discord

from ..base import ChatAttachment

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SSRF / local-IP guard — mirrors TS ssrfGuard
# ---------------------------------------------------------------------------

_LOCAL_PATTERNS = re.compile(
    r"^(localhost|127\.|10\.|172\.(1[6-9]|2\d|3[01])\.|192\.168\.|0\.0\.0\.0)",
    re.IGNORECASE,
)


def _is_safe_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        if _LOCAL_PATTERNS.match(host):
            return False
        return parsed.scheme in ("http", "https")
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Attachment download (inbound)
# ---------------------------------------------------------------------------

def _mime_to_type(mime: str | None) -> str:
    if not mime:
        return "file"
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("audio/"):
        return "audio"
    if mime.startswith("video/"):
        return "video"
    return "file"


async def download_attachment(
    att: Any,
    max_bytes: int,
    session: aiohttp.ClientSession,
) -> ChatAttachment | None:
    """
    Download a single Discord attachment and return a ChatAttachment.
    Returns None if the attachment is too large or download fails.
    Mirrors TS inbound attachment handling with size gating.
    """
    size: int = getattr(att, "size", 0) or 0
    if size > max_bytes:
        logger.debug(
            "[discord][media] Skipping large attachment %s (%d bytes > %d limit)",
            getattr(att, "filename", "?"),
            size,
            max_bytes,
        )
        return None

    url: str = str(att.url)
    if not _is_safe_url(url):
        logger.warning("[discord][media] Blocked unsafe attachment URL: %s", url)
        return None

    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                logger.warning("[discord][media] Failed to download %s: HTTP %d", url, resp.status)
                return None
            data = await resp.read()

        content_b64 = base64.b64encode(data).decode()
        mime = getattr(att, "content_type", None)
        filename = getattr(att, "filename", None)

        return ChatAttachment(
            type=_mime_to_type(mime),
            mime_type=mime,
            content=content_b64,
            url=url,
            filename=filename,
            size=size,
        )
    except Exception as exc:
        logger.warning("[discord][media] Failed to download attachment: %s", exc)
        return None


async def download_all_attachments(
    attachments: list[Any],
    max_mb: int = 8,
) -> list[ChatAttachment]:
    """Download all attachments from a Discord message up to `max_mb` each."""
    max_bytes = max_mb * 1024 * 1024
    results: list[ChatAttachment] = []
    async with aiohttp.ClientSession() as session:
        for att in attachments:
            ca = await download_attachment(att, max_bytes, session)
            if ca:
                results.append(ca)
    return results


# ---------------------------------------------------------------------------
# Outbound media send — mirrors sendDiscordMedia
# ---------------------------------------------------------------------------

async def load_outbound_media(url_or_path: str) -> tuple[bytes, str]:
    """
    Load media from a URL or local file path.
    Returns (data, filename).
    """
    if url_or_path.startswith("http"):
        if not _is_safe_url(url_or_path):
            raise ValueError(f"Blocked unsafe media URL: {url_or_path}")
        async with aiohttp.ClientSession() as session:
            async with session.get(url_or_path, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"HTTP {resp.status} downloading media")
                data = await resp.read()
        filename = url_or_path.split("/")[-1].split("?")[0] or "media"
        return data, filename
    else:
        path = Path(url_or_path)
        data = path.read_bytes()
        return data, path.name


# ---------------------------------------------------------------------------
# Voice message — mirrors sendVoiceMessageDiscord
# ---------------------------------------------------------------------------

def _convert_to_opus(input_path: str, output_path: str) -> bool:
    """
    Convert audio file to OGG/Opus using ffmpeg.
    Returns True on success.
    Discord voice messages require OGG/Opus format.
    """
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", input_path,
                "-c:a", "libopus",
                "-b:a", "64k",
                "-vbr", "on",
                "-compression_level", "10",
                output_path,
            ],
            capture_output=True,
            timeout=60,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.warning("[discord][media] ffmpeg conversion failed: %s", exc)
        return False


def _compute_waveform(data: bytes) -> bytes:
    """
    Compute a 256-sample waveform from raw PCM audio.
    Discord voice messages include a waveform visualization array.
    Returns 256 bytes in [0, 255] range.
    Mirrors TS waveform computation in voice-message.ts.
    """
    if len(data) < 2:
        return bytes(256)

    # Interpret as 16-bit LE PCM samples
    sample_count = len(data) // 2
    samples = [
        abs(int.from_bytes(data[i * 2: i * 2 + 2], "little", signed=True))
        for i in range(sample_count)
    ]

    bucket_size = max(1, sample_count // 256)
    waveform = []
    for i in range(256):
        start = i * bucket_size
        chunk = samples[start: start + bucket_size]
        avg = sum(chunk) // len(chunk) if chunk else 0
        # Normalize 16-bit range to 0-255
        waveform.append(min(255, avg * 255 // 32768))

    return bytes(waveform)


async def send_voice_message(
    channel: Any,
    audio_path: str,
    caption: str | None = None,
) -> Any:
    """
    Send a Discord voice message with OGG/Opus audio and waveform metadata.
    Mirrors sendVoiceMessageDiscord in src/discord/voice-message.ts.

    The audio is converted to OGG/Opus if necessary.
    The message is sent with Discord's voice message flags (1 << 13 = 8192).
    """
    import discord

    opus_path = audio_path
    tmp: tempfile.NamedTemporaryFile | None = None

    if not audio_path.endswith(".ogg"):
        tmp = tempfile.NamedTemporaryFile(suffix=".ogg", delete=False)
        tmp.close()
        loop = asyncio.get_running_loop()
        converted = await loop.run_in_executor(None, _convert_to_opus, audio_path, tmp.name)
        if converted:
            opus_path = tmp.name
        else:
            logger.warning("[discord][media] Could not convert to Opus; sending original file")

    try:
        audio_bytes = Path(opus_path).read_bytes()
        waveform = _compute_waveform(audio_bytes)
        waveform_b64 = base64.b64encode(waveform).decode()
        duration_secs = max(1, len(audio_bytes) // 8000)  # rough estimate

        file = discord.File(io.BytesIO(audio_bytes), filename="voice-message.ogg")

        # Discord voice message flag: MESSAGE_FLAG_IS_VOICE_MESSAGE = 1 << 13
        msg = await channel.send(
            content=caption,
            file=file,
            flags=discord.MessageFlags(voice=True),
        )
        return msg
    finally:
        if tmp:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
