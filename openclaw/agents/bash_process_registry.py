"""
Background process registry — mirrors TS src/agents/bash-process-registry.ts

Tracks running and finished background processes launched by the exec/bash tool.
Provides drainable stdout/stderr buffers (pendingStdout / pendingStderr) for
the `process poll` action, and a full aggregated output buffer for `process log`.

Usage:
    registry = get_process_registry()
    session = registry.create_session(process_id, process)
    registry.mark_backgrounded(process_id)
    ...
    # In process tool:
    sessions = registry.list_running()
    buf = registry.drain_pending(session_id)
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_TTL_MS = 30 * 60 * 1000          # 30 minutes (matches TS default)
_DEFAULT_MAX_AGG_CHARS = 1_000_000        # 1 MB aggregated output cap
_DEFAULT_TAIL_CHARS = 2_000               # tail buffer size for quick preview
_SWEEP_INTERVAL_SECS = 60.0


@dataclass
class FinishedSession:
    """A completed background session (mirrors TS FinishedSession)."""
    id: str
    process_id: str
    aggregated: str
    tail: str
    exit_code: int | None
    exit_signal: str | None
    backgrounded: bool
    created_at_ms: int
    finished_at_ms: int


@dataclass
class ProcessSession:
    """
    A live or recently-finished background process session.
    Mirrors TS ProcessSession in bash-process-registry.ts.
    """
    id: str                                   # unique session slug
    process_id: str                           # user-supplied or auto-generated name
    process: asyncio.subprocess.Process
    backgrounded: bool = False               # True once LLM yielded control
    aggregated: str = ""                     # full output (capped at max_agg_chars)
    tail: str = ""                           # last _DEFAULT_TAIL_CHARS of output
    pending_stdout: list[str] = field(default_factory=list)   # drainable since last poll
    pending_stderr: list[str] = field(default_factory=list)
    exited: bool = False
    exit_code: int | None = None
    exit_signal: str | None = None
    created_at_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    max_agg_chars: int = _DEFAULT_MAX_AGG_CHARS

    def append_output(self, data: str, is_stderr: bool = False) -> None:
        """Append new output data to aggregated buffer and pending buffers."""
        if is_stderr:
            self.pending_stderr.append(data)
        else:
            self.pending_stdout.append(data)
        self.aggregated += data
        if len(self.aggregated) > self.max_agg_chars:
            self.aggregated = self.aggregated[-self.max_agg_chars:]
        self.tail += data
        if len(self.tail) > _DEFAULT_TAIL_CHARS:
            self.tail = self.tail[-_DEFAULT_TAIL_CHARS:]

    def drain_pending(self) -> tuple[str, str]:
        """Drain and return pending stdout/stderr since last poll."""
        stdout = "".join(self.pending_stdout)
        stderr = "".join(self.pending_stderr)
        self.pending_stdout.clear()
        self.pending_stderr.clear()
        return stdout, stderr

    def mark_finished(self, exit_code: int | None, exit_signal: str | None) -> None:
        self.exited = True
        self.exit_code = exit_code
        self.exit_signal = exit_signal


class BashProcessRegistry:
    """
    In-memory registry for background shell processes.
    Mirrors TS bash-process-registry.ts (two-map design: running + finished).
    """

    def __init__(self, ttl_ms: int = _DEFAULT_TTL_MS) -> None:
        self._ttl_ms = ttl_ms
        self._running: dict[str, ProcessSession] = {}
        self._finished: dict[str, FinishedSession] = {}
        self._sweep_task: asyncio.Task | None = None

    # ── Lifecycle ──────────────────────────────────────────────────────

    def start_sweeper(self) -> None:
        """Start background TTL sweeper task."""
        if self._sweep_task is None or self._sweep_task.done():
            self._sweep_task = asyncio.create_task(self._sweep_loop())

    async def _sweep_loop(self) -> None:
        while True:
            await asyncio.sleep(_SWEEP_INTERVAL_SECS)
            self._prune_expired()

    def _prune_expired(self) -> None:
        now_ms = int(time.time() * 1000)
        expired = [
            sid for sid, s in self._finished.items()
            if now_ms - s.finished_at_ms > self._ttl_ms
        ]
        for sid in expired:
            del self._finished[sid]

    # ── Session creation ───────────────────────────────────────────────

    def create_session(
        self,
        process_id: str | None,
        process: asyncio.subprocess.Process,
    ) -> ProcessSession:
        """Create and register a new session for a launched process."""
        session_id = f"{process_id or 'proc'}-{uuid.uuid4().hex[:8]}"
        session = ProcessSession(
            id=session_id,
            process_id=process_id or session_id,
            process=process,
        )
        self._running[session_id] = session
        return session

    def mark_backgrounded(self, session_id: str) -> None:
        """Mark a session as backgrounded (LLM has yielded control)."""
        if session_id in self._running:
            self._running[session_id].backgrounded = True

    def finish_session(self, session_id: str, exit_code: int | None, exit_signal: str | None) -> None:
        """Move a session from running → finished."""
        session = self._running.pop(session_id, None)
        if session is None:
            return
        session.mark_finished(exit_code, exit_signal)
        finished = FinishedSession(
            id=session_id,
            process_id=session.process_id,
            aggregated=session.aggregated,
            tail=session.tail,
            exit_code=exit_code,
            exit_signal=exit_signal,
            backgrounded=session.backgrounded,
            created_at_ms=session.created_at_ms,
            finished_at_ms=int(time.time() * 1000),
        )
        self._finished[session_id] = finished

    # ── Lookups ────────────────────────────────────────────────────────

    def get_running(self, session_id: str) -> ProcessSession | None:
        return self._running.get(session_id)

    def get_finished(self, session_id: str) -> FinishedSession | None:
        return self._finished.get(session_id)

    def get_any(self, session_id: str) -> ProcessSession | FinishedSession | None:
        return self._running.get(session_id) or self._finished.get(session_id)

    def list_running(self) -> list[ProcessSession]:
        """Return only backgrounded running sessions (visible to `process list`)."""
        return [s for s in self._running.values() if s.backgrounded]

    def list_all(self) -> list[ProcessSession | FinishedSession]:
        result: list[Any] = list(self._running.values())
        result.extend(self._finished.values())
        return result

    # ── Mutations ──────────────────────────────────────────────────────

    async def kill_session(self, session_id: str) -> bool:
        """Kill a running session (SIGTERM → SIGKILL)."""
        session = self._running.get(session_id)
        if session is None:
            return False
        try:
            session.process.terminate()
            try:
                await asyncio.wait_for(session.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                session.process.kill()
                await session.process.wait()
        except ProcessLookupError:
            pass
        exit_code = session.process.returncode
        self.finish_session(session_id, exit_code, "SIGKILL" if exit_code == -9 else "SIGTERM")
        return True

    def remove_session(self, session_id: str) -> bool:
        """Remove a finished session from the registry."""
        if session_id in self._finished:
            del self._finished[session_id]
            return True
        return False

    def clear_all_finished(self) -> int:
        """Remove all finished sessions. Returns count removed."""
        count = len(self._finished)
        self._finished.clear()
        return count


# ── Module-level singleton ─────────────────────────────────────────────────────

_registry: BashProcessRegistry | None = None


def get_process_registry() -> BashProcessRegistry:
    """Get the module-level process registry singleton."""
    global _registry
    if _registry is None:
        _registry = BashProcessRegistry()
    return _registry


__all__ = [
    "ProcessSession",
    "FinishedSession",
    "BashProcessRegistry",
    "get_process_registry",
]
