"""Global synchronous agent event pub-sub.

Mirrors TypeScript ``src/infra/agent-events.ts``.

Used for:
- Subagent lifecycle events (start, error, end)
- Fallback transition events
- Diagnostic events
- Memory flush triggers

Usage::

    from openclaw.infra.agent_events import emit_agent_event, on_agent_event

    # Subscribe (returns an unsubscribe callable)
    unsub = on_agent_event(lambda evt: print(evt))

    # Emit
    emit_agent_event({"type": "agent_lifecycle", "phase": "start", "runId": "..."})

    # Unsubscribe
    unsub()
"""
from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Module-level listener registry — synchronous callbacks only (mirrors TS)
_listeners: set[Callable[[dict[str, Any]], None]] = set()


def emit_agent_event(event: dict[str, Any]) -> None:
    """Emit an agent event to all registered listeners.

    Synchronous and non-blocking — mirrors TS ``emitAgentEvent``.
    Listener exceptions are caught and logged so one bad listener cannot
    break the entire event pipeline.

    Args:
        event: Arbitrary event payload dict. Convention:
               ``{"type": str, ...}`` where ``type`` is the event category
               (e.g. ``"agent_lifecycle"``, ``"fallback_transition"``,
               ``"memory_flush"``).
    """
    for listener in list(_listeners):
        try:
            listener(event)
        except Exception as exc:
            logger.warning("agent_events: listener error: %s", exc)


def on_agent_event(listener: Callable[[dict[str, Any]], None]) -> Callable[[], None]:
    """Register *listener* to receive all future agent events.

    Mirrors TS ``onAgentEvent``.

    Args:
        listener: Synchronous callable accepting a single event dict.

    Returns:
        An unsubscribe callable — call it to remove the listener.
    """
    _listeners.add(listener)

    def _unsub() -> None:
        _listeners.discard(listener)

    return _unsub


def listener_count() -> int:
    """Return the number of currently registered listeners (useful for testing)."""
    return len(_listeners)


def clear_all_listeners() -> None:
    """Remove every registered listener (useful for tests)."""
    _listeners.clear()


__all__ = [
    "emit_agent_event",
    "on_agent_event",
    "listener_count",
    "clear_all_listeners",
]
