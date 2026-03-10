"""Media upload and download for Feishu channel.

Mirrors TypeScript: extensions/feishu/src/media.ts

Inbound:  download image/file/audio/video via client.im.v1.message_resource.get
Outbound: upload image via client.im.v1.image.create → image_key
          upload file  via client.im.v1.file.create  → file_key
          then send with appropriate msg_type
"""
from __future__ import annotations

import asyncio
import io
import logging
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .config import ResolvedFeishuAccount

logger = logging.getLogger(__name__)

_MAX_DEFAULT_MB = 30.0
_AUDIO_EXTENSIONS = {".opus", ".ogg", ".mp3", ".m4a", ".aac", ".wav"}

# ---------------------------------------------------------------------------
# Filename sanitization for upload
# ---------------------------------------------------------------------------
_ASCII_ONLY_RE = re.compile(r'^[\x20-\x7E]+$')


def sanitize_file_name_for_upload(filename: str) -> str:
    """RFC-5987 encode non-ASCII filenames for Feishu multipart upload.

    Feishu's Content-Disposition header requires ASCII-safe filenames.
    Non-ASCII characters (Chinese, Japanese, emoji, etc.) silently cause the
    upload to fail or produce a garbled filename on the server side.

    Applies RFC-5987 percent-encoding via urllib.parse.quote, matching the
    special-char escaping from the HTTP spec.

    Mirrors TS sanitizeFileNameForUpload() in extensions/feishu/src/media.ts.
    """
    if _ASCII_ONLY_RE.match(filename):
        return filename
    from urllib.parse import quote
    return (
        quote(filename, safe="")
        .replace("'", "%27")
        .replace("(", "%28")
        .replace(")", "%29")
    )


# ---------------------------------------------------------------------------
# Inbound: download message resource
# ---------------------------------------------------------------------------

async def download_message_resource(
    client: Any,
    message_id: str,
    file_key: str,
    resource_type: str,         # "image" | "file"
    *,
    max_mb: float = _MAX_DEFAULT_MB,
) -> bytes | None:
    """
    Download an attachment from a Feishu message.

    Uses client.im.v1.message_resource.get (sync SDK in asyncio executor).
    Returns raw bytes or None on error.

    Mirrors TS downloadMessageResourceFeishu().
    """
    import lark_oapi as lark
    from lark_oapi.api.im.v1 import GetMessageResourceRequest

    try:
        request = (
            GetMessageResourceRequest.builder()
            .message_id(message_id)
            .file_key(file_key)
            .type(resource_type)
            .build()
        )

        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.im.v1.message_resource.get(request),
        )

        if not response.success():
            logger.warning(
                "[feishu] Failed to download resource %s from message %s: code=%s msg=%s",
                file_key, message_id, response.code, response.msg,
            )
            return None

        # GetMessageResourceResponse uses .file (IO[Any]) not .data
        raw = getattr(response, "file", None) or getattr(response, "data", None)
        if raw is None:
            logger.warning("[feishu] Empty response body for resource %s", file_key)
            return None

        if hasattr(raw, "read"):
            content = raw.read()
        elif isinstance(raw, (bytes, bytearray)):
            content = bytes(raw)
        else:
            try:
                content = bytes(raw)
            except Exception:
                logger.warning("[feishu] Cannot decode resource %s body: %r", file_key, type(raw))
                return None

        if not content:
            return None

        max_bytes = int(max_mb * 1024 * 1024)
        if len(content) > max_bytes:
            logger.warning(
                "[feishu] Resource %s too large (%d bytes > %d limit), skipping",
                file_key, len(content), max_bytes,
            )
            return None

        return content

    except Exception as e:
        logger.warning("[feishu] Exception downloading resource %s: %s", file_key, e)
        return None


# ---------------------------------------------------------------------------
# Outbound: upload image
# ---------------------------------------------------------------------------

