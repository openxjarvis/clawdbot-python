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
    if name == "stop":
        return await _handle_stop(ctx, cfg, session_key)
    if name == "restart":
        return await _handle_restart(cfg)
    if name == "activation":
        return await _handle_activation(args, ctx, cfg, session_key)
    if name == "send":
        return await _handle_send_policy(args, ctx, cfg, session_key)
    if name == "queue":
        return await _handle_queue(args, ctx, cfg, session_key)
    if name in ("kill",):
        return await _handle_kill(args, ctx, cfg, session_key)
    if name in ("steer", "tell"):
        return await _handle_steer(args, ctx, cfg, session_key)
    if name in ("dock-telegram", "dock_telegram"):
        return await _handle_dock(args, ctx, cfg, session_key, channel="telegram")
    if name in ("dock-discord", "dock_discord"):
        return await _handle_dock(args, ctx, cfg, session_key, channel="discord")
    if name in ("dock-slack", "dock_slack"):
        return await _handle_dock(args, ctx, cfg, session_key, channel="slack")
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


# ---------------------------------------------------------------------------
# /stop — abort the current agent run for this session
# Mirrors TS handleStopCommand() in commands-stop.ts
# ---------------------------------------------------------------------------

async def _handle_stop(
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
) -> ReplyPayload:
    """Abort the active run for the current session."""
    try:
        from ..get_reply import set_abort_memory, format_abort_reply_text
        if session_key:
            set_abort_memory(session_key, True)
        return ReplyPayload(text=format_abort_reply_text())
    except Exception as exc:
        logger.warning(f"/stop error: {exc}")
        return ReplyPayload(text="Stopping current operation…")


# ---------------------------------------------------------------------------
# /restart — restart the gateway process
# Requires commands.restart: true (disabled by default, mirrors TS).
# ---------------------------------------------------------------------------

async def _handle_restart(cfg: dict[str, Any]) -> ReplyPayload:
    """Restart the gateway. Requires commands.restart: true in config."""
    if not (cfg.get("commands") or {}).get("restart", False):
        return ReplyPayload(text="Restart is disabled. Set commands.restart: true to enable.")
    try:
        import os
        import sys
        logger.info("Restarting gateway via /restart command")
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as exc:
        return ReplyPayload(text=f"Restart failed: {exc}")
    return ReplyPayload(text="Restarting…")


# ---------------------------------------------------------------------------
# /activation mention|always — group activation mode
# Mirrors TS handleActivationCommand()
# ---------------------------------------------------------------------------

async def _handle_activation(
    args: str,
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
) -> ReplyPayload:
    """Set group activation mode: mention or always."""
    mode = args.strip().lower()
    if mode not in ("mention", "always"):
        return ReplyPayload(text="Usage: /activation mention|always")

    try:
        from openclaw.agents.sessions import patch_session_entry
        patch_session_entry(session_key, {"groupActivation": mode}, cfg)
        return ReplyPayload(text=f"Group activation set to: {mode}")
    except Exception as exc:
        logger.warning(f"/activation error: {exc}")
        return ReplyPayload(text=f"Activation: {mode} (setting may not persist — {exc})")


# ---------------------------------------------------------------------------
# /send on|off|inherit — session-level send policy
# Mirrors TS handleSendCommand()
# ---------------------------------------------------------------------------

async def _handle_send_policy(
    args: str,
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
) -> ReplyPayload:
    """Set or show the send policy for this session."""
    mode = args.strip().lower()
    if not mode:
        # Show current
        try:
            from openclaw.agents.sessions import load_session_entry
            entry = load_session_entry(session_key, cfg)
            policy = (entry or {}).get("sendPolicy") or "inherit"
            return ReplyPayload(text=f"Send policy: {policy}")
        except Exception:
            return ReplyPayload(text="Send policy: inherit")

    if mode not in ("on", "off", "allow", "deny", "inherit"):
        return ReplyPayload(text="Usage: /send on|off|inherit")

    # Normalize: on→allow, off→deny
    normalized = {"on": "allow", "off": "deny", "inherit": None}.get(mode, mode)
    try:
        from openclaw.agents.sessions import patch_session_entry
        patch_session_entry(session_key, {"sendPolicy": normalized}, cfg)
        label = {"allow": "on", "deny": "off", None: "inherit"}.get(normalized, str(normalized))
        return ReplyPayload(text=f"Send policy set to: {label}")
    except Exception as exc:
        logger.warning(f"/send error: {exc}")
        return ReplyPayload(text=f"Send policy update failed: {exc}")


# ---------------------------------------------------------------------------
# /queue <mode> — set message queue mode
# Mirrors TS handleQueueCommand()
# ---------------------------------------------------------------------------

