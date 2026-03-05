"""Message deduplication for Feishu channel.

Two-layer deduplication:
  1. In-memory cache  — fast, synchronous, TTL 24h, max 1000 entries
  2. Persistent JSON  — survives process restarts, TTL 24h, max 10000 entries

Mirrors TypeScript: extensions/feishu/src/dedup.ts
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING

from openclaw.config.paths import STATE_DIR as _STATE_DIR

if TYPE_CHECKING:
    from .config import ResolvedFeishuAccount

logger = logging.getLogger(__name__)

_DEDUP_TTL_SECONDS = 24 * 60 * 60     # 24 hours
_MEMORY_MAX_ENTRIES = 1_000
_PERSIST_MAX_ENTRIES = 10_000


# ---------------------------------------------------------------------------
# In-memory cache (per-account)
# ---------------------------------------------------------------------------

class _MemoryDedup:
    """Fixed-size TTL cache for message IDs."""

    def __init__(self, ttl: float = _DEDUP_TTL_SECONDS, max_size: int = _MEMORY_MAX_ENTRIES) -> None:
        self._ttl = ttl
        self._max = max_size
        # {msg_id: expiry_ts}
        self._store: dict[str, float] = {}

    def seen(self, msg_id: str) -> bool:
        """Return True if message was already seen (and not expired)."""
        entry = self._store.get(msg_id)
        if entry is None:
            return False
        if time.time() > entry:
            del self._store[msg_id]
            return False
        return True

    def record(self, msg_id: str) -> None:
        """Record message as seen."""
        self._evict_if_needed()
        self._store[msg_id] = time.time() + self._ttl

    def _evict_if_needed(self) -> None:
        if len(self._store) < self._max:
            return
        now = time.time()
        # Remove expired entries first
        expired = [k for k, v in self._store.items() if now > v]
        for k in expired:
            del self._store[k]
        # If still too large, remove oldest (lowest expiry)
        if len(self._store) >= self._max:
            oldest = sorted(self._store, key=lambda k: self._store[k])
            for k in oldest[: len(self._store) - self._max + 1]:
                del self._store[k]


# ---------------------------------------------------------------------------
# Persistent JSON file cache (per-account)
# ---------------------------------------------------------------------------

class _PersistentDedup:
    """JSON file-backed TTL dedup store."""

    def __init__(self, path: Path, ttl: float = _DEDUP_TTL_SECONDS, max_size: int = _PERSIST_MAX_ENTRIES) -> None:
        self._path = path
        self._ttl = ttl
        self._max = max_size
        self._store: dict[str, float] = {}  # {msg_id: expiry_ts}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text())
            now = time.time()
            self._store = {k: v for k, v in data.items() if now < v}
        except Exception as e:
            logger.warning("[feishu] Failed to load dedup store %s: %s", self._path, e)
            self._store = {}

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(self._store))
        except Exception as e:
            logger.warning("[feishu] Failed to save dedup store %s: %s", self._path, e)

    def seen(self, msg_id: str) -> bool:
        entry = self._store.get(msg_id)
        if entry is None:
            return False
        if time.time() > entry:
            del self._store[msg_id]
            return False
        return True

    def record(self, msg_id: str) -> None:
        self._evict_if_needed()
        self._store[msg_id] = time.time() + self._ttl
        self._save()

    def _evict_if_needed(self) -> None:
        if len(self._store) < self._max:
            return
        now = time.time()
        expired = [k for k, v in self._store.items() if now > v]
        for k in expired:
            del self._store[k]
        if len(self._store) >= self._max:
            oldest = sorted(self._store, key=lambda k: self._store[k])
            for k in oldest[: len(self._store) - self._max + 1]:
                del self._store[k]


# ---------------------------------------------------------------------------
# Per-account dedup manager
# ---------------------------------------------------------------------------

class FeishuDedup:
    """Combined two-layer dedup for a single Feishu account."""

    def __init__(self, account_id: str) -> None:
        self._memory = _MemoryDedup()
        data_dir = Path(_STATE_DIR) / "feishu" / "dedup"
        self._persistent = _PersistentDedup(data_dir / f"{account_id}.json")

    def is_duplicate(self, msg_id: str) -> bool:
        """Return True if this message was already processed."""
        return self._memory.seen(msg_id) or self._persistent.seen(msg_id)

    def record(self, msg_id: str) -> None:
        """Mark message as processed in both layers."""
        self._memory.record(msg_id)
        self._persistent.record(msg_id)

    def try_record(self, msg_id: str) -> bool:
        """
        Atomically check-and-record.

        Returns True if this is the FIRST time we see this message (not a dupe).
        Returns False if it was already seen.

        Mirrors TS tryRecordMessage() + tryRecordMessagePersistent().
        """
        if self.is_duplicate(msg_id):
            return False
        self.record(msg_id)
        return True


# ---------------------------------------------------------------------------
# Module-level cache of FeishuDedup instances
# ---------------------------------------------------------------------------

_dedup_instances: dict[str, FeishuDedup] = {}


def get_dedup(account_id: str) -> FeishuDedup:
    """Return (or create) the FeishuDedup instance for the given account."""
    if account_id not in _dedup_instances:
        _dedup_instances[account_id] = FeishuDedup(account_id)
    return _dedup_instances[account_id]
