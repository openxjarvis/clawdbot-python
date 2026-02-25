"""
Browser client functions for HTTP communication with browser control server.

Mirrors TypeScript browser/client.ts and browser/client-actions.ts
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Literal

import aiohttp

logger = logging.getLogger(__name__)

DEFAULT_BROWSER_TIMEOUT_MS = 15000


async def fetch_browser_json(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: str | None = None,
    timeout_ms: int = DEFAULT_BROWSER_TIMEOUT_MS,
) -> dict[str, Any]:
    """
    Fetch JSON from browser control server.
    
    Args:
        url: Full URL to fetch
        method: HTTP method
        headers: Optional headers
        body: Optional request body (JSON string)
        timeout_ms: Request timeout in milliseconds
        
    Returns:
        Parsed JSON response
    """
    timeout = aiohttp.ClientTimeout(total=timeout_ms / 1000)
    
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.request(
                method=method,
                url=url,
                headers=headers,
                data=body,
            ) as response:
                response.raise_for_status()
                return await response.json()
    except aiohttp.ClientError as e:
        logger.error(f"Browser client error: {e}")
        raise RuntimeError(f"Browser control server request failed: {e}")
    except asyncio.TimeoutError:
        raise RuntimeError(f"Browser control server request timed out after {timeout_ms}ms")


def build_profile_query(profile: str | None) -> str:
    """Build profile query string"""
    return f"?profile={profile}" if profile else ""


def with_base_url(base_url: str | None, path: str) -> str:
    """Combine base URL with path"""
    if not base_url:
        return path
    base = base_url.rstrip("/")
    return f"{base}{path}"


# ============================================================================
# Status and lifecycle
# ============================================================================


async def browser_status(
    base_url: str | None,
    profile: str | None = None,
) -> dict[str, Any]:
    """
    Get browser status.
    
    Matches TS browserStatus() from client.ts lines 101-109
    
    Returns:
        Status object with enabled, running, pid, cdpPort, etc.
    """
    q = build_profile_query(profile)
    return await fetch_browser_json(
        with_base_url(base_url, f"/{q}"),
        timeout_ms=1500,
    )


async def browser_profiles(base_url: str | None) -> list[dict[str, Any]]:
    """
    List browser profiles.
    
    Matches TS browserProfiles() from client.ts lines 111-119
    
    Returns:
        List of profile status objects
    """
    result = await fetch_browser_json(
        with_base_url(base_url, "/profiles"),
        timeout_ms=3000,
    )
    return result.get("profiles", [])


async def browser_start(
    base_url: str | None,
    profile: str | None = None,
) -> None:
    """
    Start browser.
    
    Matches TS browserStart() from client.ts lines 121-127
    """
    q = build_profile_query(profile)
    await fetch_browser_json(
        with_base_url(base_url, f"/start{q}"),
        method="POST",
        timeout_ms=15000,
    )


async def browser_stop(
    base_url: str | None,
    profile: str | None = None,
) -> None:
    """
    Stop browser.
    
    Matches TS browserStop() from client.ts lines 129-135
    """
    q = build_profile_query(profile)
    await fetch_browser_json(
        with_base_url(base_url, f"/stop{q}"),
        method="POST",
        timeout_ms=15000,
    )


# ============================================================================
# Tab management
# ============================================================================


async def browser_tabs(
    base_url: str | None,
    profile: str | None = None,
) -> list[dict[str, Any]]:
    """
    List browser tabs.
    
    Matches TS browserTabs() from client.ts
    
    Returns:
        List of tab objects with targetId, title, url, etc.
    """
    q = build_profile_query(profile)
    return await fetch_browser_json(
        with_base_url(base_url, f"/tabs{q}"),
        timeout_ms=5000,
    )


async def browser_open_tab(
    base_url: str | None,
    url: str,
    profile: str | None = None,
) -> dict[str, Any]:
    """
    Open new tab.
    
    Matches TS browserOpenTab() from client.ts
    
    Returns:
        Tab result with targetId, url, title
    """
    q = build_profile_query(profile)
    return await fetch_browser_json(
        with_base_url(base_url, f"/tabs/open{q}"),
        method="POST",
        headers={"Content-Type": "application/json"},
        body=json.dumps({"url": url}),
        timeout_ms=15000,
    )


async def browser_focus_tab(
    base_url: str | None,
    target_id: str,
    profile: str | None = None,
) -> None:
    """
    Focus tab by ID.
    
    Matches TS browserFocusTab() from client.ts
    """
    q = build_profile_query(profile)
    await fetch_browser_json(
        with_base_url(base_url, f"/tabs/focus{q}"),
        method="POST",
        headers={"Content-Type": "application/json"},
        body=json.dumps({"targetId": target_id}),
        timeout_ms=5000,
    )


async def browser_close_tab(
    base_url: str | None,
    target_id: str,
    profile: str | None = None,
) -> None:
    """
    Close tab by ID.
    
    Matches TS browserCloseTab() from client.ts
    """
    q = build_profile_query(profile)
    await fetch_browser_json(
        with_base_url(base_url, f"/tabs/{target_id}{q}"),
        method="DELETE",
        timeout_ms=5000,
    )


# ============================================================================
# Snapshot
# ============================================================================


async def browser_snapshot(
    base_url: str | None,
    format: Literal["aria", "ai"] = "ai",
    target_id: str | None = None,
    limit: int | None = None,
    max_chars: int | None = None,
    refs: Literal["role", "aria"] | None = None,
    interactive: bool | None = None,
    compact: bool | None = None,
    depth: int | None = None,
    selector: str | None = None,
    frame: str | None = None,
    labels: bool | None = None,
    mode: Literal["efficient"] | None = None,
    profile: str | None = None,
) -> dict[str, Any]:
    """
    Take browser snapshot (aria or ai format).
    
    Matches TS browserSnapshot() from client.ts
    
    Returns:
        Snapshot result with format-specific data
    """
    q = build_profile_query(profile)
    query_params = {"format": format}
    
    if target_id:
        query_params["targetId"] = target_id
    if limit is not None:
        query_params["limit"] = limit
    if max_chars is not None:
        query_params["maxChars"] = max_chars
    if refs:
        query_params["refs"] = refs
    if interactive is not None:
        query_params["interactive"] = str(interactive).lower()
    if compact is not None:
        query_params["compact"] = str(compact).lower()
    if depth is not None:
        query_params["depth"] = depth
    if selector:
        query_params["selector"] = selector
    if frame:
        query_params["frame"] = frame
    if labels is not None:
        query_params["labels"] = str(labels).lower()
    if mode:
        query_params["mode"] = mode
    
    # Build query string
    query_str = "&".join(f"{k}={v}" for k, v in query_params.items())
    url = with_base_url(base_url, f"/snapshot{q}")
    if query_str:
        url = f"{url}{'&' if q else '?'}{query_str}"
    
    return await fetch_browser_json(url, timeout_ms=20000)


# ============================================================================
# Actions
# ============================================================================


async def browser_navigate(
    base_url: str | None,
    url: str,
    target_id: str | None = None,
    profile: str | None = None,
) -> dict[str, Any]:
    """
    Navigate to URL.
    
    Matches TS browserNavigate() from client-actions-core.ts lines 91-106
    """
    q = build_profile_query(profile)
    return await fetch_browser_json(
        with_base_url(base_url, f"/navigate{q}"),
        method="POST",
        headers={"Content-Type": "application/json"},
        body=json.dumps({"url": url, "targetId": target_id}),
        timeout_ms=20000,
    )


async def browser_screenshot_action(
    base_url: str | None,
    target_id: str | None = None,
    full_page: bool = False,
    ref: str | None = None,
    element: str | None = None,
    type: Literal["png", "jpeg"] = "png",
    profile: str | None = None,
) -> dict[str, Any]:
    """
    Take screenshot.
    
    Matches TS browserScreenshotAction() from client-actions-core.ts lines 228-248
    """
    q = build_profile_query(profile)
    return await fetch_browser_json(
        with_base_url(base_url, f"/screenshot{q}"),
        method="POST",
        headers={"Content-Type": "application/json"},
        body=json.dumps({
            "targetId": target_id,
            "fullPage": full_page,
            "ref": ref,
            "element": element,
            "type": type,
        }),
        timeout_ms=20000,
    )


async def browser_pdf_save(
    base_url: str | None,
    target_id: str | None = None,
    profile: str | None = None,
) -> dict[str, Any]:
    """
    Save page as PDF.
    
    Matches TS browserPdfSave() from client-actions-core.ts
    """
    q = build_profile_query(profile)
    return await fetch_browser_json(
        with_base_url(base_url, f"/pdf{q}"),
        method="POST",
        headers={"Content-Type": "application/json"},
        body=json.dumps({"targetId": target_id}),
        timeout_ms=20000,
    )


async def browser_console_messages(
    base_url: str | None,
    level: str | None = None,
    target_id: str | None = None,
    profile: str | None = None,
) -> dict[str, Any]:
    """
    Get console messages.
    
    Matches TS browserConsoleMessages() from client-actions-observe.ts
    """
    q = build_profile_query(profile)
    query_params = []
    
    if level:
        query_params.append(f"level={level}")
    if target_id:
        query_params.append(f"targetId={target_id}")
    
    query_str = "&".join(query_params)
    url = with_base_url(base_url, f"/console{q}")
    if query_str:
        url = f"{url}{'&' if q else '?'}{query_str}"
    
    return await fetch_browser_json(url, timeout_ms=5000)


async def browser_act(
    base_url: str | None,
    request: dict[str, Any],
    profile: str | None = None,
) -> dict[str, Any]:
    """
    Perform browser action (click, type, press, etc.).
    
    Matches TS browserAct() from client-actions-core.ts lines 214-226
    
    Args:
        base_url: Browser control server URL
        request: Action request with kind and parameters
        profile: Browser profile
        
    Returns:
        Action result
    """
    q = build_profile_query(profile)
    return await fetch_browser_json(
        with_base_url(base_url, f"/act{q}"),
        method="POST",
        headers={"Content-Type": "application/json"},
        body=json.dumps(request),
        timeout_ms=20000,
    )


async def browser_arm_dialog(
    base_url: str | None,
    accept: bool,
    prompt_text: str | None = None,
    target_id: str | None = None,
    timeout_ms: int | None = None,
    profile: str | None = None,
) -> dict[str, Any]:
    """
    Arm dialog handler.
    
    Matches TS browserArmDialog() from client-actions-core.ts lines 108-130
    """
    q = build_profile_query(profile)
    return await fetch_browser_json(
        with_base_url(base_url, f"/hooks/dialog{q}"),
        method="POST",
        headers={"Content-Type": "application/json"},
        body=json.dumps({
            "accept": accept,
            "promptText": prompt_text,
            "targetId": target_id,
            "timeoutMs": timeout_ms,
        }),
        timeout_ms=20000,
    )


async def browser_arm_file_chooser(
    base_url: str | None,
    paths: list[str],
    ref: str | None = None,
    input_ref: str | None = None,
    element: str | None = None,
    target_id: str | None = None,
    timeout_ms: int | None = None,
    profile: str | None = None,
) -> dict[str, Any]:
    """
    Arm file chooser for upload.
    
    Matches TS browserArmFileChooser() from client-actions-core.ts lines 132-158
    """
    q = build_profile_query(profile)
    return await fetch_browser_json(
        with_base_url(base_url, f"/hooks/file-chooser{q}"),
        method="POST",
        headers={"Content-Type": "application/json"},
        body=json.dumps({
            "paths": paths,
            "ref": ref,
            "inputRef": input_ref,
            "element": element,
            "targetId": target_id,
            "timeoutMs": timeout_ms,
        }),
        timeout_ms=20000,
    )
