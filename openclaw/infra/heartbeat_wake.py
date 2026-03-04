"""Heartbeat wake coalescing layer.

Mirrors TypeScript openclaw/src/infra/heartbeat-wake.ts.

Key design:
- 250 ms coalesce window before firing the wake handler.
- Priority-keyed ``pendingWakes`` map (one entry per agentId/sessionKey target).
  Priorities: ACTION (3) > DEFAULT (2) > INTERVAL (1) > RETRY (0).
- Dual-buffer: a ``_scheduled`` flag lets a queued wake pre-empt the timer.
- Timer preemption: a new request with an earlier due-time cancels the
  existing asyncio timer handle and schedules a fresh one.
- requests-in-flight check: if the handler returns
  ``{"status": "skipped", "reason": "requests-in-flight"}`` the wake is
  re-queued with reason ``"retry"`` and retried after 1 s.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

DEFAULT_COALESCE_MS: int = 250
DEFAULT_RETRY_MS: int = 1_000

REASON_PRIORITY: dict[str, int] = {
    "RETRY": 0,
    "INTERVAL": 1,
    "DEFAULT": 2,
    "ACTION": 3,
}

HeartbeatWakeHandler = Callable[
    [dict[str, Any]],
    Awaitable[dict[str, Any]],
]


@dataclass
class _PendingWakeReason:
    reason: str
    priority: int
    requested_at: float
    agent_id: str | None = None
    session_key: str | None = None


# -------------------------------------------------------------------------
# Module-level singleton state (mirrors TS module-level vars)
# -------------------------------------------------------------------------

_handler: HeartbeatWakeHandler | None = None
_handler_generation: int = 0
_pending_wakes: dict[str, _PendingWakeReason] = {}
_scheduled: bool = False
_running: bool = False
_timer_handle: asyncio.TimerHandle | None = None
_timer_due_at: float | None = None
_timer_kind: str | None = None  # "normal" | "retry"


# -------------------------------------------------------------------------
# Reason helpers (mirrors heartbeat-reason.ts)
# -------------------------------------------------------------------------

def _normalize_heartbeat_wake_reason(reason: str | None) -> str:
    trimmed = (reason or "").strip()
    return trimmed if trimmed else "requested"


def _resolve_heartbeat_reason_kind(reason: str | None) -> str:
    trimmed = (reason or "").strip()
    if trimmed == "retry":
        return "retry"
    if trimmed == "interval":
        return "interval"
    if trimmed == "manual":
        return "manual"
    if trimmed == "exec-event":
        return "exec-event"
    if trimmed == "wake":
        return "wake"
    if trimmed.startswith("cron:"):
        return "cron"
    if trimmed.startswith("hook:"):
        return "hook"
    return "other"


def _is_heartbeat_action_wake_reason(reason: str | None) -> bool:
    kind = _resolve_heartbeat_reason_kind(reason)
    return kind in ("manual", "exec-event", "hook")


def _resolve_reason_priority(reason: str) -> int:
    kind = _resolve_heartbeat_reason_kind(reason)
    if kind == "retry":
        return REASON_PRIORITY["RETRY"]
    if kind == "interval":
        return REASON_PRIORITY["INTERVAL"]
    if _is_heartbeat_action_wake_reason(reason):
        return REASON_PRIORITY["ACTION"]
    return REASON_PRIORITY["DEFAULT"]


def _normalize_wake_target(value: str | None) -> str | None:
    trimmed = (value or "").strip()
    return trimmed or None


def _get_wake_target_key(agent_id: str | None, session_key: str | None) -> str:
    return f"{agent_id or ''}::{session_key or ''}"


# -------------------------------------------------------------------------
# Pending wake queue
# -------------------------------------------------------------------------

def _queue_pending_wake_reason(
    reason: str | None = None,
    agent_id: str | None = None,
    session_key: str | None = None,
    requested_at: float | None = None,
) -> None:
    global _pending_wakes
    _requested_at = requested_at if requested_at is not None else time.time() * 1000
    normalized_reason = _normalize_heartbeat_wake_reason(reason)
    normalized_agent_id = _normalize_wake_target(agent_id)
    normalized_session_key = _normalize_wake_target(session_key)
    wake_target_key = _get_wake_target_key(normalized_agent_id, normalized_session_key)
    next_wake = _PendingWakeReason(
        reason=normalized_reason,
        priority=_resolve_reason_priority(normalized_reason),
        requested_at=_requested_at,
        agent_id=normalized_agent_id,
        session_key=normalized_session_key,
    )
    previous = _pending_wakes.get(wake_target_key)
    if not previous:
        _pending_wakes[wake_target_key] = next_wake
        return
    if next_wake.priority > previous.priority:
        _pending_wakes[wake_target_key] = next_wake
        return
    if next_wake.priority == previous.priority and next_wake.requested_at >= previous.requested_at:
        _pending_wakes[wake_target_key] = next_wake


# -------------------------------------------------------------------------
# Timer scheduling with preemption
# -------------------------------------------------------------------------

def _schedule(coalesce_ms: int, kind: str = "normal") -> None:
    """Schedule the wake batch to fire after ``coalesce_ms`` milliseconds.

    If a timer already exists:
    - retry-kind timers are never preempted (they enforce a hard minimum delay).
    - normal timers are preempted if the new request would fire sooner.
    """
    global _timer_handle, _timer_due_at, _timer_kind, _scheduled

    loop = asyncio.get_running_loop()
    delay_s = max(0, (coalesce_ms if isinstance(coalesce_ms, (int, float)) else DEFAULT_COALESCE_MS)) / 1000.0
    due_at = time.monotonic() + delay_s

    if _timer_handle is not None:
        if _timer_kind == "retry":
            # Retry cooldown is a hard minimum — do not preempt.
            return
        if _timer_due_at is not None and _timer_due_at <= due_at:
            # Existing timer fires sooner or at the same time — keep it.
            return
        # New request fires sooner — cancel existing timer.
        _timer_handle.cancel()
        _timer_handle = None
        _timer_due_at = None
        _timer_kind = None

    _timer_due_at = due_at
    _timer_kind = kind
    _timer_handle = loop.call_later(delay_s, lambda: asyncio.ensure_future(_fire(delay_s, kind)))


async def _fire(delay_s: float, kind: str) -> None:
    global _timer_handle, _timer_due_at, _timer_kind, _scheduled, _running, _pending_wakes

    _timer_handle = None
    _timer_due_at = None
    _timer_kind = None
    _scheduled = False

    active = _handler
    if active is None:
        return

    if _running:
        _scheduled = True
        _schedule(int(delay_s * 1000), kind)
        return

    pending_batch = list(_pending_wakes.values())
    _pending_wakes.clear()
    _running = True
    try:
        for pending_wake in pending_batch:
            wake_opts: dict[str, Any] = {}
            if pending_wake.reason:
                wake_opts["reason"] = pending_wake.reason
            if pending_wake.agent_id:
                wake_opts["agentId"] = pending_wake.agent_id
            if pending_wake.session_key:
                wake_opts["sessionKey"] = pending_wake.session_key
            try:
                res = await active(wake_opts)
            except Exception as exc:
                logger.error("Heartbeat wake handler error: %s", exc)
                _queue_pending_wake_reason(
                    reason=pending_wake.reason or "retry",
                    agent_id=pending_wake.agent_id,
                    session_key=pending_wake.session_key,
                )
                _schedule(DEFAULT_RETRY_MS, "retry")
                continue

            if (
                isinstance(res, dict)
                and res.get("status") == "skipped"
                and res.get("reason") == "requests-in-flight"
            ):
                _queue_pending_wake_reason(
                    reason=pending_wake.reason or "retry",
                    agent_id=pending_wake.agent_id,
                    session_key=pending_wake.session_key,
                )
                _schedule(DEFAULT_RETRY_MS, "retry")
    except Exception as exc:
        logger.error("Heartbeat wake batch error: %s", exc)
        for pending_wake in pending_batch:
            _queue_pending_wake_reason(
                reason=pending_wake.reason or "retry",
                agent_id=pending_wake.agent_id,
                session_key=pending_wake.session_key,
            )
        _schedule(DEFAULT_RETRY_MS, "retry")
    finally:
        _running = False
        if _pending_wakes or _scheduled:
            _schedule(int(delay_s * 1000), "normal")


# -------------------------------------------------------------------------
# Public API (mirrors TS exports)
# -------------------------------------------------------------------------

def set_heartbeat_wake_handler(next_handler: HeartbeatWakeHandler | None) -> "Callable[[], None]":
    """Register (or clear) the heartbeat wake handler.

    Returns a disposer function that clears this specific registration.
    Stale disposers from previous registrations are no-ops.
    Mirrors TS setHeartbeatWakeHandler().
    """
    global _handler, _handler_generation, _timer_handle, _timer_due_at, _timer_kind
    global _running, _scheduled

    _handler_generation += 1
    generation = _handler_generation
    _handler = next_handler

    if next_handler is not None:
        # Clear stale timer metadata from previous lifecycle.
        if _timer_handle is not None:
            _timer_handle.cancel()
        _timer_handle = None
        _timer_due_at = None
        _timer_kind = None
        _running = False
        _scheduled = False

    if _handler is not None and _pending_wakes:
        _schedule(DEFAULT_COALESCE_MS, "normal")

    def _dispose() -> None:
        global _handler, _handler_generation
        if _handler_generation != generation:
            return
        if _handler is not next_handler:
            return
        _handler_generation += 1
        _handler = None

    return _dispose


def request_heartbeat_now(
    reason: str | None = None,
    coalesce_ms: int = DEFAULT_COALESCE_MS,
    agent_id: str | None = None,
    session_key: str | None = None,
) -> None:
    """Request an immediate heartbeat wake, coalesced with other requests.

    Mirrors TS requestHeartbeatNow().
    """
    _queue_pending_wake_reason(reason=reason, agent_id=agent_id, session_key=session_key)
    _schedule(coalesce_ms, "normal")


def has_heartbeat_wake_handler() -> bool:
    """Return True if a wake handler is registered."""
    return _handler is not None


def has_pending_heartbeat_wake() -> bool:
    """Return True if there are pending wakes or an active timer."""
    return bool(_pending_wakes) or _timer_handle is not None or _scheduled


def reset_heartbeat_wake_state() -> None:
    """Reset all module state (for tests or in-process restarts)."""
    global _handler, _handler_generation, _pending_wakes, _scheduled, _running
    global _timer_handle, _timer_due_at, _timer_kind

    if _timer_handle is not None:
        _timer_handle.cancel()
    _timer_handle = None
    _timer_due_at = None
    _timer_kind = None
    _pending_wakes.clear()
    _scheduled = False
    _running = False
    _handler_generation += 1
    _handler = None
