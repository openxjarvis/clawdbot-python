"""WhatsApp media handling.

Outbound: load media from URL/local path, HEIC→JPEG conversion, image size optimization.
Inbound:  the raw media buffer is downloaded by the Baileys bridge and base64-encoded in the event.

Mirrors TypeScript: src/web/media.ts and src/web/inbound/media.ts
"""
from __future__ import annotations

import io
import logging
import mimetypes
import os
import re
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Outbound image optimization ladder (mirrors TS)
_IMAGE_MAX_SIDES = [2048, 1536, 1280, 1024, 800]
_IMAGE_QUALITIES = [80, 70, 60, 50, 40]

# Allowed local path roots for sandboxing
_DEFAULT_LOCAL_ROOTS = [
    str(Path.home()),
    "/tmp",
    "/var/folders",
]


@dataclass
class LoadedMedia:
    buffer: bytes
    content_type: str
    file_name: str
    kind: str  # "image" | "video" | "audio" | "document"


def load_outbound_media(
    url_or_path: str,
    media_max_mb: int = 50,
    local_roots: list[str] | None = None,
) -> LoadedMedia:
    """
    Load media for outbound sending from a URL or local path.

    Supports:
    - http:// / https://
    - file:// URLs
    - Local absolute/tilde-expanded paths
    - MEDIA: prefix (agent tool tagging)

    Performs:
    - HEIC → JPEG conversion (requires pillow)
    - Image size optimization pipeline to stay within mediaMaxMb
    - PNG alpha preservation
    - Audio/ogg mime-type fix for WhatsApp PTT
    """
    target = url_or_path.strip()

    # Strip MEDIA: prefix if present
    if target.upper().startswith("MEDIA:"):
        target = target[6:].strip()

    if target.startswith("file://"):
        target = target[7:]

    max_bytes = media_max_mb * 1024 * 1024

    # Remote URL
    if target.startswith("http://") or target.startswith("https://"):
        buf, content_type, file_name = _fetch_url(target)
    else:
        # Local path
        expanded = os.path.expanduser(target)
        resolved = str(Path(expanded).resolve())
        _assert_local_path_allowed(resolved, local_roots or _DEFAULT_LOCAL_ROOTS)
        buf, content_type, file_name = _read_local(resolved)

    # HEIC → JPEG conversion
    buf, content_type = _maybe_convert_heic(buf, content_type)

    kind = _classify_kind(content_type)

    # Image size optimization
    if kind == "image" and len(buf) > max_bytes:
        buf, content_type = _optimize_image(buf, content_type, max_bytes)

    # Audio PTT MIME fix: audio/ogg → audio/ogg; codecs=opus
    if content_type == "audio/ogg":
        content_type = "audio/ogg; codecs=opus"

    return LoadedMedia(
        buffer=buf,
        content_type=content_type,
        file_name=file_name,
        kind=kind,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fetch_url(url: str) -> tuple[bytes, str, str]:
    """Download from HTTP/HTTPS."""
    req = urllib.request.Request(url, headers={"User-Agent": "openclaw/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        buf = resp.read()
        content_type = resp.headers.get("Content-Type", "application/octet-stream")
        content_type = content_type.split(";")[0].strip()
    file_name = _extract_filename_from_url(url)
    return buf, content_type, file_name


def _read_local(path: str) -> tuple[bytes, str, str]:
    """Read a local file."""
    p = Path(path)
    buf = p.read_bytes()
    content_type, _ = mimetypes.guess_type(path)
    if not content_type:
        content_type = "application/octet-stream"
    return buf, content_type, p.name


def _assert_local_path_allowed(resolved: str, roots: list[str]) -> None:
    """Raise if local path is outside allowed roots."""
    for root in roots:
        try:
            resolved_root = str(Path(os.path.expanduser(root)).resolve())
            if resolved.startswith(resolved_root):
                return
        except Exception:
            continue
    raise PermissionError(
        f"Local media path '{resolved}' is outside allowed roots: {roots}"
    )


def _extract_filename_from_url(url: str) -> str:
    """Best-effort filename from URL path."""
    try:
        path = url.split("?")[0].rstrip("/")
        return path.split("/")[-1] or "file"
    except Exception:
        return "file"


def _classify_kind(content_type: str) -> str:
    ct = content_type.split(";")[0].strip()
    if ct.startswith("image/"):
        return "image"
    if ct.startswith("video/"):
        return "video"
    if ct.startswith("audio/"):
        return "audio"
    return "document"


def _maybe_convert_heic(buf: bytes, content_type: str) -> tuple[bytes, str]:
    """Convert HEIC/HEIF images to JPEG using pillow."""
    ct = content_type.lower()
    if "heic" not in ct and "heif" not in ct:
        # Also check magic bytes: ftyp box with heic/heis/mif1 brand
        if len(buf) < 12 or not _is_heic_bytes(buf):
            return buf, content_type
    try:
        from PIL import Image  # type: ignore
        img = Image.open(io.BytesIO(buf))
        if img.mode not in ("RGB", "RGBA", "L"):
            img = img.convert("RGB")
        out = io.BytesIO()
        img.convert("RGB").save(out, format="JPEG", quality=85)
        return out.getvalue(), "image/jpeg"
    except ImportError:
        logger.warning("[whatsapp] pillow not installed; cannot convert HEIC to JPEG")
        return buf, content_type
    except Exception as e:
        logger.warning("[whatsapp] HEIC conversion failed: %s", e)
        return buf, content_type


def _is_heic_bytes(buf: bytes) -> bool:
    """Check HEIC magic bytes (ISO base media file format with heic brand)."""
    try:
        # Bytes 4-8 should be "ftyp"
        if buf[4:8] != b"ftyp":
            return False
        brand = buf[8:12]
        return brand in (b"heic", b"heis", b"heix", b"mif1", b"msf1")
    except Exception:
        return False


def _optimize_image(buf: bytes, content_type: str, max_bytes: int) -> tuple[bytes, str]:
    """
    Reduce image size by trying progressively smaller sizes and lower JPEG quality.
    Preserves PNG alpha channel; converts to JPEG if still over limit.
    Mirrors TS loadWebMedia optimization pipeline.
    """
    try:
        from PIL import Image  # type: ignore

        img = Image.open(io.BytesIO(buf))
        has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)

        # Try PNG for alpha images
        if has_alpha and content_type == "image/png":
            for max_side in _IMAGE_MAX_SIDES:
                resized = _resize_image(img, max_side)
                out = io.BytesIO()
                resized.save(out, format="PNG", optimize=True)
                candidate = out.getvalue()
                if len(candidate) <= max_bytes:
                    return candidate, "image/png"

        # Try JPEG
        rgb = img.convert("RGB")
        for max_side in _IMAGE_MAX_SIDES:
            for quality in _IMAGE_QUALITIES:
                resized = _resize_image(rgb, max_side)
                out = io.BytesIO()
                resized.save(out, format="JPEG", quality=quality)
                candidate = out.getvalue()
                if len(candidate) <= max_bytes:
                    return candidate, "image/jpeg"

        # Return smallest JPEG produced as fallback
        resized = _resize_image(rgb, _IMAGE_MAX_SIDES[-1])
        out = io.BytesIO()
        resized.save(out, format="JPEG", quality=_IMAGE_QUALITIES[-1])
        return out.getvalue(), "image/jpeg"

    except ImportError:
        logger.warning("[whatsapp] pillow not installed; cannot optimize image")
        return buf, content_type
    except Exception as e:
        logger.warning("[whatsapp] Image optimization failed: %s", e)
        return buf, content_type


def _resize_image(img: object, max_side: int) -> object:
    """Resize image so that the longest side is at most max_side."""
    from PIL import Image  # type: ignore

    pil_img: Image.Image = img  # type: ignore
    w, h = pil_img.size
    if max(w, h) <= max_side:
        return pil_img
    if w >= h:
        new_w = max_side
        new_h = int(h * max_side / w)
    else:
        new_h = max_side
        new_w = int(w * max_side / h)
    return pil_img.resize((new_w, new_h), Image.LANCZOS)
