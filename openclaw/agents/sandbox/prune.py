"""Sandbox container pruning

Auto-removes stale sandbox containers based on idle-time and max-age thresholds.
Rate-limited to run at most once per 5 minutes.

Mirrors TypeScript openclaw/src/agents/sandbox/prune.ts
"""
from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from .docker import exec_docker
from .manage import _read_registry, _remove_registry_entry
from .manage import (
    _SANDBOX_REGISTRY_PATH,
    _SANDBOX_BROWSER_REGISTRY_PATH,
)

logger = logging.getLogger(__name__)

# Rate-limit: only prune once per 5 minutes
_last_prune_at_ms: float = 0.0
_PRUNE_INTERVAL_MS = 5 * 60 * 1000


def _should_prune_entry(
    entry: dict,
    idle_hours: int,
    max_age_days: int,
    now_ms: float,
) -> bool:
    """Return True if the registry entry is stale enough to prune.

    Mirrors TS ``shouldPruneSandboxEntry()``.
    """
    if idle_hours == 0 and max_age_days == 0:
        return False

    idle_ms = now_ms - entry.get("lastUsedAtMs", now_ms)
    age_ms = now_ms - entry.get("createdAtMs", now_ms)

    idle_expired = idle_hours > 0 and idle_ms > idle_hours * 3_600_000
    age_expired = max_age_days > 0 and age_ms > max_age_days * 86_400_000
    return idle_expired or age_expired


async def _prune_registry_entries(
    registry_path: str,
    idle_hours: int,
    max_age_days: int,
) -> int:
    """Prune stale entries from a registry file. Returns count removed."""
    if idle_hours == 0 and max_age_days == 0:
        return 0

    entries = await _read_registry(registry_path)
    now_ms = time.time() * 1000
    removed = 0

    for entry in entries:
        if not _should_prune_entry(entry, idle_hours, max_age_days, now_ms):
            continue

        cname = entry.get("containerName", "")
        try:
            await exec_docker(["rm", "-f", cname], allow_failure=True)
        except Exception:
            pass

        try:
            await _remove_registry_entry(cname, registry_path)
            removed += 1
            logger.info("Pruned stale sandbox container: %s", cname)
        except Exception as exc:
            logger.warning("Failed to remove registry entry for %s: %s", cname, exc)

    return removed


async def maybe_prune_sandboxes(
    idle_hours: int | None = None,
    max_age_days: int | None = None,
    registry_path: str | None = None,
    browser_registry_path: str | None = None,
) -> None:
    """Prune stale sandbox containers if the rate-limit interval has elapsed.

    Mirrors TS ``maybePruneSandboxes()``.

    Args:
        idle_hours: Max idle time before pruning (hours). Defaults to config value
            (24 h). Pass 0 to skip idle pruning.
        max_age_days: Max age before pruning (days). Defaults to config value (7 d).
            Pass 0 to skip age pruning.
        registry_path: Override path to containers registry JSON.
        browser_registry_path: Override path to browsers registry JSON.
    """
    global _last_prune_at_ms

    now_ms = time.time() * 1000
    if now_ms - _last_prune_at_ms < _PRUNE_INTERVAL_MS:
        return

    _last_prune_at_ms = now_ms

    # Resolve thresholds from config if not provided
    if idle_hours is None or max_age_days is None:
        try:
            from openclaw.config.loader import load_config  # type: ignore[import]
            from .config import resolve_sandbox_config_for_agent
            cfg = load_config()
            prune_cfg = resolve_sandbox_config_for_agent(cfg, None).prune
            if idle_hours is None:
                idle_hours = prune_cfg.idle_hours
            if max_age_days is None:
                max_age_days = prune_cfg.max_age_days
        except (ImportError, Exception):
            idle_hours = idle_hours if idle_hours is not None else 24
            max_age_days = max_age_days if max_age_days is not None else 7

    rpath = registry_path or _SANDBOX_REGISTRY_PATH
    brpath = browser_registry_path or _SANDBOX_BROWSER_REGISTRY_PATH

    try:
        removed = await _prune_registry_entries(rpath, idle_hours, max_age_days)
        browser_removed = await _prune_registry_entries(brpath, idle_hours, max_age_days)
        if removed or browser_removed:
            logger.info("Sandbox prune: removed %d container(s), %d browser(s)", removed, browser_removed)
    except Exception as exc:
        logger.error("Sandbox prune failed: %s", exc, exc_info=True)


def should_prune_sandbox_entry(
    entry: dict,
    idle_hours: int,
    max_age_days: int,
) -> bool:
    """Public helper: test whether a registry entry should be pruned now.

    Mirrors TS ``shouldPruneSandboxEntry()`` (exported for tests).
    """
    now_ms = time.time() * 1000
    return _should_prune_entry(entry, idle_hours, max_age_days, now_ms)
