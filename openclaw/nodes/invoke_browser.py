"""Browser proxy command handler for node-host.

Mirrors TypeScript: openclaw/src/node-host/invoke-browser.ts

Allows the node-host to forward browser control requests (Playwright/Chrome)
received via the gateway's ``browser.proxy`` RPC method.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import mimetypes
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

BROWSER_PROXY_MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB

# Singleton: ensure the browser control service is started only once.
_browser_control_ready: asyncio.Task | None = None
_browser_control_lock = asyncio.Lock()


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

@dataclass
class BrowserProxyParams:
    """Parameters for a browser proxy request (TS: BrowserProxyParams)."""
    method: str = "GET"
    path: str = ""
    query: dict[str, Any] = field(default_factory=dict)
    body: Any = None
    timeout_ms: int | None = None
    profile: str | None = None


@dataclass
class BrowserProxyFile:
    """A file returned alongside a browser proxy response (TS: BrowserProxyFile)."""
    path: str
    base64: str
    mime_type: str | None = None


@dataclass
class BrowserProxyResult:
    """Result of a browser proxy call (TS: BrowserProxyResult)."""
    result: Any = None
    files: list[BrowserProxyFile] | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_profile_allowlist(raw: list[str] | None) -> list[str]:
    """Normalize and deduplicate the browser profile allowlist.

    Mirrors TS normalizeProfileAllowlist.
    """
    if not isinstance(raw, list):
        return []
    return [entry.strip() for entry in raw if isinstance(entry, str) and entry.strip()]


def resolve_browser_proxy_config() -> dict[str, Any]:
    """Read browser proxy config from openclaw.json.

    Mirrors TS resolveBrowserProxyConfig.
    Returns dict with ``enabled`` (bool) and ``allow_profiles`` (list[str]).
    """
    try:
        from openclaw.config.loader import load_config
        cfg = load_config()
        proxy = (cfg or {}).get("nodeHost", {}).get("browserProxy", {})
    except Exception:
        proxy = {}

    enabled = proxy.get("enabled", True) is not False
    allow_profiles = normalize_profile_allowlist(proxy.get("allowProfiles"))
    return {"enabled": enabled, "allow_profiles": allow_profiles}


async def ensure_browser_control_service() -> None:
    """Start the browser control service if not already running.

    Mirrors TS ensureBrowserControlService (singleton promise pattern).
    Raises RuntimeError if browser is disabled or fails to start.
    """
    global _browser_control_ready

    async with _browser_control_lock:
        if _browser_control_ready is not None:
            try:
                await _browser_control_ready
                return
            except Exception:
                _browser_control_ready = None

        async def _start() -> None:
            try:
                from openclaw.config.loader import load_config
                from openclaw.browser.control_service import (
                    start_browser_control_service_from_config,
                )
                cfg = load_config()
                state = await start_browser_control_service_from_config(cfg)
                if not state:
                    raise RuntimeError("browser control disabled")
            except ImportError as exc:
                raise RuntimeError(f"browser module not available: {exc}") from exc

        _browser_control_ready = asyncio.create_task(_start())

    await _browser_control_ready


def is_profile_allowed(allow_profiles: list[str], profile: str | None) -> bool:
    """Check whether *profile* is in the allowlist.

    Mirrors TS isProfileAllowed.  An empty allowlist means all profiles are allowed.
    """
    if not allow_profiles:
        return True
    if not profile:
        return False
    return profile.strip() in allow_profiles


def collect_browser_proxy_paths(payload: Any) -> list[str]:
    """Extract file paths embedded in a browser proxy response payload.

    Looks for ``path``, ``imagePath``, and ``download.path`` keys.
    Mirrors TS collectBrowserProxyPaths.
    """
    if not isinstance(payload, dict):
        return []
    paths: set[str] = set()
    if isinstance(payload.get("path"), str) and payload["path"].strip():
        paths.add(payload["path"].strip())
    if isinstance(payload.get("imagePath"), str) and payload["imagePath"].strip():
        paths.add(payload["imagePath"].strip())
    download = payload.get("download")
    if isinstance(download, dict):
        dl_path = download.get("path")
        if isinstance(dl_path, str) and dl_path.strip():
            paths.add(dl_path.strip())
    return list(paths)


async def read_browser_proxy_file(file_path: str) -> BrowserProxyFile | None:
    """Read a file and encode it as base64, enforcing a 10 MB size limit.

    Mirrors TS readBrowserProxyFile.
    Returns None if the file does not exist.
    Raises RuntimeError if the file exceeds BROWSER_PROXY_MAX_FILE_BYTES.
    """
    try:
        stat = os.stat(file_path)
    except OSError:
        return None

    if not os.path.isfile(file_path):
        return None

    if stat.st_size > BROWSER_PROXY_MAX_FILE_BYTES:
        limit_mb = BROWSER_PROXY_MAX_FILE_BYTES // (1024 * 1024)
        raise RuntimeError(f"browser proxy file exceeds {limit_mb}MB")

    with open(file_path, "rb") as fh:
        data = fh.read()

    encoded = base64.b64encode(data).decode("ascii")
    mime_type, _ = mimetypes.guess_type(file_path)
    return BrowserProxyFile(path=file_path, base64=encoded, mime_type=mime_type)


def _decode_params(params_json: str | None) -> BrowserProxyParams:
    """Decode JSON-encoded browser proxy params.

    Raises ValueError on missing or invalid JSON.
    """
    if not params_json:
        raise ValueError("INVALID_REQUEST: paramsJSON required")
    raw: dict[str, Any] = json.loads(params_json)
    return BrowserProxyParams(
        method=(raw.get("method") or "GET"),
        path=(raw.get("path") or ""),
        query=raw.get("query") or {},
        body=raw.get("body"),
        timeout_ms=raw.get("timeoutMs"),
        profile=raw.get("profile"),
    )


async def run_browser_proxy_command(params_json: str | None) -> str:
    """Handle a ``browser.proxy`` invoke request from the gateway.

    Mirrors TS runBrowserProxyCommand.

    Args:
        params_json: JSON-encoded BrowserProxyParams string.

    Returns:
        JSON-encoded BrowserProxyResult string.

    Raises:
        ValueError / RuntimeError on invalid input or disabled browser.
    """
    params = _decode_params(params_json)

    path_value = params.path.strip()
    if not path_value:
        raise ValueError("INVALID_REQUEST: path required")

    proxy_config = resolve_browser_proxy_config()
    if not proxy_config["enabled"]:
        raise RuntimeError("UNAVAILABLE: node browser proxy disabled")

    await ensure_browser_control_service()

    # Profile allowlist check
    allow_profiles: list[str] = proxy_config["allow_profiles"]
    requested_profile = (params.profile or "").strip()
    if allow_profiles:
        if path_value != "/profiles":
            profile_to_check = requested_profile or None
            if not is_profile_allowed(allow_profiles, profile_to_check):
                raise ValueError("INVALID_REQUEST: browser profile not allowed")
        elif requested_profile:
            if not is_profile_allowed(allow_profiles, requested_profile):
                raise ValueError("INVALID_REQUEST: browser profile not allowed")

    method = params.method.upper()
    normalized_path = path_value if path_value.startswith("/") else f"/{path_value}"

    # Build query dict
    query: dict[str, str] = {}
    if requested_profile:
        query["profile"] = requested_profile
    for k, v in (params.query or {}).items():
        if v is None:
            continue
        query[k] = str(v)

    # Dispatch via BrowserRouteDispatcher
    try:
        from openclaw.browser.dispatcher import BrowserRouteDispatcher
        dispatcher = BrowserRouteDispatcher()
    except ImportError as exc:
        raise RuntimeError(f"browser dispatcher not available: {exc}") from exc

    timeout_s: float | None = (
        params.timeout_ms / 1000.0 if params.timeout_ms is not None else 30.0
    )
    try:
        response = await asyncio.wait_for(
            dispatcher.dispatch(
                method=method,
                path=normalized_path,
                query=query,
                body=params.body,
            ),
            timeout=timeout_s,
        )
    except asyncio.TimeoutError:
        raise RuntimeError("browser proxy request timed out")

    # Handle error responses
    if isinstance(response, dict):
        status = response.get("status", 200)
        result = response.get("body", response)
    else:
        status = 200
        result = response

    if isinstance(status, int) and status >= 400:
        error_msg: str
        if isinstance(result, dict) and "error" in result:
            error_msg = str(result["error"])
        else:
            error_msg = f"HTTP {status}"
        raise RuntimeError(error_msg)

    # Filter profiles list by allowlist if applicable
    if allow_profiles and normalized_path == "/profiles" and isinstance(result, dict):
        profiles = result.get("profiles", [])
        if isinstance(profiles, list):
            result = dict(result)
            result["profiles"] = [
                entry for entry in profiles
                if isinstance(entry, dict)
                and isinstance(entry.get("name"), str)
                and entry["name"] in allow_profiles
            ]

    # Collect and encode referenced files
    files: list[BrowserProxyFile] | None = None
    paths = collect_browser_proxy_paths(result)
    if paths:
        loaded_files: list[BrowserProxyFile] = []
        for file_path in paths:
            try:
                file_obj = await read_browser_proxy_file(file_path)
                if file_obj is None:
                    raise RuntimeError("file not found")
                loaded_files.append(file_obj)
            except Exception as exc:
                raise RuntimeError(
                    f"browser proxy file read failed for {file_path}: {exc}"
                ) from exc
        if loaded_files:
            files = loaded_files

    output: dict[str, Any] = {"result": result}
    if files:
        output["files"] = [
            {
                "path": f.path,
                "base64": f.base64,
                **({"mimeType": f.mime_type} if f.mime_type else {}),
            }
            for f in files
        ]

    return json.dumps(output)
