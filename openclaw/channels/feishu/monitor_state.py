"""Shared mutable state for Feishu account monitors.

Mirrors TypeScript: extensions/feishu/src/monitor.state.ts

Holds:
  - ws_clients dict (running WS client instances per account)
  - bot_open_ids dict (prefetched bot open_id per account)
  - per-account rate limiter for webhook requests
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Bot open_id cache
# ---------------------------------------------------------------------------

# {account_id: open_id}
_bot_open_ids: dict[str, str] = {}


def set_bot_open_id(account_id: str, open_id: str) -> None:
    _bot_open_ids[account_id] = open_id


def get_bot_open_id(account_id: str) -> str | None:
    return _bot_open_ids.get(account_id)


# ---------------------------------------------------------------------------
# WS client registry
# ---------------------------------------------------------------------------

# {account_id: ws_client_instance}
_ws_clients: dict[str, Any] = {}


def set_ws_client(account_id: str, client: Any) -> None:
    _ws_clients[account_id] = client


def get_ws_client(account_id: str) -> Any | None:
    return _ws_clients.get(account_id)


def remove_ws_client(account_id: str) -> None:
    _ws_clients.pop(account_id, None)


# ---------------------------------------------------------------------------
# Fixed-window rate limiter (for webhook endpoints)
# ---------------------------------------------------------------------------

class _FixedWindowRateLimiter:
    """
    Simple fixed-window rate limiter.

    Mirrors TS FixedWindowRateLimiter used for webhook endpoints.
    """

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._counts: dict[str, list[float]] = {}  # key → [timestamps]
        self._lock = asyncio.Lock()

    async def is_allowed(self, key: str) -> bool:
        async with self._lock:
            now = time.time()
            window_start = now - self._window
            timestamps = [t for t in self._counts.get(key, []) if t > window_start]
            if len(timestamps) >= self._max:
                return False
            timestamps.append(now)
            self._counts[key] = timestamps
            return True


# Default webhook rate limiter: 100 req/10s per IP+path
_webhook_rate_limiter = _FixedWindowRateLimiter(
    max_requests=100,
    window_seconds=10.0,
)


def get_webhook_rate_limiter() -> _FixedWindowRateLimiter:
    return _webhook_rate_limiter


# ---------------------------------------------------------------------------
# Probe cache (GET /open-apis/bot/v3/info per account, TTL 10 min success / 1 min error)
# ---------------------------------------------------------------------------

# {account_id: (result_dict, expire_at)}
_probe_cache: dict[str, tuple[dict[str, Any], float]] = {}

# Separate TTLs matching TS probe.ts behaviour
_PROBE_SUCCESS_TTL = 10 * 60.0   # 10 minutes on success
_PROBE_ERROR_TTL = 1 * 60.0      # 1 minute on error

MAX_PROBE_CACHE_SIZE = 64


def get_probe_cache(account_id: str) -> dict[str, Any] | None:
    cached = _probe_cache.get(account_id)
    if cached and time.time() < cached[1]:
        return cached[0]
    _probe_cache.pop(account_id, None)
    return None


def set_probe_cache(
    account_id: str,
    data: dict[str, Any],
    *,
    is_error: bool = False,
) -> None:
    """Cache a probe result with success or error TTL.

    Evicts the oldest entry when the cache exceeds MAX_PROBE_CACHE_SIZE.
    Mirrors TS probe.ts setCached() with MAX_PROBE_CACHE_SIZE = 64.
    """
    ttl = _PROBE_ERROR_TTL if is_error else _PROBE_SUCCESS_TTL
    _probe_cache[account_id] = (data, time.time() + ttl)
    if len(_probe_cache) > MAX_PROBE_CACHE_SIZE:
        oldest_key = next(iter(_probe_cache))
        _probe_cache.pop(oldest_key, None)


def clear_probe_cache() -> None:
    """Clear the probe cache (for testing). Mirrors TS clearProbeCache()."""
    _probe_cache.clear()
