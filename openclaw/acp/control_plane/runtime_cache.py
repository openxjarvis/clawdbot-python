"""ACP runtime handle cache — mirrors src/acp/control-plane/runtime-cache.ts

In-memory LRU-style cache of AcpRuntimeHandle entries, indexed by actor key
(lower-cased session key). Supports idle TTL eviction via collectIdleCandidates().
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class CachedRuntimeState:
    runtime: Any  # AcpRuntime instance
    handle: dict  # AcpRuntimeHandle
    backend: str
    agent: str
    mode: str  # "persistent" | "oneshot"
    cwd: Optional[str] = None
    applied_control_signature: Optional[str] = None


@dataclass
class _CacheEntry:
    state: CachedRuntimeState
    last_touched_at: float = field(default_factory=time.time)


@dataclass
class CachedRuntimeSnapshot:
    actor_key: str
    state: CachedRuntimeState
    last_touched_at: float
    idle_ms: float


class RuntimeCache:
    """
    In-memory cache of active ACP runtime handles indexed by actor key.

    The cache tracks when each entry was last used (last_touched_at) to
    enable idle TTL eviction by the session manager.
    """

    def __init__(self) -> None:
        self._cache: dict[str, _CacheEntry] = {}

    def size(self) -> int:
        return len(self._cache)

    def has(self, actor_key: str) -> bool:
        return actor_key in self._cache

    def get(
        self,
        actor_key: str,
        *,
        touch: bool = True,
        now: float | None = None,
    ) -> CachedRuntimeState | None:
        entry = self._cache.get(actor_key)
        if entry is None:
            return None
        if touch:
            entry.last_touched_at = now if now is not None else time.time()
        return entry.state

    def peek(self, actor_key: str) -> CachedRuntimeState | None:
        """Get without updating last_touched_at."""
        return self.get(actor_key, touch=False)

    def get_last_touched_at(self, actor_key: str) -> float | None:
        entry = self._cache.get(actor_key)
        return entry.last_touched_at if entry else None

    def set(
        self,
        actor_key: str,
        state: CachedRuntimeState,
        *,
        now: float | None = None,
    ) -> None:
        self._cache[actor_key] = _CacheEntry(
            state=state,
            last_touched_at=now if now is not None else time.time(),
        )

    def clear(self, actor_key: str) -> None:
        self._cache.pop(actor_key, None)

    def snapshot(self, now: float | None = None) -> list[CachedRuntimeSnapshot]:
        ts = now if now is not None else time.time()
        return [
            CachedRuntimeSnapshot(
                actor_key=key,
                state=entry.state,
                last_touched_at=entry.last_touched_at,
                idle_ms=max(0.0, (ts - entry.last_touched_at) * 1000),
            )
            for key, entry in self._cache.items()
        ]

    def collect_idle_candidates(
        self,
        max_idle_ms: float,
        now: float | None = None,
    ) -> list[CachedRuntimeSnapshot]:
        """Return entries that have been idle for at least max_idle_ms milliseconds."""
        if not (max_idle_ms > 0):
            return []
        ts = now if now is not None else time.time()
        return [s for s in self.snapshot(ts) if s.idle_ms >= max_idle_ms]
