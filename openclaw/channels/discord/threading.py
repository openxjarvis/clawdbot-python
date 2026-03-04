"""
Discord thread creation and /focus thread bindings.
Mirrors src/discord/monitor/thread-bindings.ts and src/discord/monitor/threading.ts.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thread creation helpers — mirrors threading.ts
# ---------------------------------------------------------------------------


async def create_thread_from_message(
    message: Any,
    name: str,
    auto_archive_minutes: int = 1440,  # 24h
) -> Any:
    """
    Create a public thread from an existing message.
    Mirrors createDiscordThread() in threading.ts.
    """
    try:
        thread = await message.create_thread(
            name=name[:100],  # Discord limit: 100 chars
            auto_archive_duration=auto_archive_minutes,
        )
        logger.debug("[discord][threads] Created thread '%s' (%s)", name, thread.id)
        return thread
    except Exception as exc:
        logger.warning("[discord][threads] Failed to create thread: %s", exc)
        return None


async def create_thread_in_channel(
    channel: Any,
    name: str,
    auto_archive_minutes: int = 1440,
) -> Any:
    """Create a standalone thread (without a parent message) in a text channel."""
    try:
        thread = await channel.create_thread(
            name=name[:100],
            auto_archive_duration=auto_archive_minutes,
        )
        logger.debug("[discord][threads] Created standalone thread '%s' (%s)", name, thread.id)
        return thread
    except Exception as exc:
        logger.warning("[discord][threads] Failed to create standalone thread: %s", exc)
        return None


def resolve_thread_parent(channel: Any) -> tuple[int | None, str | None]:
    """
    If the channel is a thread, return (parent_channel_id, parent_channel_name).
    Otherwise return (None, None).
    Mirrors thread parent resolution in allow-list.ts.
    """
    import discord
    if isinstance(channel, discord.Thread):
        parent = channel.parent
        if parent:
            return parent.id, getattr(parent, "name", None)
    return None, None


# ---------------------------------------------------------------------------
# Thread binding store — mirrors thread-bindings.ts
# ---------------------------------------------------------------------------

@dataclass
class _ThreadBinding:
    thread_id: str
    channel_id: str
    guild_id: str | None
    session_key: str
    created_at: float
    last_active: float
    account_id: str


class ThreadBindingStore:
    """
    Persistent JSON store for /focus thread ↔ session bindings.

    A "focus binding" ties a specific Discord thread to an agent session,
    so that messages in the thread bypass mention requirements and always
    route to the same session.

    Mirrors ThreadBindingsStore in src/discord/monitor/thread-bindings.ts.
    """

    def __init__(
        self,
        persist_dir: Path | None = None,
        account_id: str = "default",
        idle_hours: int = 24,
        max_age_hours: int = 0,
    ) -> None:
        self._idle_secs = idle_hours * 3600.0
        self._max_age_secs = max_age_hours * 3600.0 if max_age_hours > 0 else 0.0
        self._bindings: dict[str, _ThreadBinding] = {}  # thread_id -> binding
        self._path: Path | None = None
        if persist_dir:
            self._path = persist_dir / f"discord_thread_bindings_{account_id}.json"
            self._load()

    def _load(self) -> None:
        if self._path and self._path.exists():
            try:
                data = json.loads(self._path.read_text())
                for thread_id, entry in data.items():
                    self._bindings[thread_id] = _ThreadBinding(**entry)
                self._evict_expired()
            except Exception as exc:
                logger.debug("[discord][threads] Failed to load bindings: %s", exc)

    def _save(self) -> None:
        if self._path:
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                data = {tid: asdict(b) for tid, b in self._bindings.items()}
                self._path.write_text(json.dumps(data))
            except Exception as exc:
                logger.debug("[discord][threads] Failed to save bindings: %s", exc)

    def _evict_expired(self) -> None:
        now = time.time()
        to_remove = []
        for tid, b in self._bindings.items():
            if self._idle_secs > 0 and (now - b.last_active) > self._idle_secs:
                to_remove.append(tid)
            elif self._max_age_secs > 0 and (now - b.created_at) > self._max_age_secs:
                to_remove.append(tid)
        for tid in to_remove:
            del self._bindings[tid]

    def bind(
        self,
        thread_id: str,
        channel_id: str,
        session_key: str,
        guild_id: str | None = None,
        account_id: str = "default",
    ) -> None:
        now = time.time()
        self._bindings[thread_id] = _ThreadBinding(
            thread_id=thread_id,
            channel_id=channel_id,
            guild_id=guild_id,
            session_key=session_key,
            created_at=now,
            last_active=now,
            account_id=account_id,
        )
        self._save()

    def unbind(self, thread_id: str) -> bool:
        if thread_id in self._bindings:
            del self._bindings[thread_id]
            self._save()
            return True
        return False

    def get_binding(self, thread_id: str) -> _ThreadBinding | None:
        self._evict_expired()
        return self._bindings.get(thread_id)

    def touch(self, thread_id: str) -> None:
        """Update last_active timestamp for an active thread."""
        binding = self._bindings.get(thread_id)
        if binding:
            binding.last_active = time.time()
            self._save()

    def is_bound(self, thread_id: str) -> bool:
        self._evict_expired()
        return thread_id in self._bindings

    def all_bindings(self) -> list[_ThreadBinding]:
        self._evict_expired()
        return list(self._bindings.values())
