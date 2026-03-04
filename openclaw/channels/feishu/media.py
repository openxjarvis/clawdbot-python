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
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .config import ResolvedFeishuAccount

logger = logging.getLogger(__name__)

_MAX_DEFAULT_MB = 30.0
_AUDIO_EXTENSIONS = {".opus", ".ogg", ".mp3", ".m4a", ".aac", ".wav"}


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
        file_type = "opus" if ext in {".opus", ".ogg"} else "mp4"
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
        builder = (
            CreateFileRequestBody.builder()
            .file_type(file_type)
            .file_name(filename)
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
    from lark_oapi.api.im.v1 import (
        CreateMessageRequest, CreateMessageRequestBody,
        ReplyMessageRequest, ReplyMessageRequestBody,
    )
    import json

    ext = Path(filename).suffix.lower()
    is_audio = media_type == "audio" or ext in _AUDIO_EXTENSIONS
    is_video = media_type == "video" or ext in {".mp4", ".mov", ".avi", ".mkv", ".webm"}

    if media_type == "image":
        key = await upload_image(client, data)
        if not key:
            return None
        content_dict = {"image_key": key}
        msg_type = "image"
    elif is_audio:
        key = await upload_file(client, data, filename)
        if not key:
            return None
        content_dict = {"file_key": key}
        msg_type = "audio"
    elif is_video:
        # Use msg_type="media" for inline video playback in Feishu
        key = await upload_file(client, data, filename)
        if not key:
            return None
        content_dict = {"file_key": key}
        msg_type = "media"
    else:
        key = await upload_file(client, data, filename)
        if not key:
            return None
        content_dict = {"file_key": key}
        msg_type = "file"

    content_str = json.dumps(content_dict)

    loop = asyncio.get_running_loop()

    try:
        if reply_to_message_id:
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
                "[feishu] Failed to send media: code=%s msg=%s", response.code, response.msg
            )
            return None

        return response.data.message_id if response.data else None

    except Exception as e:
        logger.warning("[feishu] Exception sending media: %s", e)
        return None


# ---------------------------------------------------------------------------
# Helper: determine msg_type from file extension
# ---------------------------------------------------------------------------

def get_msg_type_for_file(filename: str) -> str:
    """Return the Feishu msg_type appropriate for a given filename."""
    ext = Path(filename).suffix.lower()
    if ext in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}:
        return "image"
    if ext in _AUDIO_EXTENSIONS:
        return "audio"
    if ext in {".mp4", ".mov", ".avi", ".mkv", ".webm"}:
        return "file"
    return "file"
