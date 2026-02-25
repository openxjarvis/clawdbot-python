"""Group history tracking for context injection.

Mirrors TypeScript openclaw/src/auto-reply/reply/history.ts and
openclaw/src/web/auto-reply/monitor/group-gating.ts.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


HISTORY_CONTEXT_MARKER = "[Chat messages since your last reply - for context]"
CURRENT_MESSAGE_MARKER = "[Current message - respond to this]"
DEFAULT_GROUP_HISTORY_LIMIT = 50
MAX_HISTORY_KEYS = 1000


@dataclass
class GroupHistoryEntry:
    """Group history entry for messages that didn't trigger processing.
    
    Mirrors TS GroupHistoryEntry from group-gating.ts and HistoryEntry from history.ts.
    """
    sender: str
    body: str
    timestamp: int | None = None
    id: str | None = None
    senderJid: str | None = None
    messageId: str | None = None


# Global in-memory storage for group histories
# In production, this should be persisted or use a proper cache
_group_histories: dict[str, list[GroupHistoryEntry]] = {}


def _evict_old_history_keys(
    history_map: dict[str, list[GroupHistoryEntry]],
    max_keys: int = MAX_HISTORY_KEYS,
) -> None:
    """Evict oldest keys from history map when it exceeds max_keys.
    
    Mirrors TS evictOldHistoryKeys().
    Uses dict insertion order for LRU-like behavior (Python 3.7+).
    """
    if len(history_map) <= max_keys:
        return
    
    keys_to_delete = len(history_map) - max_keys
    keys = list(history_map.keys())
    
    for i in range(keys_to_delete):
        if i < len(keys):
            del history_map[keys[i]]


def record_pending_group_history_entry(
    session_key: str,
    entry: GroupHistoryEntry,
    limit: int = DEFAULT_GROUP_HISTORY_LIMIT,
    history_map: dict[str, list[GroupHistoryEntry]] | None = None,
) -> list[GroupHistoryEntry]:
    """Record a group history entry for messages that didn't trigger processing.
    
    Mirrors TS recordPendingHistoryEntry() and appendHistoryEntry().
    
    Args:
        session_key: Session key for the group
        entry: History entry to record
        limit: Maximum number of entries to keep
        history_map: Optional custom history map (uses global if None)
        
    Returns:
        Updated history list for the session
    """
    if limit <= 0:
        return []
    
    if history_map is None:
        history_map = _group_histories
    
    history = history_map.get(session_key, [])
    history.append(entry)
    
    # Trim to limit
    while len(history) > limit:
        history.pop(0)
    
    # Refresh insertion order for LRU eviction
    if session_key in history_map:
        del history_map[session_key]
    
    history_map[session_key] = history
    
    # Evict oldest keys if map exceeds max size
    _evict_old_history_keys(history_map)
    
    return history


def get_group_history(
    session_key: str,
    limit: int = DEFAULT_GROUP_HISTORY_LIMIT,
    history_map: dict[str, list[GroupHistoryEntry]] | None = None,
) -> list[GroupHistoryEntry]:
    """Get group history entries for a session.
    
    Mirrors TS historyMap.get(historyKey).
    
    Args:
        session_key: Session key for the group
        limit: Maximum number of entries to return
        history_map: Optional custom history map (uses global if None)
        
    Returns:
        List of history entries (empty if none)
    """
    if limit <= 0:
        return []
    
    if history_map is None:
        history_map = _group_histories
    
    entries = history_map.get(session_key, [])
    return entries[-limit:] if limit > 0 else entries


def clear_group_history(
    session_key: str,
    history_map: dict[str, list[GroupHistoryEntry]] | None = None,
) -> None:
    """Clear group history for a session.
    
    Mirrors TS clearHistoryEntries().
    
    Args:
        session_key: Session key for the group
        history_map: Optional custom history map (uses global if None)
    """
    if history_map is None:
        history_map = _group_histories
    
    history_map[session_key] = []


def format_group_history_context(
    entries: list[GroupHistoryEntry],
    current_message: str,
    format_entry: Callable[[GroupHistoryEntry], str] | None = None,
    line_break: str = "\n",
    exclude_last: bool = False,
) -> str:
    """Format group history entries into context string.
    
    Mirrors TS buildHistoryContextFromEntries().
    
    Args:
        entries: History entries to format
        current_message: Current message text
        format_entry: Optional custom formatter (default: "sender: body")
        line_break: Line break character (default: newline)
        exclude_last: Whether to exclude the last entry
        
    Returns:
        Formatted context string with history and current message
    """
    if format_entry is None:
        format_entry = lambda e: f"{e.sender}: {e.body}"
    
    entries_to_format = entries[:-1] if exclude_last and entries else entries
    
    if not entries_to_format:
        return current_message
    
    history_text = line_break.join(format_entry(e) for e in entries_to_format)
    
    # Build context with markers
    return line_break.join([
        HISTORY_CONTEXT_MARKER,
        history_text,
        "",
        CURRENT_MESSAGE_MARKER,
        current_message,
    ])


def build_group_history_context(
    current_message: str,
    limit: int = DEFAULT_GROUP_HISTORY_LIMIT,
    format_entry: Callable[[GroupHistoryEntry], str] | None = None,
    line_break: str = "\n",
    exclude_last: bool = False,
    history_map: dict[str, list[GroupHistoryEntry]] | None = None,
    history_key: str | None = None,
    session_key: str | None = None,
    entries: list[GroupHistoryEntry] | None = None,
) -> str:
    """Build group history context from stored entries.

    Mirrors TS buildPendingHistoryContextFromMap().

    Args:
        current_message: Current message text
        limit: Maximum number of entries to include
        format_entry: Optional custom formatter
        line_break: Line break character
        exclude_last: Whether to exclude the last entry
        history_map: Optional custom history map (uses global if None)
        history_key: Session/history key (alias for session_key)
        session_key: Session key for the group
        entries: Optional new entries to add to history before building context

    Returns:
        Formatted context string with history and current message
    """
    key = history_key or session_key or ""

    # Add new entries to history map if provided
    if entries and key and history_map is not None:
        for entry in entries:
            record_pending_group_history_entry(key, entry, history_map=history_map)

    if limit <= 0:
        return current_message

    stored = get_group_history(key, limit, history_map) if key else []

    return format_group_history_context(
        stored,
        current_message,
        format_entry,
        line_break,
        exclude_last,
    )


__all__ = [
    "GroupHistoryEntry",
    "HISTORY_CONTEXT_MARKER",
    "CURRENT_MESSAGE_MARKER",
    "DEFAULT_GROUP_HISTORY_LIMIT",
    "MAX_HISTORY_KEYS",
    "record_pending_group_history_entry",
    "get_group_history",
    "clear_group_history",
    "format_group_history_context",
    "build_group_history_context",
]
