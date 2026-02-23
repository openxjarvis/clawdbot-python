"""Configuration commands.

Port of TypeScript:
  commands-config.ts     → /config
  commands-setunset.ts   → set, unset
  commands-system-prompt.ts → /system-prompt
  config-commands.ts     → config helpers
"""
from __future__ import annotations

import json
import logging
from typing import Any

from ..get_reply import ReplyPayload

logger = logging.getLogger(__name__)


async def handle_config_command(
    name: str,
    args: str,
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
    runtime: Any,
) -> ReplyPayload | None:
    if name == "config":
        return await _handle_config(args, ctx, cfg, session_key)
    if name == "set":
        return await _handle_set(args, ctx, cfg, session_key)
    if name == "unset":
        return await _handle_unset(args, ctx, cfg, session_key)
    if name == "system-prompt":
        return await _handle_system_prompt(args, ctx, cfg, session_key)
    return None


# ---------------------------------------------------------------------------
# /config [key] [value]
# ---------------------------------------------------------------------------

async def _handle_config(
    args: str,
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
) -> ReplyPayload:
    """View or update config values."""
    parts = args.strip().split(None, 1) if args else []

    if not parts:
        # Show safe subset of current config
        safe_cfg: dict[str, Any] = {}
        for k, v in cfg.items():
            if k.lower() in ("apikey", "api_key", "token", "secret"):
                safe_cfg[k] = "***"
            elif isinstance(v, dict):
                safe_cfg[k] = {
                    kk: "***" if kk.lower() in ("apikey", "api_key", "token", "secret") else vv
                    for kk, vv in v.items()
                }
            else:
                safe_cfg[k] = v
        return ReplyPayload(text=f"Config:\n```json\n{json.dumps(safe_cfg, indent=2, default=str)}\n```")

    if len(parts) == 1:
        # Show single key
        key = parts[0]
        val = _get_nested(cfg, key)
        if val is None:
            return ReplyPayload(text=f"Config key not found: {key}")
        return ReplyPayload(text=f"{key}: {json.dumps(val, default=str)}")

    # Set key = value
    key, value_str = parts
    try:
        try:
            value = json.loads(value_str)
        except json.JSONDecodeError:
            value = value_str
        _set_nested(cfg, key, value)
        return ReplyPayload(text=f"Config updated: {key} = {json.dumps(value, default=str)}")
    except Exception as exc:
        return ReplyPayload(text=f"Could not update config: {exc}")


# ---------------------------------------------------------------------------
# set <key> <value>
# ---------------------------------------------------------------------------

async def _handle_set(
    args: str,
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
) -> ReplyPayload:
    """Set a session or config value."""
    parts = args.strip().split(None, 1) if args else []
    if len(parts) < 2:
        return ReplyPayload(text="Usage: /set <key> <value>")

    key, value_str = parts
    try:
        try:
            value = json.loads(value_str)
        except json.JSONDecodeError:
            value = value_str
        _update_session_field(session_key, cfg, key, value)
        return ReplyPayload(text=f"Set {key} = {json.dumps(value, default=str)}")
    except Exception as exc:
        return ReplyPayload(text=f"Could not set {key}: {exc}")


# ---------------------------------------------------------------------------
# unset <key>
# ---------------------------------------------------------------------------

async def _handle_unset(
    args: str,
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
) -> ReplyPayload:
    """Unset (remove) a session value."""
    key = args.strip()
    if not key:
        return ReplyPayload(text="Usage: /unset <key>")
    try:
        _unset_session_field(session_key, cfg, key)
        return ReplyPayload(text=f"Unset {key}")
    except Exception as exc:
        return ReplyPayload(text=f"Could not unset {key}: {exc}")


# ---------------------------------------------------------------------------
# /system-prompt [new prompt text]
# ---------------------------------------------------------------------------

async def _handle_system_prompt(
    args: str,
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
) -> ReplyPayload:
    """View or set the system prompt."""
    if not args.strip():
        # Show current
        system_prompt = (
            cfg.get("system_prompt")
            or cfg.get("agents", {}).get("defaults", {}).get("systemPrompt")
            or ""
        )
        # Also check session entry
        entry = _load_session_entry(session_key, cfg)
        if entry and entry.get("systemPrompt"):
            system_prompt = entry["systemPrompt"]

        if not system_prompt:
            return ReplyPayload(text="No system prompt configured.")
        preview = system_prompt[:500] + ("..." if len(system_prompt) > 500 else "")
        return ReplyPayload(text=f"System prompt:\n```\n{preview}\n```")

    # Set new system prompt
    new_prompt = args.strip()
    try:
        _update_session_field(session_key, cfg, "systemPrompt", new_prompt)
        preview = new_prompt[:200] + ("..." if len(new_prompt) > 200 else "")
        return ReplyPayload(text=f"System prompt updated:\n```\n{preview}\n```")
    except Exception as exc:
        return ReplyPayload(text=f"Could not set system prompt: {exc}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_nested(obj: dict, key: str) -> Any:
    """Get a value from a nested dict using dot notation."""
    parts = key.split(".")
    current = obj
    for part in parts:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
        if current is None:
            return None
    return current


def _set_nested(obj: dict, key: str, value: Any) -> None:
    """Set a value in a nested dict using dot notation."""
    parts = key.split(".")
    current = obj
    for part in parts[:-1]:
        if part not in current:
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


def _load_session_entry(session_key: str, cfg: dict[str, Any]) -> dict | None:
    if not session_key:
        return None
    try:
        from openclaw.config.sessions import load_session_store, resolve_store_path
        store_path = resolve_store_path(cfg.get("session", {}).get("store"), {})
        store = load_session_store(store_path)
        return store.get(session_key.lower()) or store.get(session_key)
    except Exception:
        return None


def _update_session_field(session_key: str, cfg: dict[str, Any], field: str, value: Any) -> None:
    try:
        from openclaw.config.sessions import load_session_store, resolve_store_path, save_session_store
        import time as _time
        store_path = resolve_store_path(cfg.get("session", {}).get("store"), {})
        store = load_session_store(store_path)
        key = session_key.lower() if session_key else ""
        entry = (store.get(key) if key else None) or {}
        entry[field] = value
        entry["updatedAt"] = int(_time.time() * 1000)
        if key:
            store[key] = entry
        save_session_store(store_path, store)
    except Exception as exc:
        raise RuntimeError(f"Could not persist {field}: {exc}") from exc


def _unset_session_field(session_key: str, cfg: dict[str, Any], field: str) -> None:
    try:
        from openclaw.config.sessions import load_session_store, resolve_store_path, save_session_store
        import time as _time
        store_path = resolve_store_path(cfg.get("session", {}).get("store"), {})
        store = load_session_store(store_path)
        key = session_key.lower() if session_key else ""
        entry = (store.get(key) if key else None) or {}
        entry.pop(field, None)
        entry["updatedAt"] = int(_time.time() * 1000)
        if key:
            store[key] = entry
        save_session_store(store_path, store)
    except Exception as exc:
        raise RuntimeError(f"Could not unset {field}: {exc}") from exc