async def upload_image(
    client: Any,
    data: bytes,
    *,
    image_type: str = "message",
) -> str | None:
    """
    Upload an image buffer to Feishu and return the image_key.

    Mirrors TS uploadImageFeishu().
    """
    import lark_oapi as lark
    from lark_oapi.api.im.v1 import CreateImageRequest, CreateImageRequestBody

    try:
        file_obj = io.BytesIO(data)
        request = (
            CreateImageRequest.builder()
            .request_body(
                CreateImageRequestBody.builder()
                .image_type(image_type)
                .image(file_obj)
                .build()
            )
            .build()
        )

        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.im.v1.image.create(request),
        )

        if not response.success():
            logger.warning(
                "[feishu] Failed to upload image: code=%s msg=%s", response.code, response.msg
            )
            return None

        return response.data.image_key if response.data else None

    except Exception as e:
        logger.warning("[feishu] Exception uploading image: %s", e)
        return None


# ---------------------------------------------------------------------------
# Outbound: upload file
# ---------------------------------------------------------------------------

async def upload_file(
    client: Any,
    data: bytes,
    filename: str,
    *,
    duration: int = 0,
) -> str | None:
    """
    Upload a file/audio/video buffer to Feishu and return the file_key.

    For audio files, duration (ms) should be set.
    Mirrors TS uploadFileFeishu().
    """
    from lark_oapi.api.im.v1 import CreateFileRequest, CreateFileRequestBody

    ext = Path(filename).suffix.lower()
    if ext in _AUDIO_EXTENSIONS:
        # All audio files use file_type="opus" for Feishu upload
        # This includes MP3, WAV, M4A, OGG, and OPUS formats
        file_type = "opus"
    elif ext in {".mp4", ".mov", ".avi", ".mkv"}:
        file_type = "mp4"
    elif ext == ".pdf":
        file_type = "pdf"
    elif ext in {".doc", ".docx"}:
        file_type = "doc"
    elif ext in {".xls", ".xlsx"}:
        file_type = "xls"
    elif ext in {".ppt", ".pptx"}:
        file_type = "ppt"
    else:
        file_type = "stream"

    try:
        file_obj = io.BytesIO(data)
        # Sanitize filename: RFC-5987 encode non-ASCII chars that would silently
        # fail Feishu's multipart upload Content-Disposition header.
        safe_filename = sanitize_file_name_for_upload(filename)
        builder = (
            CreateFileRequestBody.builder()
            .file_type(file_type)
            .file_name(safe_filename)
            .file(file_obj)
        )
        if duration and file_type in {"opus", "mp4"}:
            builder = builder.duration(duration)

        request = (
            CreateFileRequest.builder()
            .request_body(builder.build())
            .build()
        )

        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.im.v1.file.create(request),
        )

        if not response.success():
            logger.warning(
                "[feishu] Failed to upload file %s: code=%s msg=%s",
                filename, response.code, response.msg,
            )
            return None

        return response.data.file_key if response.data else None

    except Exception as e:
        logger.warning("[feishu] Exception uploading file %s: %s", filename, e)
        return None


# ---------------------------------------------------------------------------
# Outbound: send media (orchestrates upload + send message)
# ---------------------------------------------------------------------------

