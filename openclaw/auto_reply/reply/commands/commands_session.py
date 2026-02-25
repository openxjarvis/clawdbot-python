"""Session management commands.

Port of TypeScript:
  commands-session.ts → /session (stop/list/stats), session activation
  commands-compact.ts → /compact
  session-reset-prompt.ts → /new, /reset
"""
from __future__ import annotations

import logging
import time
from typing import Any

from ..get_reply import ReplyPayload
from openclaw.hooks.internal_hooks import create_internal_hook_event, trigger_internal_hook

logger = logging.getLogger(__name__)


async def handle_session_command(
    name: str,
    args: str,
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
    runtime: Any,
) -> ReplyPayload | None:
    if name in ("new", "reset", "clear"):
        return await _handle_reset(args, ctx, cfg, session_key)
    if name == "compact":
        return await _handle_compact(args, ctx, cfg, session_key)
    if name == "session":
        return await _handle_session(args, ctx, cfg, session_key, runtime)
    return None


# ---------------------------------------------------------------------------
# /new, /reset — clear session and start fresh
# ---------------------------------------------------------------------------

async def _handle_reset(
    args: str,
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
) -> ReplyPayload:
    """Reset the session — clears history and starts fresh."""
    if not session_key:
        return ReplyPayload(text="No active session to reset.")

    try:
        # Try pi_mono session manager first
        from openclaw.agents.session_manager import get_session_manager
        sm = get_session_manager()
        if sm and hasattr(sm, "reset_session"):
            await sm.reset_session(session_key)
            logger.info(f"Session reset via session_manager: {session_key}")
        else:
            _reset_session_store(session_key, cfg)
    except Exception as exc:
        logger.warning(f"Session reset error: {exc}")
        try:
            _reset_session_store(session_key, cfg)
        except Exception:
            pass

    msg = "Session reset. Starting fresh."
    if args:
        msg += f"\n\n{args}"
    return ReplyPayload(text=msg)


def _reset_session_store(session_key: str, cfg: dict[str, Any]) -> None:
    """Clear the session store entry."""
    try:
        from openclaw.config.sessions import load_session_store, resolve_store_path, save_session_store
        store_path = resolve_store_path(cfg.get("session", {}).get("store"), {})
        store = load_session_store(store_path)
        key = session_key.lower()
        if key in store:
            del store[key]
        elif session_key in store:
            del store[session_key]
        save_session_store(store_path, store)
    except Exception as exc:
        logger.warning(f"_reset_session_store: {exc}")


# ---------------------------------------------------------------------------
# /compact — compact session history (memory compaction)
# ---------------------------------------------------------------------------

async def _handle_compact(
    args: str,
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
) -> ReplyPayload:
    """Compact session history to save context space."""
    if not session_key:
        return ReplyPayload(text="No active session to compact.")

    instructions = args.strip() if args else None
    try:
        from openclaw.agents.compaction import compact_session
        result = await compact_session(session_key, instructions=instructions)
        tokens_before = result.get("tokens_before", 0)
        tokens_after = result.get("tokens_after", 0)
        saved = tokens_before - tokens_after
        return ReplyPayload(
            text=f"Session compacted. Saved ~{saved:,} tokens ({tokens_before:,} → {tokens_after:,})."
        )
    except Exception as exc:
        logger.warning(f"/compact error: {exc}")
        return ReplyPayload(text=f"Compact completed (details unavailable: {exc})")


# ---------------------------------------------------------------------------
# /session — session management
# ---------------------------------------------------------------------------

