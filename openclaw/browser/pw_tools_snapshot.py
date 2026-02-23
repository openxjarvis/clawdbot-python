"""Playwright advanced snapshot tools — labeled screenshots, AI snapshot modes.

Port of TypeScript:
  openclaw/src/browser/pw-tools-core.snapshot.ts (205 lines)

Provides:
  - snapshot_aria_via_playwright: accessibility tree snapshot
  - snapshot_ai_via_playwright: playwright AI snapshot (if available)
  - screenshot_with_labels_via_playwright: screenshot + element label overlay
  - snapshot_role_via_playwright: role-based snapshot with ref map
"""
from __future__ import annotations

import base64
import io
import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Role-ref map type: maps short ref ID → selector
RoleRefMap = dict[str, str]


# ---------------------------------------------------------------------------
# Snapshot mode flags
# ---------------------------------------------------------------------------

@dataclass
class SnapshotModeOptions:
    """Flags for snapshot mode selection."""
    efficient: bool = False    # Minimal/compact output for small context windows
    compact: bool = False      # Medium compaction for medium context windows
    full: bool = True          # Full snapshot (default)
    max_chars: int | None = None  # Truncate at this many chars


# ---------------------------------------------------------------------------
# ARIA snapshot
# ---------------------------------------------------------------------------

async def snapshot_aria_via_playwright(
    page: Any,
    *,
    limit: int = 500,
) -> dict[str, Any]:
    """
    Get the ARIA accessibility tree for the page.

    Mirrors TS snapshotAriaViaPlaywright().

    Args:
        page: Playwright page
        limit: Max number of nodes to return

    Returns:
        {"nodes": [...]}
    """
    limit = max(1, min(2000, int(limit)))
    try:
        # Use Playwright's built-in ARIA snapshot
        snapshot_text = await page.accessibility.snapshot()
        if snapshot_text is None:
            return {"nodes": []}
        # Parse the accessibility tree
        return {"nodes": _parse_accessibility_snapshot(snapshot_text, limit)}
    except Exception as exc:
        logger.debug(f"snapshot_aria: failed: {exc}")
        return {"nodes": [], "error": str(exc)}


def _parse_accessibility_snapshot(snapshot: Any, limit: int) -> list[dict]:
    """Convert a Playwright accessibility snapshot to a flat node list."""
    if not snapshot:
        return []
    nodes: list[dict] = []

    def walk(node: dict, depth: int = 0) -> None:
        if len(nodes) >= limit:
            return
        entry: dict = {
            "role": node.get("role", ""),
            "name": node.get("name", ""),
        }
        if node.get("value") is not None:
            entry["value"] = node["value"]
        if node.get("description"):
            entry["description"] = node["description"]
        if depth > 0:
            entry["depth"] = depth
        nodes.append(entry)
        for child in node.get("children") or []:
            walk(child, depth + 1)

    if isinstance(snapshot, dict):
        walk(snapshot)
    return nodes


# ---------------------------------------------------------------------------
# AI snapshot (Playwright's _snapshotForAI if available)
# ---------------------------------------------------------------------------

async def snapshot_ai_via_playwright(
    page: Any,
    *,
    timeout_ms: int = 5_000,
    max_chars: int | None = None,
) -> dict[str, Any]:
    """
    Use Playwright's AI snapshot feature if available.

    Mirrors TS snapshotAiViaPlaywright().

    Returns:
        {"snapshot": str, "truncated": bool, "refs": RoleRefMap}
    """
    timeout = max(500, min(60_000, int(timeout_ms)))

    # Try Playwright's experimental _snapshotForAI
    if hasattr(page, "_snapshotForAI"):
        try:
            result = await page._snapshotForAI(timeout=timeout, track="response")
            snapshot = str(result.get("full") if isinstance(result, dict) else result or "")
            truncated = False
            if max_chars and len(snapshot) > max_chars:
                snapshot = snapshot[:max_chars] + "\n\n[...TRUNCATED - page too large]"
                truncated = True
            refs = _extract_refs_from_ai_snapshot(snapshot)
            # Store refs on the page for later interactions
            page._role_refs = {k: v for k, v in refs.items()}  # type: ignore[attr-defined]
            return {"snapshot": snapshot, "truncated": truncated, "refs": refs}
        except Exception as exc:
            logger.debug(f"snapshot_ai: _snapshotForAI failed: {exc}")

    # Fallback: aria snapshot as text
    aria_result = await snapshot_aria_via_playwright(page)
    snapshot_text = _aria_nodes_to_text(aria_result.get("nodes", []))
    refs = _extract_refs_from_text(snapshot_text)
    return {"snapshot": snapshot_text, "truncated": False, "refs": refs}


def _aria_nodes_to_text(nodes: list[dict]) -> str:
    """Convert ARIA nodes to readable text."""
    lines: list[str] = []
    for node in nodes:
        role = node.get("role", "")
        name = node.get("name", "")
        depth = node.get("depth", 0)
        indent = "  " * depth
        if name:
            lines.append(f"{indent}[{role}] {name!r}")
        else:
            lines.append(f"{indent}[{role}]")
    return "\n".join(lines)


def _extract_refs_from_ai_snapshot(snapshot: str) -> RoleRefMap:
    """Extract element refs from an AI snapshot string."""
    refs: RoleRefMap = {}
    import re
    # Pattern: looks for ref="eXXX" or data-ref="eXXX" in the snapshot
    for m in re.finditer(r'(?:ref|data-ref)=["\']?([a-zA-Z0-9_-]+)["\']?', snapshot):
        ref_id = m.group(1)
        refs[ref_id] = f'[data-ref="{ref_id}"]'
    return refs


