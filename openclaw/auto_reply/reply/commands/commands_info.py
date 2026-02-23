"""Info / status commands.

Port of TypeScript:
  commands-info.ts   → /help, /commands, /whoami
  commands-status.ts → /status
  commands-context-report.ts → /context, /context-report
  commands-export-session.ts → /export-session, /export
"""
from __future__ import annotations

import logging
import platform
import sys
import time
from typing import Any

from ..get_reply import ReplyPayload

logger = logging.getLogger(__name__)


async def handle_info_command(
    name: str,
    args: str,
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
    runtime: Any,
) -> ReplyPayload | None:
    if name == "help":
        return await _handle_help(ctx, cfg)
    if name in ("commands",):
        return await _handle_commands_list(ctx, cfg)
    if name == "status":
        return await _handle_status(ctx, cfg, session_key, runtime)
    if name in ("context", "context-report"):
        return await _handle_context(ctx, cfg, session_key)
    if name == "whoami":
        return await _handle_whoami(ctx, cfg)
    if name in ("export-session", "export"):
        return await _handle_export_session(ctx, cfg, session_key)
    if name == "debug":
        return await _handle_debug(ctx, cfg, session_key)
    return None


# ---------------------------------------------------------------------------
# /help
# ---------------------------------------------------------------------------

async def _handle_help(ctx: Any, cfg: dict[str, Any]) -> ReplyPayload:
    lines = [
        "Available commands:",
        "",
        "  /help         Show this message",
        "  /commands     List all commands",
        "  /status       Show session status",
        "  /context      Show context info",
        "  /whoami       Show your identity",
        "",
        "  /new          Start a new session",
        "  /reset        Reset current session",
        "  /compact      Compact session history",
        "  /session      Session management",
        "",
        "  /model        Set AI model",
        "  /models       List available models",
        "  /think        Set thinking level",
        "  /verbose      Toggle verbose mode",
        "",
        "  /config       View/edit configuration",
        "  /system-prompt  View/set system prompt",
        "",
        "  /bash         Run a bash command",
        "  /subagents    List running sub-agents",
        "  /allowlist    Manage allowed senders",
        "  /tts          Toggle text-to-speech",
        "",
        "  stop / /stop  Abort current operation",
    ]
    return ReplyPayload(text="\n".join(lines))


# ---------------------------------------------------------------------------
# /commands
# ---------------------------------------------------------------------------

async def _handle_commands_list(ctx: Any, cfg: dict[str, Any]) -> ReplyPayload:
    try:
        from openclaw.auto_reply.commands_registry_data import get_builtin_commands
        cmds = get_builtin_commands()
        lines = ["Commands:"]
        for cmd in cmds:
            name_part = cmd.name
            aliases = getattr(cmd, "aliases", [])
            if aliases:
                name_part += f" ({', '.join(aliases)})"
            desc = getattr(cmd, "description", "")
            lines.append(f"  /{name_part}  — {desc}")
        return ReplyPayload(text="\n".join(lines))
    except Exception:
        return await _handle_help(ctx, cfg)


# ---------------------------------------------------------------------------
# /status
# ---------------------------------------------------------------------------

async def _handle_status(
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
    runtime: Any,
) -> ReplyPayload:
    lines: list[str] = []

    # Basic identity
    agent_id = _resolve_agent_id(session_key, cfg)
    lines.append(f"Session: {session_key or '(none)'}")
    if agent_id:
        lines.append(f"Agent: {agent_id}")

    # Model info
    provider, model = _resolve_model(cfg, runtime)
    lines.append(f"Model: {provider}/{model}")

    # Session entry info
    try:
        entry = _load_session_entry(session_key, cfg)
        if entry:
            if entry.get("ttsAuto"):
                lines.append(f"TTS: {entry['ttsAuto']}")
            if entry.get("model") or entry.get("provider"):
                m = entry.get("model") or model
                p = entry.get("provider") or provider
                lines.append(f"Session model: {p}/{m}")
    except Exception:
        pass

    # System info
    lines.append(f"Python: {sys.version.split()[0]}")

    # Uptime (if available)
    try:
        from openclaw.gateway.uptime import get_uptime_seconds
        uptime = get_uptime_seconds()
        lines.append(f"Uptime: {_format_duration(uptime)}")
    except Exception:
        pass

    return ReplyPayload(text="\n".join(lines))


# ---------------------------------------------------------------------------
# /context
# ---------------------------------------------------------------------------

