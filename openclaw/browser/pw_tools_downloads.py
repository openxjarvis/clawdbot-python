"""Playwright downloads and file uploads.

Port of TypeScript:
  openclaw/src/browser/pw-tools-core.downloads.ts (281 lines)

Provides:
  - download_via_playwright: trigger and wait for a file download
  - wait_for_download_via_playwright: arm a download waiter before a click
  - arm_file_upload_via_playwright: set a file chooser handler before a trigger
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import tempfile
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_DOWNLOAD_TIMEOUT_MS = 30_000
DEFAULT_UPLOAD_TIMEOUT_MS = 10_000
_MAX_FILENAME_LENGTH = 200
_DOWNLOAD_ARM_ID = 0
_UPLOAD_ARM_ID = 0


# ---------------------------------------------------------------------------
# Filename sanitization (mirrors sanitizeDownloadFileName)
# ---------------------------------------------------------------------------

def _sanitize_download_file_name(file_name: str) -> str:
    """Strip path separators and control chars; enforce length limit."""
    trimmed = str(file_name or "").strip()
    if not trimmed:
        return "download.bin"
    # Keep only the basename part (strip any directory components)
    base = os.path.basename(trimmed.replace("\\", "/"))
    # Remove control characters
    base = "".join(c for c in base if ord(c) >= 0x20 and ord(c) != 0x7F)
    base = base.strip()
    if not base or base in (".", ".."):
        return "download.bin"
    if len(base) > _MAX_FILENAME_LENGTH:
        base = base[:_MAX_FILENAME_LENGTH]
    return base


def _resolve_tmp_download_dir() -> Path:
    """Resolve the download staging directory."""
    base = os.environ.get("OPENCLAW_TMP_DIR") or tempfile.gettempdir()
    d = Path(base) / "openclaw" / "downloads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _build_temp_download_path(file_name: str) -> Path:
    run_id = uuid.uuid4().hex
    safe_name = _sanitize_download_file_name(file_name)
    return _resolve_tmp_download_dir() / f"{run_id}-{safe_name}"


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

async def download_via_playwright(
    page: Any,
    *,
    trigger_fn: Any,
    timeout_ms: int = DEFAULT_DOWNLOAD_TIMEOUT_MS,
    dest_path: str | Path | None = None,
) -> dict[str, Any]:
    """
    Trigger a page action that starts a download, wait for the download to
    complete, and save it to a local path.

    Mirrors TS downloadViaPlaywright().

    Args:
        page: Playwright page object
        trigger_fn: Async callable that triggers the download (e.g. page.click("..."))
        timeout_ms: Maximum time to wait for the download
        dest_path: Where to save the file; auto-generated if None

    Returns:
        dict with keys: path, file_name, size_bytes
    """
    timeout_s = timeout_ms / 1000

    async with page.expect_download(timeout=timeout_s * 1000) as download_info:
        await trigger_fn()

    download = await download_info.value
    suggested = download.suggested_filename or "download.bin"

    if dest_path is None:
        dest_path = _build_temp_download_path(suggested)
    else:
        dest_path = Path(dest_path)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

    await download.save_as(str(dest_path))

    size = dest_path.stat().st_size if dest_path.exists() else 0
    logger.info(f"download_via_playwright: saved {suggested!r} → {dest_path} ({size} bytes)")

    return {
        "path": str(dest_path),
        "file_name": suggested,
        "size_bytes": size,
    }


async def wait_for_download_via_playwright(
    page: Any,
    *,
    timeout_ms: int = DEFAULT_DOWNLOAD_TIMEOUT_MS,
    dest_dir: str | Path | None = None,
) -> "DownloadWaiter":
    """
    Create a download waiter that can be used before triggering a download.
    Returns an async context manager.

    Usage:
        waiter = await wait_for_download_via_playwright(page, timeout_ms=30_000)
        await page.click("#download-button")
        result = await waiter.wait()
    """
    return DownloadWaiter(page, timeout_ms=timeout_ms, dest_dir=dest_dir)


class DownloadWaiter:
    """Async download result waiter."""

    def __init__(
        self,
        page: Any,
        *,
        timeout_ms: int = DEFAULT_DOWNLOAD_TIMEOUT_MS,
        dest_dir: str | Path | None = None,
    ) -> None:
        self._page = page
        self._timeout_ms = timeout_ms
        self._dest_dir = Path(dest_dir) if dest_dir else _resolve_tmp_download_dir()
        self._download_event: asyncio.Event = asyncio.Event()
        self._download_obj: Any = None
        self._err: Exception | None = None

        def on_download(download: Any) -> None:
            self._download_obj = download
            self._download_event.set()

        page.once("download", on_download)

    async def wait(self) -> dict[str, Any]:
        """Wait for the download to complete and return file info."""
        try:
            await asyncio.wait_for(
                self._download_event.wait(),
                timeout=self._timeout_ms / 1000,
            )
        except asyncio.TimeoutError:
            raise TimeoutError(f"Download did not start within {self._timeout_ms}ms")

        download = self._download_obj
        suggested = download.suggested_filename or "download.bin"
        dest_path = self._dest_dir / f"{uuid.uuid4().hex}-{_sanitize_download_file_name(suggested)}"

        await download.save_as(str(dest_path))
        size = dest_path.stat().st_size if dest_path.exists() else 0

        return {
            "path": str(dest_path),
            "file_name": suggested,
            "size_bytes": size,
        }


# ---------------------------------------------------------------------------
# File upload
# ---------------------------------------------------------------------------

async def arm_file_upload_via_playwright(
    page: Any,
    *,
    file_paths: list[str | Path],
    timeout_ms: int = DEFAULT_UPLOAD_TIMEOUT_MS,
) -> None:
    """
    Arm a file chooser handler so the next file-chooser dialog is
    automatically filled with the given files.

    Mirrors TS armFileUploadViaPlaywright().

    Args:
        page: Playwright page
        file_paths: Files to upload
        timeout_ms: How long to wait for the file chooser
    """
    if not file_paths:
        raise ValueError("file_paths must not be empty")

    # Validate all paths exist
    validated: list[str] = []
    for fp in file_paths:
        p = Path(fp)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {fp}")
        if not p.is_file():
            raise ValueError(f"Not a file: {fp}")
        validated.append(str(p.resolve()))

    upload_event: asyncio.Event = asyncio.Event()

    async def handle_file_chooser(file_chooser: Any) -> None:
        try:
            await file_chooser.set_files(validated)
        except Exception as exc:
            logger.warning(f"arm_file_upload: set_files failed: {exc}")
        finally:
            upload_event.set()

    page.once("filechooser", handle_file_chooser)

    logger.info(f"arm_file_upload_via_playwright: armed with {len(validated)} file(s)")


# ---------------------------------------------------------------------------
# Validate download path (security check)
# ---------------------------------------------------------------------------

def validate_download_path(path: str | Path, allowed_dirs: list[str | Path] | None = None) -> Path:
    """
    Validate that a download destination path is within allowed directories.

    Raises ValueError if the path escapes the allowed roots.
    """
    p = Path(path).resolve()
    roots = [Path(d).resolve() for d in (allowed_dirs or [])]
    if not roots:
        roots = [_resolve_tmp_download_dir()]
    for root in roots:
        try:
            p.relative_to(root)
            return p
        except ValueError:
            continue
    raise ValueError(f"Download path {p} is outside allowed directories: {roots}")
