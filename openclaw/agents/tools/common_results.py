"""Image and file result helpers for agent tools.

Ported from TypeScript openclaw/src/agents/tools/common.ts:
- imageResult()
- imageResultFromFile()

These helpers create AgentToolResult objects with proper MEDIA: prefix
for channel delivery (Telegram sendPhoto, etc.) and embed base64 image
data in the content block so the LLM can see the image.
"""
from __future__ import annotations

import base64
import logging
import mimetypes
from pathlib import Path
from typing import Any

from ..types import AgentToolResult, ImageContent, TextContent

logger = logging.getLogger(__name__)


def _detect_mime(buf: bytes) -> str:
    """Detect MIME type from file magic bytes. Mirrors TS detectMime()."""
    if buf[:4] == b"\x89PNG":
        return "image/png"
    if buf[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if buf[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if buf[:4] == b"RIFF" and buf[8:12] == b"WEBP":
        return "image/webp"
    if buf[:4] == b"%PDF":
        return "application/pdf"
    return "application/octet-stream"


async def image_result(
    label: str,
    path: str,
    base64_data: str,
    mime_type: str,
    extra_text: str | None = None,
    details: dict[str, Any] | None = None,
) -> AgentToolResult:
    """Create a tool result with image data.

    Mirrors TypeScript imageResult() from common.ts lines 211-236.

    The result contains:
    - A text content block with MEDIA:<path> (parsed by channel manager
      for delivery to Telegram/Discord/etc.)
    - An image content block with base64 data so the LLM can see the image

    Args:
        label: Diagnostic label (e.g. "canvas:snapshot", "browser:screenshot")
        path: Absolute path where image was saved on disk
        base64_data: Base64-encoded image bytes
        mime_type: MIME type (e.g. "image/png", "image/jpeg")
        extra_text: Optional extra text to include before MEDIA token
        details: Optional metadata dict for AgentToolResult.details
    """
    text = extra_text if extra_text else f"MEDIA:{path}"
    content = [
        TextContent(text=text),
        ImageContent(data=base64_data, mimeType=mime_type),
    ]
    result_details: dict[str, Any] = {"path": path, **(details or {})}
    return AgentToolResult(content=content, details=result_details)


async def image_result_from_file(
    label: str,
    path: str,
    extra_text: str | None = None,
    details: dict[str, Any] | None = None,
) -> AgentToolResult:
    """Create a tool result by reading an image file from disk.

    Mirrors TypeScript imageResultFromFile() from common.ts lines 238-256.
    Reads the file, detects MIME type from magic bytes, then calls image_result().

    Args:
        label: Diagnostic label (e.g. "browser:screenshot")
        path: Absolute path to the image file
        extra_text: Optional extra text content
        details: Optional metadata dict
    """
    file_path = Path(path)
    buf = file_path.read_bytes()
    mime_type = _detect_mime(buf[:256])
    b64 = base64.b64encode(buf).decode("ascii")
    return await image_result(
        label=label,
        path=path,
        base64_data=b64,
        mime_type=mime_type,
        extra_text=extra_text,
        details=details,
    )


def json_result(payload: Any) -> AgentToolResult:
    """Create a tool result with JSON text content.

    Mirrors TypeScript jsonResult() from common.ts.
    """
    import json
    text = json.dumps(payload, indent=2)
    return AgentToolResult(
        content=[TextContent(text=text)],
        details=payload,
    )


__all__ = [
    "image_result",
    "image_result_from_file",
    "json_result",
]
