"""Queue policy resolution for the auto-reply dispatch flow.

Mirrors TypeScript ``openclaw/src/auto-reply/reply/queue-policy.ts``.

Determines what action to take when a new message arrives while an agent
is potentially still running.

Actions:
  - "run-now"          — no active run; start immediately
  - "steer"            — active run is streaming; inject message via steer
  - "enqueue-followup" — active run exists; queue for after completion
  - "interrupt"        — queue mode is "interrupt"; abort active and re-run
  - "drop"             — heartbeat or other drop-condition
"""
from __future__ import annotations

import logging
from typing import Literal

from openclaw.auto_reply.reply.queue import QueueSettings

logger = logging.getLogger(__name__)

ActiveRunQueueAction = Literal[
    "run-now",
    "steer",
    "enqueue-followup",
    "interrupt",
    "drop",
]


def resolve_active_run_queue_action(
    session_id: str,
    queue_settings: QueueSettings | None,
    *,
    is_heartbeat: bool = False,
) -> ActiveRunQueueAction:
    """Return the action to take for a new inbound message.

    Mirrors TS ``resolveActiveRunQueueAction``.

    Args:
        session_id:      The session identifier (used to check active runs).
        queue_settings:  Resolved queue settings for this session.
        is_heartbeat:    True if the message is a heartbeat prompt (always drop).
    """
    from openclaw.agents.pi_embedded import (
        is_embedded_pi_run_active,
        is_embedded_pi_run_streaming,
    )

    is_active = is_embedded_pi_run_active(session_id)

    # When there is no active run, run immediately (or drop heartbeats when idle).
    # Mirrors TS: !isActive check comes first; a heartbeat with no active run
    # returns "run-now" in TS so the turn immediately sends the heartbeat reply.
    if not is_active:
        if is_heartbeat:
            return "drop"
        return "run-now"

    # Active run: heartbeat is always silently dropped
    if is_heartbeat:
        return "drop"

    mode = (queue_settings.mode if queue_settings else None) or "followup"

    # Interrupt mode: abort current run and start fresh
    if mode == "interrupt":
        return "interrupt"

    # Steer mode: try to inject directly into the active streaming session
    if mode in ("steer", "steer-backlog", "steer+backlog"):
        if is_embedded_pi_run_streaming(session_id):
            return "steer"
        # Active but not streaming (e.g. compacting) → fall through to followup
        if mode == "steer":
            # Pure steer — enqueue as followup for after run finishes
            return "enqueue-followup"

    # Default: enqueue as followup when agent is busy
    if mode in ("followup", "collect", "steer-backlog", "steer+backlog", "queue"):
        return "enqueue-followup"

    return "enqueue-followup"


__all__ = ["ActiveRunQueueAction", "resolve_active_run_queue_action"]