async def _handle_queue(
    args: str,
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
) -> ReplyPayload:
    """Show or set the message queue mode for this session."""
    parts = args.strip().split() if args.strip() else []

    if not parts:
        # Show current mode
        try:
            from openclaw.agents.sessions import load_session_entry
            entry = load_session_entry(session_key, cfg)
            mode = (entry or {}).get("queueMode") or (cfg.get("messages") or {}).get("queue", {}).get("mode", "steer")
            return ReplyPayload(text=f"Queue mode: {mode}")
        except Exception:
            return ReplyPayload(text="Queue mode: steer (default)")

    mode = parts[0].lower()
    valid_modes = ("interrupt", "steer", "followup", "collect", "backlog", "backlog-steer", "backlog-followup", "backlog-collect")
    if mode not in valid_modes:
        return ReplyPayload(text=f"Usage: /queue <mode>\nModes: {', '.join(valid_modes)}")

    try:
        from openclaw.agents.sessions import patch_session_entry
        patch_session_entry(session_key, {"queueMode": mode}, cfg)
        return ReplyPayload(text=f"Queue mode set to: {mode}")
    except Exception as exc:
        logger.warning(f"/queue error: {exc}")
        return ReplyPayload(text=f"Queue mode: {mode} (setting may not persist — {exc})")


# ---------------------------------------------------------------------------
# /kill <id|#|all> — kill sub-agent runs
# Mirrors TS handleKillCommand()
# ---------------------------------------------------------------------------

async def _handle_kill(
    args: str,
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
) -> ReplyPayload:
    """Immediately abort one or all running sub-agents for this session."""
    target = args.strip().lower()
    if not target:
        return ReplyPayload(text="Usage: /kill <id|#|all>")

    try:
        from openclaw.agents.subagent_registry import list_subagent_runs_for_requester, abort_subagent_run
        from openclaw.routing.session_key import normalize_main_key
        requester = normalize_main_key(session_key) if session_key else session_key
        runs = list_subagent_runs_for_requester(requester)
        active = [r for r in runs if not r.get("ended_at")]

        if target == "all":
            count = 0
            for run in active:
                run_id = run.get("run_id") or run.get("child_session_key")
                if run_id:
                    abort_subagent_run(run_id)
                    count += 1
            return ReplyPayload(text=f"Killed {count} sub-agent(s).")

        # Match by index (#N) or run id
        matched = None
        if target.startswith("#"):
            try:
                idx = int(target[1:]) - 1
                if 0 <= idx < len(active):
                    matched = active[idx]
            except ValueError:
                pass
        else:
            matched = next((r for r in active if (r.get("run_id") or "") == target), None)

        if not matched:
            return ReplyPayload(text=f"No active sub-agent matching: {target}")
        run_id = matched.get("run_id") or matched.get("child_session_key")
        abort_subagent_run(run_id)
        return ReplyPayload(text=f"Killed sub-agent: {target}")

    except Exception as exc:
        logger.warning(f"/kill error: {exc}")
        return ReplyPayload(text=f"Kill failed: {exc}")


# ---------------------------------------------------------------------------
# /steer <id|#> <message> / /tell <id|#> <message>
# Mirrors TS handleSteerCommand()
# ---------------------------------------------------------------------------

async def _handle_steer(
    args: str,
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
) -> ReplyPayload:
    """Steer a running sub-agent with a new message."""
    parts = args.strip().split(None, 1)
    if len(parts) < 2:
        return ReplyPayload(text="Usage: /steer <id|#> <message>")

    target, message = parts[0], parts[1]
    try:
        from openclaw.agents.subagent_registry import list_subagent_runs_for_requester, steer_subagent_run
        from openclaw.routing.session_key import normalize_main_key
        requester = normalize_main_key(session_key) if session_key else session_key
        runs = list_subagent_runs_for_requester(requester)
        active = [r for r in runs if not r.get("ended_at")]

        matched = None
        if target.startswith("#"):
            try:
                idx = int(target[1:]) - 1
                if 0 <= idx < len(active):
                    matched = active[idx]
            except ValueError:
                pass
        else:
            matched = next((r for r in active if (r.get("run_id") or "") == target), None)

        if not matched:
            return ReplyPayload(text=f"No active sub-agent matching: {target}")
        run_id = matched.get("run_id") or matched.get("child_session_key")
        steer_subagent_run(run_id, message)
        return ReplyPayload(text=f"Steered sub-agent {target}.")
    except Exception as exc:
        logger.warning(f"/steer error: {exc}")
        return ReplyPayload(text=f"Steer failed: {exc}")


# ---------------------------------------------------------------------------
# /dock-telegram / /dock-discord / /dock-slack
# Mirrors TS handleDockCommand() — switch reply surface
# ---------------------------------------------------------------------------

async def _handle_dock(
    args: str,
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
    channel: str = "",
) -> ReplyPayload:
    """Switch the reply surface to another channel."""
    try:
        from openclaw.agents.sessions import patch_session_entry
        patch_session_entry(session_key, {"dockedChannel": channel}, cfg)
        return ReplyPayload(text=f"Docked to {channel}.")
    except Exception as exc:
        logger.warning(f"/dock error: {exc}")
        return ReplyPayload(text=f"Dock to {channel} failed: {exc}")
