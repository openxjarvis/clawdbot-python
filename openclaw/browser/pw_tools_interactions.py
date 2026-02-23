"""Playwright advanced interactions — drag, fill-form, keyboard, dialogs, viewport.

Port of TypeScript:
  openclaw/src/browser/pw-tools-core.interactions.ts (646 lines)

Provides:
  - click_via_playwright (with double-click, button, modifiers)
  - hover_via_playwright
  - drag_via_playwright
  - fill_form_via_playwright (multi-field)
  - select_option_via_playwright
  - press_key_via_playwright
  - type_via_playwright (slow/fast)
  - evaluate_via_playwright (JS eval in page context)
  - arm_dialog_via_playwright (dialog handler registration)
  - scroll_via_playwright
  - highlight_via_playwright
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Literal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_TIMEOUT_MS = 8_000
_MIN_TIMEOUT_MS = 500
_MAX_TIMEOUT_MS = 60_000
_DEFAULT_EVALUATE_TIMEOUT_MS = 20_000


def _clamp_timeout(ms: int | float | None, default: int = _DEFAULT_TIMEOUT_MS) -> int:
    if ms is None or not isinstance(ms, (int, float)):
        ms = default
    return max(_MIN_TIMEOUT_MS, min(_MAX_TIMEOUT_MS, int(ms)))


# ---------------------------------------------------------------------------
# Form field type (mirrors TS BrowserFormField)
# ---------------------------------------------------------------------------

@dataclass
class BrowserFormField:
    ref: str
    type: str   # "text" | "checkbox" | "radio" | "select" | ...
    value: str | bool | int | None = None


# ---------------------------------------------------------------------------
# Interactions
# ---------------------------------------------------------------------------

async def highlight_via_playwright(
    page: Any,
    ref: str,
) -> None:
    """Highlight an element (visual debugging)."""
    locator = _ref_locator(page, ref)
    try:
        await locator.highlight()
    except Exception as exc:
        raise _ai_friendly_error(exc, ref) from exc


async def click_via_playwright(
    page: Any,
    ref: str,
    *,
    double_click: bool = False,
    button: Literal["left", "right", "middle"] | None = None,
    modifiers: list[str] | None = None,
    timeout_ms: int | None = None,
) -> None:
    """
    Click an element identified by a role ref.

    Mirrors TS clickViaPlaywright().

    Args:
        page: Playwright page
        ref: Role reference string (e.g. "e123")
        double_click: Whether to double-click
        button: Mouse button ("left", "right", "middle")
        modifiers: Keyboard modifiers (["Shift", "Control", ...])
        timeout_ms: Click timeout
    """
    timeout = _clamp_timeout(timeout_ms)
    locator = _ref_locator(page, ref)
    click_opts: dict[str, Any] = {"timeout": timeout}
    if button:
        click_opts["button"] = button
    if modifiers:
        click_opts["modifiers"] = modifiers
    try:
        if double_click:
            await locator.dblclick(**click_opts)
        else:
            await locator.click(**click_opts)
    except Exception as exc:
        raise _ai_friendly_error(exc, ref) from exc


async def hover_via_playwright(
    page: Any,
    ref: str,
    *,
    timeout_ms: int | None = None,
) -> None:
    """Hover over an element."""
    timeout = _clamp_timeout(timeout_ms)
    locator = _ref_locator(page, ref)
    try:
        await locator.hover(timeout=timeout)
    except Exception as exc:
        raise _ai_friendly_error(exc, ref) from exc


async def drag_via_playwright(
    page: Any,
    start_ref: str,
    end_ref: str,
    *,
    timeout_ms: int | None = None,
) -> None:
    """
    Drag from one element to another.

    Mirrors TS dragViaPlaywright().
    """
    if not start_ref or not end_ref:
        raise ValueError("start_ref and end_ref are required")
    timeout = _clamp_timeout(timeout_ms)
    start_loc = _ref_locator(page, start_ref)
    end_loc = _ref_locator(page, end_ref)
    try:
        await start_loc.drag_to(end_loc, timeout=timeout)
    except Exception as exc:
        raise _ai_friendly_error(exc, f"{start_ref} -> {end_ref}") from exc


async def select_option_via_playwright(
    page: Any,
    ref: str,
    values: list[str],
    *,
    timeout_ms: int | None = None,
) -> None:
    """Select options in a <select> element."""
    if not values:
        raise ValueError("values are required")
    timeout = _clamp_timeout(timeout_ms)
    locator = _ref_locator(page, ref)
    try:
        await locator.select_option(values, timeout=timeout)
    except Exception as exc:
        raise _ai_friendly_error(exc, ref) from exc


async def press_key_via_playwright(
    page: Any,
    key: str,
    *,
    delay_ms: int = 0,
) -> None:
    """
    Press a keyboard key.

    Mirrors TS pressKeyViaPlaywright().

    Args:
        page: Playwright page
        key: Key name (e.g. "Enter", "Escape", "Control+A")
        delay_ms: Delay between keydown and keyup
    """
    key = str(key or "").strip()
    if not key:
        raise ValueError("key is required")
    await page.keyboard.press(key, delay=max(0, delay_ms))


async def type_via_playwright(
    page: Any,
    ref: str,
    text: str,
    *,
    submit: bool = False,
    slowly: bool = False,
    timeout_ms: int | None = None,
) -> None:
    """
    Type text into an element.

    Mirrors TS typeViaPlaywright().

    Args:
        page: Playwright page
        ref: Role reference
        text: Text to type
        submit: Press Enter after typing
        slowly: Use slow key-by-key typing (75ms delay) instead of fill()
        timeout_ms: Timeout
    """
    timeout = _clamp_timeout(timeout_ms)
    locator = _ref_locator(page, ref)
    try:
        if slowly:
            await locator.click(timeout=timeout)
            await locator.type(text, timeout=timeout, delay=75)
        else:
            await locator.fill(text, timeout=timeout)
        if submit:
            await locator.press("Enter", timeout=timeout)
    except Exception as exc:
        raise _ai_friendly_error(exc, ref) from exc


async def fill_form_via_playwright(
    page: Any,
    fields: list[BrowserFormField],
    *,
    timeout_ms: int | None = None,
) -> None:
    """
    Fill multiple form fields at once.

    Mirrors TS fillFormViaPlaywright().

    Args:
        page: Playwright page
        fields: List of BrowserFormField objects
        timeout_ms: Timeout per field
    """
    timeout = _clamp_timeout(timeout_ms)
    for field in fields:
        ref = str(field.ref or "").strip()
        ftype = str(field.type or "").strip()
        if not ref or not ftype:
            continue
        raw_value = field.value
        if isinstance(raw_value, str):
            value = raw_value
        elif isinstance(raw_value, (int, float, bool)):
            value = str(raw_value)
        else:
            value = ""

        locator = _ref_locator(page, ref)
        if ftype in ("checkbox", "radio"):
            checked = raw_value in (True, 1, "1", "true")
            try:
                await locator.set_checked(checked, timeout=timeout)
            except Exception as exc:
                raise _ai_friendly_error(exc, ref) from exc
        else:
            try:
                await locator.fill(value, timeout=timeout)
            except Exception as exc:
                raise _ai_friendly_error(exc, ref) from exc


async def evaluate_via_playwright(
    page: Any,
    fn: str,
    *,
    ref: str | None = None,
    timeout_ms: int | None = None,
    abort_signal: Any = None,
) -> Any:
    """
    Evaluate JavaScript in the page context.

    Mirrors TS evaluateViaPlaywright().

    Args:
        page: Playwright page
        fn: JavaScript function body or expression string
        ref: Optional element ref to pass as argument
        timeout_ms: Outer timeout
        abort_signal: Optional asyncio.Event for abort

    Returns:
        Whatever the evaluated function returns
    """
    fn_text = str(fn or "").strip()
    if not fn_text:
        raise ValueError("fn (function body) is required")

    outer_timeout = max(_MIN_TIMEOUT_MS, min(120_000, int(timeout_ms or _DEFAULT_EVALUATE_TIMEOUT_MS)))

    try:
        if ref:
            locator = _ref_locator(page, ref)
            result = await asyncio.wait_for(
                locator.evaluate(fn_text),
                timeout=outer_timeout / 1000,
            )
        else:
            result = await asyncio.wait_for(
                page.evaluate(fn_text),
                timeout=outer_timeout / 1000,
            )
        return result
    except asyncio.TimeoutError:
        raise TimeoutError(f"evaluate timed out after {outer_timeout}ms")
    except Exception as exc:
        raise RuntimeError(f"evaluate error: {exc}") from exc


async def scroll_via_playwright(
    page: Any,
    ref: str | None = None,
    *,
    x: int = 0,
    y: int = 0,
    timeout_ms: int | None = None,
) -> None:
    """
    Scroll the page or a specific element.

    Args:
        page: Playwright page
        ref: Optional element ref to scroll into view (or None for page scroll)
        x: Horizontal scroll delta
        y: Vertical scroll delta
        timeout_ms: Timeout
    """
    timeout = _clamp_timeout(timeout_ms)
    if ref:
        locator = _ref_locator(page, ref)
        try:
            await locator.scroll_into_view_if_needed(timeout=timeout)
        except Exception as exc:
            raise _ai_friendly_error(exc, ref) from exc
    else:
        await page.evaluate(f"window.scrollBy({x}, {y})")


# ---------------------------------------------------------------------------
# Dialog handling
# ---------------------------------------------------------------------------

async def arm_dialog_via_playwright(
    page: Any,
    *,
    action: Literal["accept", "dismiss"] = "accept",
    prompt_text: str | None = None,
    timeout_ms: int = 10_000,
) -> None:
    """
    Arm a one-shot dialog handler.

    The next alert/confirm/prompt dialog will be automatically handled.

    Mirrors TS armDialogViaPlaywright().

    Args:
        page: Playwright page
        action: "accept" or "dismiss"
        prompt_text: Text to fill in a prompt dialog before accepting
        timeout_ms: How long to wait for the dialog (unused here — one-shot)
    """

    async def handle_dialog(dialog: Any) -> None:
        try:
            if action == "accept":
                if prompt_text is not None:
                    await dialog.accept(prompt_text)
                else:
                    await dialog.accept()
            else:
                await dialog.dismiss()
        except Exception as exc:
            logger.debug(f"arm_dialog: dialog handling failed: {exc}")

    page.once("dialog", handle_dialog)
    logger.debug(f"arm_dialog_via_playwright: armed action={action}")


# ---------------------------------------------------------------------------
# Viewport resize
# ---------------------------------------------------------------------------

async def resize_viewport_via_playwright(
    page: Any,
    width: int,
    height: int,
) -> None:
    """
    Resize the browser viewport.

    Mirrors TS resizeViewportViaPlaywright().
    """
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")
    await page.set_viewport_size({"width": width, "height": height})


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ref_locator(page: Any, ref: str) -> Any:
    """
    Resolve a role-ref to a Playwright locator.
    Tries the role-ref map first, then falls back to a CSS/text selector.
    """
    if not ref or not ref.strip():
        raise ValueError("ref is required")
    ref = ref.strip()

    # Check if the page has a stored ref map (set by snapshot tools)
    ref_map: dict[str, Any] | None = getattr(page, "_role_refs", None)
    if ref_map and ref in ref_map:
        selector = ref_map[ref]
        return page.locator(selector)

    # Attempt to use ref as an ARIA/CSS selector directly
    if ref.startswith("[") or ref.startswith("#") or ref.startswith("."):
        return page.locator(ref)

    # If it looks like a short ref ID (e.g. "e123"), try the test-id approach
    if ref.isalnum() and len(ref) < 20:
        return page.get_by_test_id(ref)

    # Fallback: treat as text selector
    return page.get_by_text(ref, exact=False)


def _ai_friendly_error(exc: Exception, ref: str | None = None) -> RuntimeError:
    """Convert a Playwright error to a concise, AI-friendly message."""
    msg = str(exc)
    if ref:
        # Strip long stack traces from playwright errors
        first_line = msg.split("\n")[0]
        return RuntimeError(f"Element {ref!r}: {first_line}")
    return RuntimeError(msg.split("\n")[0])
