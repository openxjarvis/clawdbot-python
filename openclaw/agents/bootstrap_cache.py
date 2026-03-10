"""
Bootstrap cache invalidation — mirrors TS clearBootstrapSnapshot / bootstrap-cache.ts.

When a session is reset (/new, /reset), mark_bootstrap_stale(session_key) is called so
that channel_manager rebuilds the system prompt from disk on the next turn (re-reading
SOUL.md, USER.md, MEMORY.md, AGENTS.md, etc.) instead of serving the cached prompt.
"""

from __future__ import annotations

import threading
from typing import Set

_lock = threading.Lock()
_stale_keys: Set[str] = set()


def mark_bootstrap_stale(session_key: str) -> None:
    """Mark a session key as needing fresh bootstrap file reads on next run."""
    with _lock:
        _stale_keys.add(session_key)


def consume_bootstrap_stale(session_key: str) -> bool:
    """Check and clear the stale flag for a session key.

    Returns True if the key was stale (caller should rebuild system prompt from disk).
    Clears the flag atomically so only the first turn after reset triggers a rebuild.
    """
    with _lock:
        if session_key in _stale_keys:
            _stale_keys.discard(session_key)
            return True
    return False


def is_bootstrap_stale(session_key: str) -> bool:
    """Non-consuming check — returns True if the key is stale."""
    with _lock:
        return session_key in _stale_keys


def clear_all_bootstrap_stale() -> None:
    """Clear all stale flags (used in tests / full gateway restart)."""
    with _lock:
        _stale_keys.clear()
