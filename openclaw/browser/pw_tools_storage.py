"""Playwright storage operations — cookies, localStorage, sessionStorage.

Port of TypeScript:
  openclaw/src/browser/pw-tools-core.storage.ts (128 lines)

Provides:
  - cookies_get_via_playwright / cookies_set_via_playwright / cookies_clear_via_playwright
  - storage_get_via_playwright / storage_set_via_playwright / storage_clear_via_playwright
"""
from __future__ import annotations

import logging
from typing import Any, Literal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

StorageKind = Literal["local", "session"]


# ---------------------------------------------------------------------------
# Cookies
# ---------------------------------------------------------------------------

async def cookies_get_via_playwright(page: Any) -> dict[str, Any]:
    """
    Get all cookies from the page context.

    Mirrors TS cookiesGetViaPlaywright().

    Returns:
        {"cookies": [...]}
    """
    cookies = await page.context().cookies()
    return {"cookies": cookies}


async def cookies_set_via_playwright(
    page: Any,
    cookie: dict[str, Any],
) -> None:
    """
    Add a cookie to the page context.

    Mirrors TS cookiesSetViaPlaywright().

    Args:
        page: Playwright page
        cookie: Dict with required keys name, value, and one of url or (domain+path)
    """
    name = cookie.get("name") or ""
    value = cookie.get("value")

    if not name or value is None:
        raise ValueError("cookie name and value are required")

    has_url = bool(str(cookie.get("url") or "").strip())
    has_domain_path = (
        bool(str(cookie.get("domain") or "").strip())
        and bool(str(cookie.get("path") or "").strip())
    )

    if not has_url and not has_domain_path:
        raise ValueError("cookie requires url, or domain+path")

    await page.context().add_cookies([cookie])


async def cookies_clear_via_playwright(page: Any) -> None:
    """
    Clear all cookies from the page context.

    Mirrors TS cookiesClearViaPlaywright().
    """
    await page.context().clear_cookies()


# ---------------------------------------------------------------------------
# localStorage / sessionStorage
# ---------------------------------------------------------------------------

async def storage_get_via_playwright(
    page: Any,
    kind: StorageKind,
    key: str | None = None,
) -> dict[str, Any]:
    """
    Get localStorage or sessionStorage values.

    Mirrors TS storageGetViaPlaywright().

    Args:
        page: Playwright page
        kind: "local" or "session"
        key: If provided, get only this key. If None, get all keys.

    Returns:
        {"values": {"key": "value", ...}}
    """
    if kind not in ("local", "session"):
        raise ValueError(f"kind must be 'local' or 'session', got: {kind!r}")

    values = await page.evaluate(
        """
        ([kind, key]) => {
            const store = kind === "session" ? window.sessionStorage : window.localStorage;
            if (key !== null && key !== undefined) {
                const value = store.getItem(key);
                return value === null ? {} : { [key]: value };
            }
            const out = {};
            for (let i = 0; i < store.length; i++) {
                const k = store.key(i);
                if (k !== null) {
                    const v = store.getItem(k);
                    if (v !== null) {
                        out[k] = v;
                    }
                }
            }
            return out;
        }
        """,
        [kind, key],
    )
    return {"values": values or {}}


async def storage_set_via_playwright(
    page: Any,
    kind: StorageKind,
    key: str,
    value: str,
) -> None:
    """
    Set a localStorage or sessionStorage value.

    Mirrors TS storageSetViaPlaywright().

    Args:
        page: Playwright page
        kind: "local" or "session"
        key: Storage key (required)
        value: Storage value
    """
    if kind not in ("local", "session"):
        raise ValueError(f"kind must be 'local' or 'session', got: {kind!r}")
    if not key:
        raise ValueError("key is required")

    await page.evaluate(
        """
        ([kind, key, value]) => {
            const store = kind === "session" ? window.sessionStorage : window.localStorage;
            store.setItem(key, value);
        }
        """,
        [kind, str(key), str(value)],
    )


async def storage_clear_via_playwright(
    page: Any,
    kind: StorageKind,
) -> None:
    """
    Clear all values from localStorage or sessionStorage.

    Mirrors TS storageClearViaPlaywright().
    """
    if kind not in ("local", "session"):
        raise ValueError(f"kind must be 'local' or 'session', got: {kind!r}")

    await page.evaluate(
        """
        ([kind]) => {
            const store = kind === "session" ? window.sessionStorage : window.localStorage;
            store.clear();
        }
        """,
        [kind],
    )


# ---------------------------------------------------------------------------
# Convenience: get/set specific localStorage key (common pattern)
# ---------------------------------------------------------------------------

async def local_storage_get(page: Any, key: str) -> str | None:
    """Get a single localStorage value. Returns None if not found."""
    result = await storage_get_via_playwright(page, "local", key)
    return result["values"].get(key)


async def local_storage_set(page: Any, key: str, value: str) -> None:
    """Set a single localStorage value."""
    await storage_set_via_playwright(page, "local", key, value)


async def local_storage_get_all(page: Any) -> dict[str, str]:
    """Get all localStorage values."""
    result = await storage_get_via_playwright(page, "local")
    return result["values"]


async def session_storage_get(page: Any, key: str) -> str | None:
    """Get a single sessionStorage value."""
    result = await storage_get_via_playwright(page, "session", key)
    return result["values"].get(key)


async def session_storage_set(page: Any, key: str, value: str) -> None:
    """Set a single sessionStorage value."""
    await storage_set_via_playwright(page, "session", key, value)
