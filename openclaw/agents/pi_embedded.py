"""Active embedded run registry for the Pi agent runtime.

Mirrors TypeScript ``openclaw/src/agents/pi-embedded-runner/runs.ts``.

This module maintains a process-level registry of currently-running agent
sessions so that:

- Steer mode can inject messages into an active run without starting a
  new turn (``queue_embedded_pi_message``).
- Abort logic can cancel an in-progress run (``abort_embedded_pi_run``).
- The gateway can wait for a specific run to complete
  (``wait_for_embedded_pi_run_end``).
- The restart sentinel can check whether work is still in flight
  (``get_active_embedded_run_count``).
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Handle — mirrors TS EmbeddedPiQueueHandle
# ---------------------------------------------------------------------------

@dataclass
class EmbeddedPiRunHandle:
    """Tracks a single active embedded Pi agent run.

    Mirrors the TS ``EmbeddedPiQueueHandle`` interface.
    """

    run_id: str
    session_key: str
    pi_session: Any  # pi_coding_agent.AgentSession

    # Streaming state — set by PiAgentRuntime
    is_streaming: bool = False
    is_compacting: bool = False

    # Abort signal — set() to request abort
    abort_event: asyncio.Event = field(default_factory=asyncio.Event)

    # Completion waiters
    _done_event: asyncio.Event = field(default_factory=asyncio.Event)

    def queue_message(self, text: str) -> bool:
        """Inject *text* into the active run (steer mode).

        Returns True on success, False if the session does not support
        steering or is compacting.
        """
        if self.is_compacting:
            logger.debug(
                "queue_message: skipping steer — session %s is compacting", self.run_id[:8]
            )
            return False
        if not self.is_streaming:
            logger.debug(
                "queue_message: skipping steer — session %s is not streaming", self.run_id[:8]
            )
            return False
        try:
            steer_fn = getattr(self.pi_session, "steer", None)
            if steer_fn is None:
                return False
            steer_fn(text)
            logger.info("queue_message: steered message into run %s", self.run_id[:8])
            return True
        except Exception as exc:
            logger.warning("queue_message steer error: %s", exc)
            return False

    def mark_done(self) -> None:
        """Signal waiters that this run has finished."""
        self._done_event.set()


# ---------------------------------------------------------------------------
# Registry — module-level state, mirrors TS ``ACTIVE_EMBEDDED_RUNS``
# ---------------------------------------------------------------------------

# session_id (str) → EmbeddedPiRunHandle
ACTIVE_EMBEDDED_RUNS: dict[str, EmbeddedPiRunHandle] = {}

# Completion waiters: run_id → list[asyncio.Event]
_RUN_END_WAITERS: dict[str, list[asyncio.Event]] = {}


# ---------------------------------------------------------------------------
# Public API — mirrors TS exports from runs.ts
# ---------------------------------------------------------------------------

def set_active_embedded_run(
    session_id: str,
    handle: EmbeddedPiRunHandle,
    session_key: str | None = None,
) -> None:
    """Register *handle* as the active run for *session_id*.

    Mirrors TS ``setActiveEmbeddedRun``.
    """
    ACTIVE_EMBEDDED_RUNS[session_id] = handle
    if session_key:
        handle.session_key = session_key
    logger.debug("set_active_embedded_run: session=%s run=%s", session_id[:8], handle.run_id[:8])


def clear_active_embedded_run(session_id: str, run_id: str | None = None) -> None:
    """Remove the active run for *session_id* from the registry.

    If *run_id* is provided it is checked against the current handle to
    avoid clearing a handle that was already replaced by a newer run
    (mirrors TS safety check in ``clearActiveEmbeddedRun``).
    """
    existing = ACTIVE_EMBEDDED_RUNS.get(session_id)
    if existing is None:
        return
    if run_id and existing.run_id != run_id:
        logger.debug(
            "clear_active_embedded_run: run_id mismatch — not clearing (current=%s, requested=%s)",
            existing.run_id[:8], run_id[:8],
        )
        return
    del ACTIVE_EMBEDDED_RUNS[session_id]
    existing.mark_done()
    # Notify waiters keyed by run_id
    for ev in _RUN_END_WAITERS.pop(existing.run_id, []):
        ev.set()
    logger.debug("clear_active_embedded_run: cleared session=%s", session_id[:8])


def get_active_embedded_run(session_id: str) -> EmbeddedPiRunHandle | None:
    """Return the handle for the currently-active run of *session_id*, or None."""
    return ACTIVE_EMBEDDED_RUNS.get(session_id)


def is_embedded_pi_run_active(session_id: str) -> bool:
    """Return True when *session_id* has an active embedded run."""
    return session_id in ACTIVE_EMBEDDED_RUNS


def is_embedded_pi_run_streaming(session_id: str) -> bool:
    """Return True when *session_id* has an active run that is currently streaming."""
    handle = ACTIVE_EMBEDDED_RUNS.get(session_id)
    return handle is not None and handle.is_streaming


def get_active_embedded_run_count() -> int:
    """Return the number of sessions with an active embedded run.

    Used by the restart sentinel to determine whether to wait.
    """
    return len(ACTIVE_EMBEDDED_RUNS)


def queue_embedded_pi_message(session_id: str, text: str) -> bool:
    """Steer *text* into an active run for *session_id*.

    Returns True if the message was successfully queued into the pi session,
    False when no active run exists or steer is not possible.

    Mirrors TS ``queueEmbeddedPiMessage``.
    """
    handle = ACTIVE_EMBEDDED_RUNS.get(session_id)
    if handle is None:
        logger.debug("queue_embedded_pi_message: no active run for session %s", session_id[:8])
        return False
    return handle.queue_message(text)


def abort_embedded_pi_run(session_id: str) -> bool:
    """Request abort for the active run of *session_id*.

    Sets the ``abort_event`` on the handle and also tries to call
    ``pi_session.abort()`` if available.  Non-blocking — callers should use
    ``wait_for_embedded_pi_run_end`` if they need to await completion.

    Returns True if a handle was found and abort was requested, False if no
    active run was found for the session.

    Mirrors TS ``abortEmbeddedPiRun``.
    """
    handle = ACTIVE_EMBEDDED_RUNS.get(session_id)
    if handle is None:
        return False
    handle.abort_event.set()
    try:
        abort_fn = getattr(handle.pi_session, "abort", None)
        if abort_fn is not None:
            # pi_session.abort() may be a coroutine — fire-and-forget safely
            result = abort_fn()
            if asyncio.iscoroutine(result):
                try:
                    asyncio.ensure_future(result)
                except RuntimeError:
                    pass
    except Exception as exc:
        logger.debug("abort_embedded_pi_run: abort error: %s", exc)
    logger.info("abort_embedded_pi_run: abort requested for session %s", session_id[:8])
    return True


async def wait_for_embedded_pi_run_end(
    session_id: str,
    timeout_ms: int = 30_000,
) -> bool:
    """Wait for the active run of *session_id* to finish.

    Returns True if the run ended within *timeout_ms*, False on timeout.
    If no run is active returns True immediately.

    Mirrors TS ``waitForEmbeddedPiRunEnd``.
    """
    handle = ACTIVE_EMBEDDED_RUNS.get(session_id)
    if handle is None:
        return True
    try:
        await asyncio.wait_for(handle._done_event.wait(), timeout=timeout_ms / 1000.0)
        return True
    except asyncio.TimeoutError:
        return False


def notify_embedded_run_ended(session_id: str) -> None:
    """Notify any waiters that the run for *session_id* has ended.

    Called by ``clear_active_embedded_run``; exposed for external use.
    Mirrors TS ``notifyEmbeddedRunEnded``.
    """
    clear_active_embedded_run(session_id)


COMMAND_LANE_MAIN = "main"


def resolve_session_lane(key: str) -> str:
    """Return the command lane name for *key*.

    Mirrors TS ``resolveSessionLane(key)`` in pi-embedded-runner/lanes.ts:
    - Trims whitespace
    - Falls back to COMMAND_LANE_MAIN when empty
    - Adds "session:" prefix ONLY if the key does not already start with it
    """
    cleaned = (key or "").strip() or COMMAND_LANE_MAIN
    return cleaned if cleaned.startswith("session:") else f"session:{cleaned}"


def resolve_global_lane(lane: str | None = None) -> str:
    """Return the global command lane name.

    Mirrors TS ``resolveGlobalLane(lane?)`` in pi-embedded-runner/lanes.ts:
    - Trims whitespace
    - Falls back to COMMAND_LANE_MAIN when empty/None
    """
    cleaned = (lane or "").strip()
    return cleaned if cleaned else COMMAND_LANE_MAIN


def resolve_embedded_session_lane(session_key: str) -> str:
    """Return the command lane name for *session_key*.

    Mirrors TS ``resolveEmbeddedSessionLane(key)`` from
    ``pi-embedded-runner/lanes.ts`` which delegates to ``resolveSessionLane``.

    Alignment fixes (P1-10):
    - Trims the key before use
    - Falls back to COMMAND_LANE_MAIN when key is empty
    - Does NOT double-add the "session:" prefix
    """
    return resolve_session_lane(session_key)


# ---------------------------------------------------------------------------
# P1-11: RotationManager — multi-key auth rotation placeholder
# ---------------------------------------------------------------------------

class RotationManager:
    """Manages rotation through multiple API keys for a provider.

    Mirrors TS auth profile rotation in agents/auth-profiles.ts.
    The rotation manager maintains a list of API keys and cycles through them
    on rate-limit / auth errors, with per-key cooldowns.

    In the Python version this provides a foundation for future multi-key
    support. Current implementation cycles naively without cooldown tracking.
    """

    def __init__(self, profiles: list[dict]) -> None:
        """
        Args:
            profiles: List of auth profile dicts with at least ``{"apiKey": str}``
        """
        self._profiles = [p for p in profiles if p and p.get("apiKey")]
        self._index = 0
        self._cooldowns: dict[str, float] = {}  # profile_id → cooldown_until_ts
        logger.debug("RotationManager: initialized with %d profile(s)", len(self._profiles))

    def get_current(self) -> dict | None:
        """Return the current auth profile, or None if all profiles are exhausted."""
        if not self._profiles:
            return None
        # Find the first non-cooled-down profile starting from _index
        import time as _time
        now = _time.time()
        n = len(self._profiles)
        for i in range(n):
            idx = (self._index + i) % n
            profile = self._profiles[idx]
            pid = profile.get("id", str(idx))
            if self._cooldowns.get(pid, 0) <= now:
                self._index = idx
                return profile
        return None  # All in cooldown

    def mark_failed(self, profile_id: str | None, cooldown_seconds: float = 60.0) -> None:
        """Put a profile into cooldown after a rate-limit or auth error."""
        if not profile_id:
            return
        import time as _time
        self._cooldowns[profile_id] = _time.time() + cooldown_seconds
        # Advance index to the next profile
        self._index = (self._index + 1) % max(len(self._profiles), 1)
        logger.debug("RotationManager: profile %s in cooldown for %.0fs", profile_id, cooldown_seconds)

    def advance(self) -> dict | None:
        """Advance to the next available profile and return it."""
        if not self._profiles:
            return None
        self._index = (self._index + 1) % len(self._profiles)
        return self.get_current()

    def has_available(self) -> bool:
        """Return True when at least one profile is not in cooldown."""
        return self.get_current() is not None


__all__ = [
    "EmbeddedPiRunHandle",
    "ACTIVE_EMBEDDED_RUNS",
    "COMMAND_LANE_MAIN",
    "set_active_embedded_run",
    "clear_active_embedded_run",
    "get_active_embedded_run",
    "is_embedded_pi_run_active",
    "is_embedded_pi_run_streaming",
    "get_active_embedded_run_count",
    "queue_embedded_pi_message",
    "abort_embedded_pi_run",
    "wait_for_embedded_pi_run_end",
    "notify_embedded_run_ended",
    "resolve_session_lane",
    "resolve_global_lane",
    "resolve_embedded_session_lane",
    "RotationManager",
]