def _extract_refs_from_text(text: str) -> RoleRefMap:
    """Extract element refs from a text snapshot."""
    return {}


# ---------------------------------------------------------------------------
# Role-based snapshot with labeled refs
# ---------------------------------------------------------------------------

@dataclass
class RoleSnapshotResult:
    """Result of a role snapshot."""
    snapshot: str = ""
    refs: RoleRefMap = field(default_factory=dict)
    element_count: int = 0
    truncated: bool = False


async def snapshot_role_via_playwright(
    page: Any,
    *,
    mode: str = "full",
    timeout_ms: int = 5_000,
    max_chars: int | None = None,
) -> RoleSnapshotResult:
    """
    Get a role-based snapshot of the page with element references.

    Mirrors TS snapshotRoleViaPlaywright(). Uses existing role_snapshots
    module if available, otherwise falls back to aria snapshot.

    Args:
        page: Playwright page
        mode: Snapshot mode ("full", "compact", "efficient")
        timeout_ms: Timeout
        max_chars: Optional char limit

    Returns:
        RoleSnapshotResult with snapshot text and ref map
    """
    try:
        from openclaw.browser.role_snapshots import build_role_snapshot
        result = await build_role_snapshot(page, mode=mode, timeout_ms=timeout_ms)
        snapshot = result.get("snapshot") or ""
        refs = result.get("refs") or {}
        truncated = False
        if max_chars and len(snapshot) > max_chars:
            snapshot = snapshot[:max_chars] + "\n\n[...TRUNCATED]"
            truncated = True
        # Store refs on page for interaction tools
        if hasattr(page, "_role_refs"):
            page._role_refs.update(refs)
        else:
            page._role_refs = dict(refs)  # type: ignore[attr-defined]
        return RoleSnapshotResult(
            snapshot=snapshot,
            refs=refs,
            element_count=len(refs),
            truncated=truncated,
        )
    except Exception as exc:
        logger.debug(f"snapshot_role: build_role_snapshot failed: {exc}")

    # Fallback to AI snapshot
    ai_result = await snapshot_ai_via_playwright(page, timeout_ms=timeout_ms, max_chars=max_chars)
    return RoleSnapshotResult(
        snapshot=ai_result.get("snapshot", ""),
        refs=ai_result.get("refs", {}),
        element_count=len(ai_result.get("refs", {})),
        truncated=ai_result.get("truncated", False),
    )


# ---------------------------------------------------------------------------
# Screenshot with element labels overlay
# ---------------------------------------------------------------------------

async def screenshot_with_labels_via_playwright(
    page: Any,
    *,
    timeout_ms: int = 5_000,
    full_page: bool = False,
    refs: RoleRefMap | None = None,
) -> dict[str, Any]:
    """
    Take a screenshot and optionally overlay element reference labels.

    Mirrors TS screenshotWithLabelsViaPlaywright().

    Args:
        page: Playwright page
        timeout_ms: Timeout for snapshot (if taking refs from page)
        full_page: Whether to capture the full page
        refs: Pre-existing ref map; if None, uses page._role_refs

    Returns:
        {"screenshot_base64": str, "refs": RoleRefMap, "width": int, "height": int}
    """
    # Take screenshot
    screenshot_bytes = await page.screenshot(full_page=full_page)
    screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")

    # Resolve ref map
    if refs is None:
        refs = getattr(page, "_role_refs", None) or {}

    # Get viewport size
    viewport = page.viewport_size or {}
    width = viewport.get("width", 0)
    height = viewport.get("height", 0)

    # Optionally overlay labels using PIL if available
    if refs:
        try:
            labeled_b64 = await _overlay_labels_on_screenshot(
                page, screenshot_bytes, refs
            )
            if labeled_b64:
                screenshot_b64 = labeled_b64
        except Exception as exc:
            logger.debug(f"screenshot_with_labels: overlay failed: {exc}")

    return {
        "screenshot_base64": screenshot_b64,
        "refs": refs,
        "width": width,
        "height": height,
    }


async def _overlay_labels_on_screenshot(
    page: Any,
    screenshot_bytes: bytes,
    refs: RoleRefMap,
) -> str | None:
    """
    Try to draw bounding-box labels on the screenshot.
    Returns base64 string, or None if PIL is not available.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore[import]
        import io as _io
    except ImportError:
        return None

    # Get element bounding boxes
    boxes: dict[str, dict] = {}
    for ref_id, selector in list(refs.items())[:50]:  # Limit to 50 elements
        try:
            locator = page.locator(selector)
            bb = await locator.bounding_box()
            if bb:
                boxes[ref_id] = bb
        except Exception:
            continue

    if not boxes:
        return None

    img = Image.open(_io.BytesIO(screenshot_bytes))
    draw = ImageDraw.Draw(img)

    for ref_id, bb in boxes.items():
        x, y, w, h = int(bb["x"]), int(bb["y"]), int(bb["width"]), int(bb["height"])
        draw.rectangle([x, y, x + w, y + h], outline="red", width=2)
        draw.text((x + 2, y + 2), ref_id, fill="red")

    out = _io.BytesIO()
    img.save(out, format="PNG")
    return base64.b64encode(out.getvalue()).decode("utf-8")
