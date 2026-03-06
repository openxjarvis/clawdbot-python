"""
Process management tool — mirrors TS src/agents/bash-tools.process.ts

Manages background processes launched by the exec/bash tool.

Actions (matching TS process tool):
  list        — list all backgrounded running + finished sessions
  poll        — drain buffered stdout/stderr since last poll; wait up to N ms
  log         — read full aggregated output with offset/limit pagination
  write       — write raw bytes to stdin
  send-keys   — send encoded key sequences (Ctrl-C, Enter, etc.)
  submit      — send CR (\\r) to stdin
  paste       — send text with optional bracketed paste mode
  kill        — terminate session (SIGTERM then SIGKILL)
  clear       — remove a finished session from the registry
  remove      — kill (if running) + remove from registry
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..bash_process_registry import get_process_registry, ProcessSession, FinishedSession
from ..types import AgentToolResult, TextContent
from .base import AgentToolBase

logger = logging.getLogger(__name__)

# Key-sequence encoding table (mirrors TS SEND_KEYS_MAP)
_SEND_KEYS_MAP: dict[str, bytes] = {
    "ctrl-c":     b"\x03",
    "ctrl-d":     b"\x04",
    "ctrl-z":     b"\x1a",
    "ctrl-l":     b"\x0c",
    "enter":      b"\r",
    "return":     b"\r",
    "tab":        b"\t",
    "backspace":  b"\x7f",
    "escape":     b"\x1b",
    "up":         b"\x1b[A",
    "down":       b"\x1b[B",
    "right":      b"\x1b[C",
    "left":       b"\x1b[D",
    "home":       b"\x1b[H",
    "end":        b"\x1b[F",
    "pageup":     b"\x1b[5~",
    "pagedown":   b"\x1b[6~",
    "delete":     b"\x1b[3~",
}


def create_process_tool() -> AgentToolBase:
    """Create the process management tool (mirrors TS createProcessTool())."""

    registry = get_process_registry()

    class ProcessTool(AgentToolBase[dict, dict]):
        """Manage background shell processes launched by the exec/bash tool."""

        @property
        def name(self) -> str:
            return "process"

        @property
        def label(self) -> str:
            return "Process"

        @property
        def description(self) -> str:
            return (
                "Manage background processes launched by the bash/exec tool. "
                "Actions: list, poll, log, write, send-keys, submit, paste, kill, clear, remove."
            )

        @property
        def parameters(self) -> dict[str, Any]:
            return {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "list", "poll", "log", "write",
                            "send-keys", "submit", "paste",
                            "kill", "clear", "remove",
                        ],
                        "description": "Action to perform on a background process",
                    },
                    "session_id": {
                        "type": "string",
                        "description": "Session ID returned when process was backgrounded",
                    },
                    "timeout_ms": {
                        "type": "integer",
                        "description": "(poll) Wait up to N ms for new output before returning",
                        "default": 0,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "(log) Character offset into aggregated output",
                        "default": 0,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "(log) Max characters to return",
                        "default": 8000,
                    },
                    "data": {
                        "type": "string",
                        "description": "(write/paste) Text to write to stdin",
                    },
                    "keys": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "(send-keys) Key sequence names: ctrl-c, enter, tab, etc.",
                    },
                    "bracketed_paste": {
                        "type": "boolean",
                        "description": "(paste) Wrap in bracketed paste escape sequences",
                        "default": False,
                    },
                },
                "required": ["action"],
            }

        async def execute(
            self,
            tool_call_id: str,
            params: dict,
            signal: asyncio.Event | None = None,
            on_update: Any = None,
        ) -> AgentToolResult[dict]:
            action = params.get("action", "")
            try:
                if action == "list":
                    return _do_list(registry)
                elif action == "poll":
                    return await _do_poll(registry, params)
                elif action == "log":
                    return _do_log(registry, params)
                elif action == "write":
                    return _do_write(registry, params)
                elif action == "send-keys":
                    return _do_send_keys(registry, params)
                elif action == "submit":
                    return _do_submit(registry, params)
                elif action == "paste":
                    return _do_paste(registry, params)
                elif action == "kill":
                    return await _do_kill(registry, params)
                elif action == "clear":
                    return _do_clear(registry, params)
                elif action == "remove":
                    return await _do_remove(registry, params)
                else:
                    return _err(f"Unknown action: {action!r}")
            except Exception as e:
                logger.error("process tool error (action=%s): %s", action, e, exc_info=True)
                return _err(str(e))

    return ProcessTool()


# ── Helper constructors ────────────────────────────────────────────────────────

def _ok(text: str, details: dict | None = None) -> AgentToolResult:
    return AgentToolResult(content=[TextContent(text=text)], details=details)


def _err(msg: str) -> AgentToolResult:
    raise Exception(msg)


def _require_session_id(params: dict) -> str:
    sid = params.get("session_id", "").strip()
    if not sid:
        raise Exception("session_id required")
    return sid


# ── Action implementations ─────────────────────────────────────────────────────

def _do_list(registry) -> AgentToolResult:
    """list — show all backgrounded running + finished sessions."""
    running = registry.list_running()
    finished = list(registry._finished.values())

    if not running and not finished:
        return _ok("No background processes.", {"count": 0, "sessions": []})

    lines: list[str] = []
    sessions_data: list[dict] = []

    for s in running:
        status = "running"
        lines.append(f"[{s.id}] {s.process_id}  pid={s.process.pid}  {status}")
        sessions_data.append({
            "session_id": s.id, "process_id": s.process_id,
            "pid": s.process.pid, "status": status, "backgrounded": s.backgrounded,
        })

    for s in finished:
        status = f"exited({s.exit_code})" if s.exit_code is not None else "finished"
        lines.append(f"[{s.id}] {s.process_id}  {status}")
        sessions_data.append({
            "session_id": s.id, "process_id": s.process_id,
            "status": status, "exit_code": s.exit_code,
        })

    return _ok("\n".join(lines), {"count": len(sessions_data), "sessions": sessions_data})


async def _do_poll(registry, params: dict) -> AgentToolResult:
    """poll — drain buffered output, optionally waiting up to timeout_ms."""
    sid = _require_session_id(params)
    timeout_ms: int = int(params.get("timeout_ms") or 0)

    session = registry.get_running(sid)
    if session is None:
        finished = registry.get_finished(sid)
        if finished:
            return _ok(
                f"Process finished (exit_code={finished.exit_code}).\n{finished.tail}",
                {"status": "finished", "exit_code": finished.exit_code},
            )
        raise Exception(f"Session {sid!r} not found")

    if timeout_ms > 0:
        deadline = asyncio.get_event_loop().time() + timeout_ms / 1000
        while asyncio.get_event_loop().time() < deadline:
            stdout, stderr = session.drain_pending()
            if stdout or stderr or session.exited:
                break
            remaining = deadline - asyncio.get_event_loop().time()
            await asyncio.sleep(min(0.1, remaining))
        else:
            stdout, stderr = session.drain_pending()
    else:
        stdout, stderr = session.drain_pending()

    status = "finished" if session.exited else "running"
    output = stdout
    if stderr:
        output += ("\n" if output else "") + stderr

    return _ok(
        output or "(no new output)",
        {
            "status": status,
            "exit_code": session.exit_code,
            "pid": session.process.pid,
            "stdout_bytes": len(stdout),
            "stderr_bytes": len(stderr),
        },
    )


def _do_log(registry, params: dict) -> AgentToolResult:
    """log — read aggregated output with offset/limit."""
    sid = _require_session_id(params)
    offset: int = int(params.get("offset") or 0)
    limit: int = int(params.get("limit") or 8000)

    session = registry.get_any(sid)
    if session is None:
        raise Exception(f"Session {sid!r} not found")

    agg = session.aggregated if isinstance(session, ProcessSession) else session.aggregated
    total = len(agg)
    chunk = agg[offset: offset + limit]
    remaining = max(0, total - offset - len(chunk))

    return _ok(
        chunk or "(empty)",
        {
            "total_chars": total,
            "offset": offset,
            "returned_chars": len(chunk),
            "remaining_chars": remaining,
        },
    )


def _do_write(registry, params: dict) -> AgentToolResult:
    """write — write raw text to process stdin."""
    sid = _require_session_id(params)
    data: str = params.get("data") or ""
    session = registry.get_running(sid)
    if session is None:
        raise Exception(f"Session {sid!r} not found or already finished")
    if session.process.stdin is None:
        raise Exception(f"Session {sid!r} stdin is not available")
    session.process.stdin.write(data.encode())
    return _ok(f"Wrote {len(data)} bytes to stdin of session {sid!r}")


def _do_send_keys(registry, params: dict) -> AgentToolResult:
    """send-keys — send encoded key sequences to stdin."""
    sid = _require_session_id(params)
    keys: list[str] = params.get("keys") or []
    session = registry.get_running(sid)
    if session is None:
        raise Exception(f"Session {sid!r} not found or already finished")
    if session.process.stdin is None:
        raise Exception(f"Session {sid!r} stdin is not available")

    sent: list[str] = []
    for key in keys:
        encoded = _SEND_KEYS_MAP.get(key.lower())
        if encoded is None:
            # Treat unknown keys as literal text
            encoded = key.encode()
        session.process.stdin.write(encoded)
        sent.append(key)

    return _ok(f"Sent keys {sent!r} to session {sid!r}")


def _do_submit(registry, params: dict) -> AgentToolResult:
    """submit — send CR (\\r) to stdin."""
    sid = _require_session_id(params)
    session = registry.get_running(sid)
    if session is None:
        raise Exception(f"Session {sid!r} not found or already finished")
    if session.process.stdin is None:
        raise Exception(f"Session {sid!r} stdin is not available")
    session.process.stdin.write(b"\r")
    return _ok(f"Submitted (CR) to session {sid!r}")


def _do_paste(registry, params: dict) -> AgentToolResult:
    """paste — send text, optionally using bracketed paste mode."""
    sid = _require_session_id(params)
    data: str = params.get("data") or ""
    bracketed: bool = bool(params.get("bracketed_paste", False))
    session = registry.get_running(sid)
    if session is None:
        raise Exception(f"Session {sid!r} not found or already finished")
    if session.process.stdin is None:
        raise Exception(f"Session {sid!r} stdin is not available")

    if bracketed:
        payload = b"\x1b[200~" + data.encode() + b"\x1b[201~"
    else:
        payload = data.encode()
    session.process.stdin.write(payload)
    return _ok(f"Pasted {len(data)} chars to session {sid!r} (bracketed={bracketed})")


async def _do_kill(registry, params: dict) -> AgentToolResult:
    """kill — terminate session gracefully then forcefully."""
    sid = _require_session_id(params)
    killed = await registry.kill_session(sid)
    if not killed:
        # Maybe it's already finished
        finished = registry.get_finished(sid)
        if finished:
            return _ok(f"Session {sid!r} already finished (exit_code={finished.exit_code})")
        raise Exception(f"Session {sid!r} not found")
    return _ok(f"Killed session {sid!r}")


def _do_clear(registry, params: dict) -> AgentToolResult:
    """clear — remove a finished session from the registry."""
    sid = _require_session_id(params)
    removed = registry.remove_session(sid)
    if not removed:
        raise Exception(f"Session {sid!r} not found in finished sessions (may still be running — use 'kill' first)")
    return _ok(f"Cleared session {sid!r}")


async def _do_remove(registry, params: dict) -> AgentToolResult:
    """remove — kill (if running) + remove from registry."""
    sid = _require_session_id(params)
    # Try to kill if running
    if registry.get_running(sid):
        await registry.kill_session(sid)
    # Remove from finished
    registry.remove_session(sid)
    return _ok(f"Removed session {sid!r}")


# Backwards-compat alias: allow both create_process_tool() and ProcessTool()
ProcessTool = create_process_tool

__all__ = ["create_process_tool", "ProcessTool"]