async def send_media_feishu(
    client: Any,
    *,
    receive_id: str,
    receive_id_type: str,
    data: bytes,
    filename: str,
    media_type: str,      # "image" | "audio" | "video" | "file"
    reply_to_message_id: str | None = None,
    reply_in_thread: bool = False,
) -> str | None:
    """
    Upload media and send via appropriate msg_type.

    Returns sent message_id or None.
    Mirrors TS sendMediaFeishu().
    """
    logger.info(f"[feishu media] send_media_feishu: filename={filename}, media_type={media_type}, data_size={len(data)} bytes")
    
    from lark_oapi.api.im.v1 import (
        CreateMessageRequest, CreateMessageRequestBody,
        ReplyMessageRequest, ReplyMessageRequestBody,
    )
    import json

    ext = Path(filename).suffix.lower()
    is_audio = media_type == "audio" or ext in _AUDIO_EXTENSIONS
    is_video = media_type == "video" or ext in {".mp4", ".mov", ".avi", ".mkv", ".webm"}

    logger.info(f"[feishu media] Determined: is_audio={is_audio}, is_video={is_video}, ext={ext}")

    # Duration is required for audio and video files by Feishu API
    # Default to 10 seconds if not provided (should ideally extract from file metadata)
    duration_ms = 0
    if is_video or is_audio:
        duration_ms = 10000  # 10 seconds default

    if media_type == "image":
        logger.info(f"[feishu media] Uploading as image")
        key = await upload_image(client, data)
        if not key:
            logger.error(f"[feishu media] Failed to upload image")
            return None
        content_dict = {"image_key": key}
        msg_type = "image"
    elif is_audio:
        # All audio files (MP3, M4A, WAV, OPUS, OGG, etc.) use msg_type="audio"
        # This is required by Feishu API to display audio player
        # Only opus files use duration parameter
        logger.info(f"[feishu media] Uploading as audio (msg_type=audio), duration={duration_ms}ms")
        key = await upload_file(client, data, filename, duration=duration_ms)
        if not key:
            logger.error(f"[feishu media] Failed to upload audio")
            return None
        content_dict = {"file_key": key}
        msg_type = "audio"
    else:
        # Everything else (video, PPT, PDF, DOC, etc.) uses msg_type="file"
        # CRITICAL FIX: Videos use msg_type="file" (not "media")
        # This aligns with TS version and Feishu API documentation
        # See: openclaw/extensions/feishu/src/media.ts:470-472
        if is_video:
            logger.info(f"[feishu media] Uploading as video (msg_type=file), duration={duration_ms}ms")
            key = await upload_file(client, data, filename, duration=duration_ms)
        else:
            logger.info(f"[feishu media] Uploading as file (document/other)")
            key = await upload_file(client, data, filename, duration=0)
        
        if not key:
            logger.error(f"[feishu media] Failed to upload {'video' if is_video else 'file'}")
            return None
        content_dict = {"file_key": key}
        msg_type = "file"

    logger.info(f"[feishu media] Upload complete: key={key}, msg_type={msg_type}")
    content_str = json.dumps(content_dict)

    loop = asyncio.get_running_loop()

    try:
        if reply_to_message_id:
            logger.info(f"[feishu media] Sending as reply to message_id={reply_to_message_id}")
            request = (
                ReplyMessageRequest.builder()
                .message_id(reply_to_message_id)
                .request_body(
                    ReplyMessageRequestBody.builder()
                    .content(content_str)
                    .msg_type(msg_type)
                    .reply_in_thread(reply_in_thread)
                    .build()
                )
                .build()
            )
            response = await loop.run_in_executor(
                None,
                lambda: client.im.v1.message.reply(request),
            )
        else:
            logger.info(f"[feishu media] Sending as new message to {receive_id} (type={receive_id_type})")
            request = (
                CreateMessageRequest.builder()
                .receive_id_type(receive_id_type)
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(receive_id)
                    .content(content_str)
                    .msg_type(msg_type)
                    .build()
                )
                .build()
            )
            response = await loop.run_in_executor(
                None,
                lambda: client.im.v1.message.create(request),
            )

        if not response.success():
            logger.warning(
                "[feishu media] Failed to send media: code=%s msg=%s", response.code, response.msg
            )
            return None

        msg_id = response.data.message_id if response.data else None
        logger.info(f"[feishu media] Message sent successfully: message_id={msg_id}")
        return msg_id

    except Exception as e:
        logger.warning("[feishu media] Exception sending media: %s", e, exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Helper: determine msg_type from file extension
# ---------------------------------------------------------------------------

def get_msg_type_for_file(filename: str) -> str:
    """Return the Feishu msg_type appropriate for a given filename.
    
    Mirrors TS media.ts logic:
    - Images use "image"
    - Opus/OGG audio uses "audio"  
    - Everything else (including video, PPT, PDF) uses "file"
    """
    ext = Path(filename).suffix.lower()
    if ext in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}:
        return "image"
    if ext in {".opus", ".ogg"}:
        return "audio"
    # Video, documents, and everything else use "file"
    return "file"
