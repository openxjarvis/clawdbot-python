"""Cron session reaper — prunes completed isolated cron run sessions.

Mirrors TypeScript: openclaw/src/cron/session-reaper.ts

Pattern: sessions keyed as `...:cron:<jobId>:run:<uuid>` are ephemeral
run records. The base session (`...:cron:<jobId>`) is kept as-is.
"""
from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_RETENTION_MS = 24 * 3_600_000  # 24 hours
MIN_SWEEP_INTERVAL_MS = 5 * 60_000     # 5 minutes

# Per-store-path last sweep tracking (matches TS lastSweepAtMsByStore)
_last_sweep_at_ms_by_store: dict[str, int] = {}

# Cron run session key pattern: agent:<name>:cron:<jobId>:run:<uuid>
# Matches TS: /^agent:[^:]+:cron:[^:]+:run:.+$/
_CRON_RUN_SESSION_KEY_RE = re.compile(r"^agent:[^:]+:cron:[^:]+:run:.+$", re.IGNORECASE)


def is_cron_run_session_key(key: str) -> bool:
    """Check if session key matches the cron run pattern."""
    return bool(_CRON_RUN_SESSION_KEY_RE.search(key))


def resolve_retention_ms(cron_config: dict[str, Any] | None) -> int | None:
    """Resolve retention period in ms from config.

    Returns None if pruning is disabled (sessionRetention=false).
    """
    if cron_config is None:
        return DEFAULT_RETENTION_MS

    retention = cron_config.get("sessionRetention")
    if retention is False:
        return None  # pruning disabled

    if isinstance(retention, str) and retention.strip():
        try:
            return _parse_duration_ms(retention.strip())
        except Exception:
            return DEFAULT_RETENTION_MS

    if isinstance(retention, (int, float)) and retention > 0:
        return int(retention)

    return DEFAULT_RETENTION_MS


def _parse_duration_ms(raw: str) -> int:
    """Parse a duration string like "24h", "30m", "1d" to milliseconds."""
    raw = raw.strip().lower()
    units = {
        "ms": 1,
        "s": 1_000,
        "m": 60_000,
        "h": 3_600_000,
        "d": 86_400_000,
    }
    for suffix, multiplier in units.items():
        if raw.endswith(suffix):
            try:
                n = float(raw[: -len(suffix)])
                return int(n * multiplier)
            except ValueError:
                pass
    # Default to hours if just a number
    try:
        return int(float(raw) * 3_600_000)
    except ValueError:
        raise ValueError(f"Cannot parse duration: {raw!r}")


async def sweep_cron_run_sessions(
    cron_config: dict[str, Any] | None = None,
    session_store_path: str | None = None,
    now_ms: int | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Sweep the session store and prune expired cron run sessions.

    Self-throttles to MIN_SWEEP_INTERVAL_MS per store path.
    Must be called OUTSIDE cron service locked() sections.

    Returns: {"swept": bool, "pruned": int}
    """
    if not session_store_path:
        return {"swept": False, "pruned": 0}

    now = now_ms if now_ms is not None else int(time.time() * 1000)
    store_path = str(session_store_path)
    last_sweep = _last_sweep_at_ms_by_store.get(store_path, 0)

    # Throttle
    if not force and now - last_sweep < MIN_SWEEP_INTERVAL_MS:
        return {"swept": False, "pruned": 0}

    retention_ms = resolve_retention_ms(cron_config)
    if retention_ms is None:
        _last_sweep_at_ms_by_store[store_path] = now
        return {"swept": False, "pruned": 0}

    pruned = 0
    try:
        pruned = _sweep_store(store_path, now=now, retention_ms=retention_ms)
    except Exception as e:
        logger.warning(f"cron-reaper: failed to sweep session store {store_path!r}: {e}")
        return {"swept": False, "pruned": 0}

    _last_sweep_at_ms_by_store[store_path] = now

    if pruned > 0:
        logger.info(
            f"cron-reaper: pruned {pruned} expired cron run session(s) "
            f"(retentionMs={retention_ms}, store={store_path!r})"
        )

    return {"swept": True, "pruned": pruned}


def _sweep_store(store_path: str, now: int, retention_ms: int) -> int:
    """Load, prune expired cron run sessions, and atomically save."""
    path = Path(store_path)
    if not path.exists():
        return 0

    try:
        with open(path, encoding="utf-8") as f:
            store: dict[str, Any] = json.load(f)
    except (json.JSONDecodeError, OSError):
        return 0

    if not isinstance(store, dict):
        return 0

    cutoff = now - retention_ms
    pruned = 0
    keys_to_delete = []

    for key, entry in store.items():
        if not is_cron_run_session_key(key):
            continue
        if not isinstance(entry, dict):
            continue
        updated_at = entry.get("updatedAt") or entry.get("updated_at") or 0
        if updated_at < cutoff:
            keys_to_delete.append(key)

    if not keys_to_delete:
        return 0

    for key in keys_to_delete:
        del store[key]
        pruned += 1

    # Atomic write
    import uuid
    tmp = path.with_suffix(f".{uuid.uuid4().hex[:8]}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(store, f, indent=2)
        tmp.replace(path)
    except Exception as e:
        logger.error(f"cron-reaper: failed to write pruned store: {e}")
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        raise

    return pruned


def reset_reaper_throttle() -> None:
    """Reset throttle timers — for tests."""
    _last_sweep_at_ms_by_store.clear()