async def _handle_context(ctx: Any, cfg: dict[str, Any], session_key: str) -> ReplyPayload:
    lines: list[str] = [f"Context for session: {session_key or '(none)'}"]
    try:
        entry = _load_session_entry(session_key, cfg)
        if entry:
            turn_count = entry.get("turnCount") or entry.get("turn_count") or 0
            lines.append(f"Turns: {turn_count}")
            created = entry.get("createdAt") or entry.get("created_at")
            if created:
                dt = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(created / 1000))
                lines.append(f"Started: {dt}")
            updated = entry.get("updatedAt") or entry.get("updated_at")
            if updated:
                dt = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(updated / 1000))
                lines.append(f"Last active: {dt}")
    except Exception as exc:
        lines.append(f"(context unavailable: {exc})")
    return ReplyPayload(text="\n".join(lines))


# ---------------------------------------------------------------------------
# /whoami
# ---------------------------------------------------------------------------

async def _handle_whoami(ctx: Any, cfg: dict[str, Any]) -> ReplyPayload:
    lines = ["Identity:"]
    channel = str(
        getattr(ctx, "Surface", None) or getattr(ctx, "Provider", None) or "unknown"
    ).lower()
    lines.append(f"Channel: {channel}")
    sender_id = getattr(ctx, "SenderId", None) or getattr(ctx, "From", None) or ""
    if sender_id:
        lines.append(f"User id: {sender_id}")
    sender_username = getattr(ctx, "SenderUsername", None)
    if sender_username:
        handle = sender_username if sender_username.startswith("@") else f"@{sender_username}"
        lines.append(f"Username: {handle}")
    chat_type = getattr(ctx, "ChatType", None) or ""
    if chat_type == "group":
        chat_from = getattr(ctx, "From", None) or ""
        if chat_from:
            lines.append(f"Chat: {chat_from}")
    thread_id = getattr(ctx, "MessageThreadId", None)
    if thread_id is not None:
        lines.append(f"Thread: {thread_id}")
    if sender_id:
        lines.append(f"AllowFrom: {sender_id}")
    return ReplyPayload(text="\n".join(lines))


# ---------------------------------------------------------------------------
# /export-session
# ---------------------------------------------------------------------------

async def _handle_export_session(
    ctx: Any, cfg: dict[str, Any], session_key: str
) -> ReplyPayload:
    import json
    try:
        entry = _load_session_entry(session_key, cfg)
        if not entry:
            return ReplyPayload(text="No session data found.")
        # Remove sensitive fields
        safe_entry = {k: v for k, v in entry.items() if k not in ("systemPrompt", "apiKey")}
        return ReplyPayload(text=f"Session export:\n```json\n{json.dumps(safe_entry, indent=2)}\n```")
    except Exception as exc:
        return ReplyPayload(text=f"Export failed: {exc}")


# ---------------------------------------------------------------------------
# /debug
# ---------------------------------------------------------------------------

async def _handle_debug(ctx: Any, cfg: dict[str, Any], session_key: str) -> ReplyPayload:
    lines = ["Debug info:"]
    lines.append(f"Python: {sys.version}")
    lines.append(f"Platform: {platform.platform()}")
    lines.append(f"Session key: {session_key or '(none)'}")

    ctx_fields = [
        "SessionKey", "ChatType", "CommandSource", "Surface", "Provider",
        "From", "To", "SenderId", "SenderName",
    ]
    for field in ctx_fields:
        val = getattr(ctx, field, None)
        if val is not None:
            lines.append(f"  ctx.{field}: {val}")

    return ReplyPayload(text="\n".join(lines))


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _resolve_agent_id(session_key: str, cfg: dict[str, Any]) -> str:
    if not session_key:
        return ""
    try:
        from openclaw.routing.session_key import parse_agent_session_key
        parsed = parse_agent_session_key(session_key)
        return parsed.get("agent_id") or parsed.get("agentId") or "" if parsed else ""
    except Exception:
        parts = session_key.split(":")
        return parts[1] if len(parts) > 1 else ""


def _resolve_model(cfg: dict[str, Any], runtime: Any) -> tuple[str, str]:
    if runtime:
        provider = getattr(runtime, "provider", None) or getattr(runtime, "default_provider", None)
        model = getattr(runtime, "model", None) or getattr(runtime, "default_model", None)
        if provider and model:
            return str(provider), str(model)
    # From config
    if cfg:
        agents_cfg = cfg.get("agents", {}).get("defaults", {})
        model_cfg = agents_cfg.get("model", {})
        primary = model_cfg.get("primary") or ""
        if "/" in primary:
            parts = primary.split("/", 1)
            return parts[0], parts[1]
    return "google", "gemini-2.0-flash"


def _load_session_entry(session_key: str, cfg: dict[str, Any]) -> dict | None:
    if not session_key:
        return None
    try:
        from openclaw.config.sessions import load_session_store, resolve_store_path
        store_path = resolve_store_path(cfg.get("session", {}).get("store"), {})
        store = load_session_store(store_path)
        return store.get(session_key.lower()) or store.get(session_key)
    except Exception:
        pass
    return None


def _format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds // 60)}m {int(seconds % 60)}s"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    return f"{h}h {m}m"
