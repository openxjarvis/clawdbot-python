"""ACP session meta disk persistence — mirrors src/acp/runtime/session-meta.ts

Provides helpers to read and write SessionAcpMeta for a session key from the
on-disk sessions.json store.
"""
from __future__ import annotations

import json
import os
from typing import Any, Callable


SessionAcpMeta = dict[str, Any]
SessionEntry = dict[str, Any]


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def _resolve_sessions_json_path(
    session_key: str,
    state_dir: str | None = None,
) -> str:
    """Return the path to sessions.json for the given session key."""
    base = state_dir or os.environ.get("OPENCLAW_STATE_DIR") or os.path.expanduser("~/.openclaw")
    return os.path.join(base, "sessions", "sessions.json")


# ---------------------------------------------------------------------------
# Store helpers
# ---------------------------------------------------------------------------

def _load_sessions_store(store_path: str) -> dict[str, SessionEntry]:
    try:
        with open(store_path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_sessions_store(store_path: str, store: dict[str, SessionEntry]) -> None:
    os.makedirs(os.path.dirname(store_path), exist_ok=True)
    tmp = store_path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(store, fh, indent=2)
        os.replace(tmp, store_path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def _resolve_store_session_key(
    store: dict[str, SessionEntry],
    session_key: str,
) -> str:
    normalized = session_key.strip()
    if not normalized:
        return ""
    if normalized in store:
        return normalized
    lower = normalized.lower()
    if lower in store:
        return lower
    for key in store:
        if key.lower() == lower:
            return key
    return lower


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def read_acp_session_entry(
    session_key: str,
    state_dir: str | None = None,
) -> dict[str, Any] | None:
    """
    Read the sessions.json entry (including acp meta) for session_key.

    Returns None if not found or the file cannot be read.
    """
    key = session_key.strip()
    if not key:
        return None
    store_path = _resolve_sessions_json_path(key, state_dir)
    store = _load_sessions_store(store_path)
    store_key = _resolve_store_session_key(store, key)
    entry = store.get(store_key)
    if not entry:
        return None
    return {
        "storePath": store_path,
        "sessionKey": key,
        "storeSessionKey": store_key,
        "entry": entry,
        "acp": entry.get("acp"),
    }


async def list_acp_session_entries(
    state_dir: str | None = None,
) -> list[dict[str, Any]]:
    """
    List all sessions.json entries that have ACP meta.

    Searches the default sessions store path.
    """
    store_path = _resolve_sessions_json_path("", state_dir)
    store = _load_sessions_store(store_path)
    entries = []
    for session_key, entry in store.items():
        if not isinstance(entry, dict):
            continue
        if not entry.get("acp"):
            continue
        entries.append({
            "storePath": store_path,
            "sessionKey": session_key,
            "storeSessionKey": session_key,
            "entry": entry,
            "acp": entry.get("acp"),
        })
    return entries


async def upsert_acp_session_meta(
    session_key: str,
    mutate: Callable[[SessionAcpMeta | None, SessionEntry | None], SessionAcpMeta | None],
    state_dir: str | None = None,
) -> SessionEntry | None:
    """
    Read, mutate, and write back the ACP meta for session_key.

    The mutate callback receives (current_acp_meta, current_entry) and should
    return:
      - a new/updated SessionAcpMeta dict to save
      - None to remove the acp key from the entry
      - the unchanged current_acp_meta to make no change

    Returns the updated SessionEntry, or None if no change was made.
    """
    key = session_key.strip()
    if not key:
        return None
    store_path = _resolve_sessions_json_path(key, state_dir)
    store = _load_sessions_store(store_path)
    store_key = _resolve_store_session_key(store, key)
    current_entry: SessionEntry | None = store.get(store_key)

    next_meta = mutate(
        current_entry.get("acp") if current_entry else None,
        current_entry,
    )
    if next_meta is None and not current_entry:
        return None

    next_entry: SessionEntry = dict(current_entry or {})
    if next_meta is None:
        next_entry.pop("acp", None)
    else:
        next_entry["acp"] = next_meta

    store[store_key] = next_entry
    _save_sessions_store(store_path, store)
    return next_entry
