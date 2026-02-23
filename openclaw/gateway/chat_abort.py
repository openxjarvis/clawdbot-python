"""
Chat abort utilities — fully aligned with TypeScript
openclaw/src/gateway/chat-abort.ts.

Provides:
- ChatAbortControllerEntry: per-run abort state
- is_chat_stop_command_text(): detect /stop and abort triggers
- resolve_chat_run_expires_at_ms(): compute bounded expiry time
- abort_chat_run_by_id(): abort a single run and broadcast
- abort_chat_runs_for_session_key(): abort all runs for a session
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

@dataclass
class ChatAbortControllerEntry:
    """State for a single running chat turn — mirrors TS ChatAbortControllerEntry."""
    task: asyncio.Task  # asyncio task powering this run
    session_id: str
    session_key: str
    started_at_ms: int
    expires_at_ms: int


class ChatAbortOps(Protocol):
    """Interface expected by abort helpers — mirrors TS ChatAbortOps."""
    chat_abort_controllers: dict[str, ChatAbortControllerEntry]
    chat_run_buffers: dict[str, str]
    chat_delta_sent_at: dict[str, int]
    chat_aborted_runs: dict[str, int]
    agent_run_seq: dict[str, int]

    def remove_chat_run(
        self,
        session_id: str,
        client_run_id: str,
        session_key: str | None = None,
    ) -> dict[str, str] | None: ...

    async def broadcast(
        self,
        event: str,
        payload: Any,
        opts: dict | None = None,
    ) -> None: ...

    async def node_send_to_session(
        self,
        session_key: str,
        event: str,
        payload: Any,
    ) -> None: ...


# ---------------------------------------------------------------------------
# Stop-command detection
# ---------------------------------------------------------------------------

_ABORT_TRIGGER_WORDS = frozenset({
    "/stop",
    "/abort",
    "/cancel",
    "stop",
    "cancel",
    "abort",
})


def is_abort_trigger(text: str) -> bool:
    """Return True if text matches a known abort trigger word/phrase."""
    return text.strip().lower() in _ABORT_TRIGGER_WORDS


def is_chat_stop_command_text(text: str) -> bool:
    """Return True if text is a chat stop command (/stop or abort trigger).

    Mirrors TS isChatStopCommandText().
    """
    trimmed = text.strip()
    if not trimmed:
        return False
    return trimmed.lower() == "/stop" or is_abort_trigger(trimmed)


# ---------------------------------------------------------------------------
# Expiry resolution
# ---------------------------------------------------------------------------

def resolve_chat_run_expires_at_ms(
    *,
    now: int,
    timeout_ms: int,
    grace_ms: int = 60_000,
    min_ms: int = 2 * 60_000,
    max_ms: int = 24 * 60 * 60_000,
) -> int:
    """Compute a bounded expiry timestamp for a chat run.

    Mirrors TS resolveChatRunExpiresAtMs().

    Args:
        now: Current epoch milliseconds.
        timeout_ms: Expected run duration in ms.
        grace_ms: Extra buffer after timeout (default 60s).
        min_ms: Minimum window from now (default 2m).
        max_ms: Maximum window from now (default 24h).
    """
    bounded_timeout_ms = max(0, timeout_ms)
    target = now + bounded_timeout_ms + grace_ms
    min_t = now + min_ms
    max_t = now + max_ms
    return min(max_t, max(min_t, target))


# ---------------------------------------------------------------------------
# Broadcast helper
# ---------------------------------------------------------------------------

async def _broadcast_chat_aborted(
    ops: Any,
    *,
    run_id: str,
    session_key: str,
    stop_reason: str | None = None,
    partial_text: str | None = None,
) -> None:
    """Broadcast a chat.aborted event to all subscribers."""
    seq: int = (ops.agent_run_seq.get(run_id) or 0) + 1
    payload: dict[str, Any] = {
        "runId": run_id,
        "sessionKey": session_key,
        "seq": seq,
        "state": "aborted",
    }
    if stop_reason:
        payload["stopReason"] = stop_reason
    if partial_text:
        payload["message"] = {
            "role": "assistant",
            "content": [{"type": "text", "text": partial_text}],
            "timestamp": int(time.time() * 1000),
        }
    try:
        await ops.broadcast("chat", payload)
    except Exception:
        pass
    try:
        await ops.node_send_to_session(session_key, "chat", payload)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Abort a single run
# ---------------------------------------------------------------------------

async def abort_chat_run_by_id(
    ops: Any,
    *,
    run_id: str,
    session_key: str,
    stop_reason: str | None = None,
) -> dict[str, bool]:
    """Abort a specific running chat turn and broadcast the aborted event.

    Mirrors TS abortChatRunById().

    Returns:
        {"aborted": True} if the run was found and cancelled,
        {"aborted": False} otherwise.
    """
    active = ops.chat_abort_controllers.get(run_id)
    if not active:
        return {"aborted": False}
    if active.session_key != session_key:
        return {"aborted": False}

    buffered_text = ops.chat_run_buffers.get(run_id)
    partial_text = buffered_text.strip() if buffered_text and buffered_text.strip() else None

    # Record abort time before cancelling
    ops.chat_aborted_runs[run_id] = int(time.time() * 1000)

    # Cancel the task
    active.task.cancel()

    # Clean up state
    ops.chat_abort_controllers.pop(run_id, None)
    ops.chat_run_buffers.pop(run_id, None)
    ops.chat_delta_sent_at.pop(run_id, None)

    # Remove from run registry (if available)
    removed: dict | None = None
    try:
        removed = ops.remove_chat_run(run_id, run_id, session_key)
    except Exception:
        pass

    await _broadcast_chat_aborted(
        ops,
        run_id=run_id,
        session_key=session_key,
        stop_reason=stop_reason,
        partial_text=partial_text,
    )

    ops.agent_run_seq.pop(run_id, None)
    if removed and isinstance(removed, dict):
        client_run_id = removed.get("clientRunId")
        if client_run_id:
            ops.agent_run_seq.pop(client_run_id, None)

    return {"aborted": True}


# ---------------------------------------------------------------------------
# Abort all runs for a session
# ---------------------------------------------------------------------------

async def abort_chat_runs_for_session_key(
    ops: Any,
    *,
    session_key: str,
    stop_reason: str | None = None,
) -> dict[str, Any]:
    """Abort all active chat runs for a given session key.

    Mirrors TS abortChatRunsForSessionKey().

    Returns:
        {"aborted": bool, "runIds": list[str]}
    """
    run_ids: list[str] = []
    for run_id, active in list(ops.chat_abort_controllers.items()):
        if active.session_key != session_key:
            continue
        result = await abort_chat_run_by_id(
            ops,
            run_id=run_id,
            session_key=session_key,
            stop_reason=stop_reason,
        )
        if result.get("aborted"):
            run_ids.append(run_id)
    return {"aborted": len(run_ids) > 0, "runIds": run_ids}