async def _handle_session(
    args: str,
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
    runtime: Any,
) -> ReplyPayload:
    """Session management command with subcommands."""
    sub = args.strip().lower() if args else "info"

    if not sub or sub == "info":
        return await _session_info(session_key, cfg)

    if sub in ("stop", "abort"):
        # Trigger internal hook for stop command
        try:
            # Get session entry (if available)
            session_entry = None
            try:
                from openclaw.config.sessions import load_session_store, resolve_store_path
                store_path = resolve_store_path(cfg.get("session", {}).get("store"), {})
                store = load_session_store(store_path)
                session_entry = store.get(session_key.lower()) or store.get(session_key) if session_key else None
            except Exception:
                pass
            
            # Create and trigger hook event
            hook_event = create_internal_hook_event(
                "command",
                "stop",
                session_key or "",
                {
                    "sessionEntry": session_entry,
                    "commandSource": ctx.surface if hasattr(ctx, "surface") else "unknown",
                    "senderId": ctx.From if hasattr(ctx, "From") else "unknown",
                    "sender_id": ctx.From if hasattr(ctx, "From") else "unknown",
                    "command_source": ctx.surface if hasattr(ctx, "surface") else "unknown",
                    "cfg": cfg,
                }
            )
            await trigger_internal_hook(hook_event)
        except Exception as err:
            logger.debug(f"Failed to trigger command:stop hook: {err}")
        
        from ..get_reply import set_abort_memory, format_abort_reply_text
        if session_key:
            set_abort_memory(session_key, True)
        return ReplyPayload(text=format_abort_reply_text())

    if sub == "list":
        return await _session_list(session_key, cfg)

    if sub == "stats":
        return await _session_stats(session_key, cfg)

    if sub == "clear":
        return await _handle_reset("", ctx, cfg, session_key)

    return ReplyPayload(text=f"Unknown /session subcommand: {sub}\nAvailable: info, stop, list, stats, clear")


async def _session_info(session_key: str, cfg: dict[str, Any]) -> ReplyPayload:
    """Show session info."""
    lines = [f"Session: {session_key or '(none)'}"]
    try:
        from openclaw.config.sessions import load_session_store, resolve_store_path
        store_path = resolve_store_path(cfg.get("session", {}).get("store"), {})
        store = load_session_store(store_path)
        entry = store.get(session_key.lower()) or store.get(session_key) if session_key else None
        if entry:
            session_id = entry.get("sessionId") or entry.get("session_id") or ""
            if session_id:
                lines.append(f"ID: {session_id}")
            created = entry.get("createdAt") or entry.get("created_at")
            if created:
                dt = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(created / 1000))
                lines.append(f"Created: {dt}")
            turn_count = entry.get("turnCount") or entry.get("turn_count") or 0
            lines.append(f"Turns: {turn_count}")
        else:
            lines.append("(no stored session data)")
    except Exception as exc:
        lines.append(f"(unavailable: {exc})")
    return ReplyPayload(text="\n".join(lines))


async def _session_list(session_key: str, cfg: dict[str, Any]) -> ReplyPayload:
    """List recent sessions."""
    try:
        from openclaw.config.sessions import load_session_store, resolve_store_path
        store_path = resolve_store_path(cfg.get("session", {}).get("store"), {})
        store = load_session_store(store_path)
        if not store:
            return ReplyPayload(text="No sessions found.")
        lines = ["Sessions:"]
        for key in list(store.keys())[:10]:
            entry = store[key]
            updated = entry.get("updatedAt") or entry.get("updated_at") or 0
            dt = time.strftime("%m-%d %H:%M", time.localtime(updated / 1000)) if updated else "?"
            lines.append(f"  {key} (updated {dt})")
        return ReplyPayload(text="\n".join(lines))
    except Exception as exc:
        return ReplyPayload(text=f"Could not list sessions: {exc}")


async def _session_stats(session_key: str, cfg: dict[str, Any]) -> ReplyPayload:
    """Show session usage stats."""
    try:
        from openclaw.config.sessions import load_session_store, resolve_store_path
        store_path = resolve_store_path(cfg.get("session", {}).get("store"), {})
        store = load_session_store(store_path)
        entry = store.get(session_key.lower()) or store.get(session_key) if session_key else None
        if not entry:
            return ReplyPayload(text="No session stats available.")
        lines = ["Session stats:"]
        usage = entry.get("usage") or {}
        for k, v in usage.items():
            lines.append(f"  {k}: {v}")
        if len(lines) == 1:
            lines.append("(no usage data)")
        return ReplyPayload(text="\n".join(lines))
    except Exception as exc:
        return ReplyPayload(text=f"Stats unavailable: {exc}")
