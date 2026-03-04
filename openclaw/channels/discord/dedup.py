"""Two-layer message deduplication — mirrors TS Discord dedup logic."""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_MEMORY_TTL = 60.0  # seconds — keep seen IDs for 1 minute
_PERSIST_TTL = 3600.0  # seconds — persist IDs for 1 hour


class _MemoryDedup:
    """Fast in-process dedup using a TTL dict."""

    def __init__(self, ttl: float = _MEMORY_TTL) -> None:
        self._ttl = ttl
        self._seen: dict[str, float] = {}

    def _evict(self) -> None:
        now = time.monotonic()
        expired = [k for k, v in self._seen.items() if now > v]
        for k in expired:
            del self._seen[k]

    def is_seen(self, key: str) -> bool:
        self._evict()
        now = time.monotonic()
        if key in self._seen:
            return True
        self._seen[key] = now + self._ttl
        return False


class _PersistentDedup:
    """
    JSON file-backed dedup for cross-restart deduplication.
    Mirrors the file-based dedup used in WhatsApp/Feishu channels.
    """

    def __init__(self, path: Path, ttl: float = _PERSIST_TTL) -> None:
        self._path = path
        self._ttl = ttl
        self._data: dict[str, float] = {}
        self._load()

    def _load(self) -> None:
        try:
            if self._path.exists():
                raw = json.loads(self._path.read_text())
                now = time.time()
                # Discard expired entries on load
                self._data = {k: v for k, v in raw.items() if isinstance(v, (int, float)) and v > now}
        except Exception as exc:
            logger.debug("[discord][dedup] Failed to load persistent dedup: %s", exc)
            self._data = {}

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(self._data))
        except Exception as exc:
            logger.debug("[discord][dedup] Failed to save persistent dedup: %s", exc)

    def is_seen(self, key: str) -> bool:
        now = time.time()
        if key in self._data and self._data[key] > now:
            return True
        self._data[key] = now + self._ttl
        # Evict expired
        self._data = {k: v for k, v in self._data.items() if v > now}
        self._save()
        return False


class DiscordDedup:
    """Combines memory + persistent dedup layers."""

    def __init__(self, persist_dir: Path | None = None, account_id: str = "default") -> None:
        self._memory = _MemoryDedup()
        if persist_dir:
            path = persist_dir / f"discord_dedup_{account_id}.json"
            self._persistent: _PersistentDedup | None = _PersistentDedup(path)
        else:
            self._persistent = None

    def is_duplicate(self, message_id: str) -> bool:
        """Return True if this message_id was already seen (and register it if new)."""
        if self._memory.is_seen(message_id):
            return True
        if self._persistent and self._persistent.is_seen(message_id):
            return True
        return False
