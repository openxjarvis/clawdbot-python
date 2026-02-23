"""In-memory system event queue — mirrors TypeScript src/infra/system-events.ts

Events are lightweight, session-scoped, and ephemeral (never persisted).
The cron service enqueues events here, and the heartbeat runner drains them
when running an agent turn.
"""
from __future__ import annotations

import threading
import time
from typing import TypedDict

MAX_EVENTS = 20


class SystemEvent(TypedDict):
    text: str
    ts: int
    contextKey: str | None


class _SessionQueue:
    __slots__ = ("queue", "last_text", "last_context_key")

    def __init__(self) -> None:
        self.queue: list[SystemEvent] = []
        self.last_text: str | None = None
        self.last_context_key: str | None = None


_queues: dict[str, _SessionQueue] = {}
_lock = threading.Lock()


def _require_session_key(key: str | None) -> str:
    trimmed = (key or "").strip()
    if not trimmed:
        raise ValueError("system events require a non-empty sessionKey")
    return trimmed


def _normalize_context_key(key: str | None) -> str | None:
    if not key:
        return None
    trimmed = key.strip()
    return trimmed.lower() if trimmed else None


def enqueue_system_event(
    text: str,
    session_key: str,
    context_key: str | None = None,
) -> None:
    key = _require_session_key(session_key)
    cleaned = text.strip()
    if not cleaned:
        return

    normalized_ctx = _normalize_context_key(context_key)

    with _lock:
        entry = _queues.get(key)
        if entry is None:
            entry = _SessionQueue()
            _queues[key] = entry

        entry.last_context_key = normalized_ctx

        # Skip consecutive duplicates (same text)
        if entry.last_text == cleaned:
            return
        entry.last_text = cleaned

        entry.queue.append(
            SystemEvent(
                text=cleaned,
                ts=int(time.time() * 1000),
                contextKey=normalized_ctx,
            )
        )
        if len(entry.queue) > MAX_EVENTS:
            entry.queue.pop(0)


def drain_system_event_entries(session_key: str) -> list[SystemEvent]:
    key = _require_session_key(session_key)
    with _lock:
        entry = _queues.get(key)
        if not entry or not entry.queue:
            return []
        out = entry.queue[:]
        entry.queue.clear()
        entry.last_text = None
        entry.last_context_key = None
        del _queues[key]
        return out


def drain_system_events(session_key: str) -> list[str]:
    return [e["text"] for e in drain_system_event_entries(session_key)]


def peek_system_event_entries(session_key: str) -> list[SystemEvent]:
    key = _require_session_key(session_key)
    with _lock:
        entry = _queues.get(key)
        if not entry:
            return []
        return entry.queue[:]


def peek_system_events(session_key: str) -> list[str]:
    return [e["text"] for e in peek_system_event_entries(session_key)]


def has_system_events(session_key: str) -> bool:
    key = _require_session_key(session_key)
    with _lock:
        entry = _queues.get(key)
        return bool(entry and entry.queue)


def is_system_event_context_changed(
    session_key: str,
    context_key: str | None = None,
) -> bool:
    key = _require_session_key(session_key)
    normalized = _normalize_context_key(context_key)
    with _lock:
        entry = _queues.get(key)
        return normalized != (entry.last_context_key if entry else None)


def reset_for_test() -> None:
    with _lock:
        _queues.clear()
