"""Media loading from URLs and files.

Matches TypeScript src/media/store.ts and src/web/media.ts
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import mimetypes
from urllib.parse import urlparse, unquote
import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class LoadedMedia:
    """Loaded media data."""

    buffer: bytes
    content_type: Optional[str] = None
    file_name: Optional[str] = None


# Alias for backward compatibility
MediaResult = LoadedMedia


async def load_web_media(url_or_path: str, max_bytes: Optional[int] = None) -> LoadedMedia:
    """Load media from URL or local file path.

    Args:
        url_or_path: URL or file path
        max_bytes: Maximum bytes to load (optional)

    Returns:
        Loaded media with buffer and metadata

    Raises:
        ValueError: If max_bytes exceeded or file not found
        IOError: If download fails
    """
    max_size = max_bytes or 10 * 1024 * 1024

    # TS-compatible convenience prefix.
    if url_or_path.startswith("MEDIA:"):
        url_or_path = url_or_path[len("MEDIA:") :]
    if url_or_path.startswith("~/"):
        url_or_path = str(Path.home() / url_or_path[2:])

    parsed = urlparse(url_or_path)
    scheme = parsed.scheme.lower()

    # Check if it's a local file path
    if scheme in ("", "file") or url_or_path.startswith("/"):
        path_str = unquote(url_or_path.replace("file://", ""))
        path = Path(path_str)

        if not path.exists():
            raise ValueError(f"File not found: {path}")

        file_size = path.stat().st_size
        if file_size > max_size:
            raise ValueError(
                f"File size {file_size} exceeds max_bytes {max_size}"
            )

        buffer = path.read_bytes()
        content_type, _ = mimetypes.guess_type(str(path))
        file_name = path.name

        return LoadedMedia(buffer=buffer, content_type=content_type, file_name=file_name)

    if scheme not in ("http", "https"):
        raise ValueError(f"Unsupported media scheme: {scheme}")

    # Download from URL
    try:
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url_or_path, allow_redirects=True, max_redirects=5) as response:
                response.raise_for_status()

                # Check content length if provided
                content_length = response.headers.get("Content-Length")
                if content_length:
                    if int(content_length) > max_size:
                        raise ValueError(
                            f"Content length {content_length} exceeds max_bytes {max_size}"
                        )

                # Read response in chunks to enforce bounds during transfer.
                chunks: list[bytes] = []
                current = 0
                async for chunk in response.content.iter_chunked(64 * 1024):
                    current += len(chunk)
                    if current > max_size:
                        raise ValueError(
                            f"Downloaded {current} bytes, exceeds max_bytes {max_size}"
                        )
                    chunks.append(chunk)
                buffer = b"".join(chunks)

                # Check actual size
                if len(buffer) > max_size:
                    raise ValueError(
                        f"Downloaded {len(buffer)} bytes, exceeds max_bytes {max_size}"
                    )

                content_type = response.headers.get("Content-Type")

                # Extract filename from URL
                file_name = Path(unquote(parsed.path)).name
                if not file_name or "." not in file_name:
                    file_name = None

                return LoadedMedia(buffer=buffer, content_type=content_type, file_name=file_name)

    except aiohttp.ClientError as e:
        raise IOError(f"Failed to download media from {url_or_path}: {e}")


# Backward compatibility alias
load_media = load_web_media


class MediaLoader:
    """Media loader class for backward compatibility."""
    
    @staticmethod
    async def load(url_or_path: str, max_bytes: Optional[int] = None) -> LoadedMedia:
        """Load media from URL or file path."""
        return await load_web_media(url_or_path, max_bytes)


__all__ = ["LoadedMedia", "load_web_media", "load_media", "MediaLoader"]
