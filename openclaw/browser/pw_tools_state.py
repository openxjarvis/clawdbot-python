"""Playwright page state tracking — console messages, errors, network requests.

Port of TypeScript:
  openclaw/src/browser/pw-tools-core.state.ts (209 lines)

Provides per-page state tracking for:
  - Console messages (log/warn/error)
  - Uncaught page errors (JS exceptions)
  - Network request activity (URL, method, status)
  - Offline / extra HTTP headers / geolocation / viewport overrides

Used by the agent for debugging and observability.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class ConsoleMessage:
    type: str          # "log" | "warn" | "error" | "info" | "debug"
    text: str
    location: str | None = None


@dataclass
class PageError:
    message: str
    stack: str | None = None


@dataclass
class NetworkRequest:
    url: str
    method: str
    status: int | None = None
    resource_type: str | None = None
    failed: bool = False


@dataclass
class PageActivity:
    console_messages: list[ConsoleMessage] = field(default_factory=list)
    page_errors: list[PageError] = field(default_factory=list)
    network_requests: list[NetworkRequest] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Per-page state registry
# ---------------------------------------------------------------------------

_MAX_CONSOLE_MESSAGES = 100
_MAX_PAGE_ERRORS = 50
_MAX_NETWORK_REQUESTS = 200

# Maps page object id → PageActivity
_page_state: dict[int, PageActivity] = {}


def ensure_page_state(page: Any) -> PageActivity:
    """
    Attach console/error/network listeners to a Playwright page and
    return (or create) its PageActivity tracker.

    Mirrors TS ensurePageState(page).
    """
    page_id = id(page)
    if page_id in _page_state:
        return _page_state[page_id]

    activity = PageActivity()
    _page_state[page_id] = activity

    # Console messages
    def on_console(msg: Any) -> None:
        if len(activity.console_messages) >= _MAX_CONSOLE_MESSAGES:
            activity.console_messages.pop(0)
        loc = None
        try:
            loc_obj = msg.location
            if loc_obj:
                loc = f"{loc_obj.get('url','')}:{loc_obj.get('lineNumber','')}:{loc_obj.get('columnNumber','')}"
        except Exception:
            pass
        activity.console_messages.append(ConsoleMessage(
            type=getattr(msg, "type", "log") or "log",
            text=str(msg.text) if hasattr(msg, "text") else str(msg),
            location=loc,
        ))

    # Page errors
    def on_page_error(error: Any) -> None:
        if len(activity.page_errors) >= _MAX_PAGE_ERRORS:
            activity.page_errors.pop(0)
        msg = str(error)
        stack = getattr(error, "stack", None)
        activity.page_errors.append(PageError(message=msg, stack=stack))

    # Network requests (request + response)
    def on_request(request: Any) -> None:
        if len(activity.network_requests) >= _MAX_NETWORK_REQUESTS:
            activity.network_requests.pop(0)
        activity.network_requests.append(NetworkRequest(
            url=str(request.url),
            method=str(request.method),
            resource_type=getattr(request, "resource_type", None),
        ))

    def on_response(response: Any) -> None:
        url = str(response.url)
        status = response.status
        for req in reversed(activity.network_requests):
            if req.url == url and req.status is None:
                req.status = status
                break

    def on_request_failed(request: Any) -> None:
        url = str(request.url)
        for req in reversed(activity.network_requests):
            if req.url == url and not req.failed:
                req.failed = True
                break

    try:
        page.on("console", on_console)
        page.on("pageerror", on_page_error)
        page.on("request", on_request)
        page.on("response", on_response)
        page.on("requestfailed", on_request_failed)
        # Remove state when page closes
        def on_close(_: Any) -> None:
            _page_state.pop(page_id, None)
        page.on("close", on_close)
    except Exception as exc:
        logger.debug(f"ensure_page_state: could not attach listeners: {exc}")

    return activity


def get_page_activity(page: Any) -> PageActivity:
    """Return the PageActivity for a page, or empty if not tracked."""
    return _page_state.get(id(page), PageActivity())


def clear_page_activity(page: Any) -> None:
    """Clear all tracked activity for a page."""
    activity = _page_state.get(id(page))
    if activity:
        activity.console_messages.clear()
        activity.page_errors.clear()
        activity.network_requests.clear()


# ---------------------------------------------------------------------------
# High-level state manipulation (mirrors TS pw-tools-core.state.ts)
# ---------------------------------------------------------------------------

async def set_offline_via_playwright(
    page: Any,
    offline: bool,
) -> None:
    """Set the page context to offline/online mode."""
    ensure_page_state(page)
    await page.context().set_offline(bool(offline))


async def set_extra_http_headers_via_playwright(
    page: Any,
    headers: dict[str, str],
) -> None:
    """Set extra HTTP headers for all requests from this context."""
    ensure_page_state(page)
    await page.context().set_extra_http_headers(headers)


async def set_geolocation_via_playwright(
    page: Any,
    latitude: float | None = None,
    longitude: float | None = None,
    accuracy: float | None = None,
    clear: bool = False,
) -> None:
    """Set or clear geolocation for the page context."""
    ensure_page_state(page)
    if clear:
        await page.context().set_geolocation(None)
        return
    if latitude is None or longitude is None:
        raise ValueError("latitude and longitude are required")
    geo: dict[str, Any] = {"latitude": latitude, "longitude": longitude}
    if accuracy is not None:
        geo["accuracy"] = accuracy
    await page.context().set_geolocation(geo)


async def set_viewport_via_playwright(
    page: Any,
    width: int,
    height: int,
) -> None:
    """Resize the viewport."""
    ensure_page_state(page)
    await page.set_viewport_size({"width": width, "height": height})


async def emulate_device_via_playwright(
    page: Any,
    device_name: str,
) -> None:
    """Emulate a named device (from playwright device list)."""
    ensure_page_state(page)
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise RuntimeError("playwright not installed")
    try:
        import playwright.async_api as pw_api
        devices = getattr(pw_api, "DEVICES", None)
        if devices is None:
            from playwright.async_api import devices
        device = devices.get(device_name)
        if not device:
            raise ValueError(f"Unknown device: {device_name}")
        await page.emulate_media(device.get("media") or "screen")
        vp = device.get("viewport")
        if vp:
            await page.set_viewport_size(vp)
        ua = device.get("user_agent")
        if ua:
            await page.set_extra_http_headers({"User-Agent": ua})
    except ImportError:
        raise RuntimeError("playwright not installed")


async def set_http_credentials_via_playwright(
    page: Any,
    username: str | None = None,
    password: str | None = None,
    clear: bool = False,
) -> None:
    """Set or clear HTTP basic auth credentials for the page context."""
    ensure_page_state(page)
    if clear:
        await page.context().set_http_credentials(None)
        return
    if not username:
        raise ValueError("username is required (or set clear=True)")
    await page.context().set_http_credentials({"username": username, "password": password or ""})


# ---------------------------------------------------------------------------
# Format page activity as a human-readable summary (for agent tools)
# ---------------------------------------------------------------------------

def format_page_activity_summary(activity: PageActivity, max_items: int = 10) -> str:
    """Format PageActivity as a concise text summary for the agent."""
    lines: list[str] = []

    errors = activity.page_errors[-max_items:]
    if errors:
        lines.append(f"Page errors ({len(activity.page_errors)} total):")
        for e in errors:
            lines.append(f"  ✗ {e.message[:200]}")

    warn_errors = [m for m in activity.console_messages if m.type in ("warn", "error")]
    if warn_errors:
        shown = warn_errors[-max_items:]
        lines.append(f"Console warnings/errors ({len(warn_errors)} total):")
        for m in shown:
            lines.append(f"  [{m.type}] {m.text[:200]}")

    failed = [r for r in activity.network_requests if r.failed or (r.status and r.status >= 400)]
    if failed:
        shown = failed[-max_items:]
        lines.append(f"Failed network requests ({len(failed)} total):")
        for r in shown:
            status = f" ({r.status})" if r.status else ""
            lines.append(f"  {r.method} {r.url[:150]}{status}")

    if not lines:
        return "(no notable page activity)"
    return "\n".join(lines)
