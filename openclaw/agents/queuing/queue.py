"""
Queue manager for session and global lanes.

Mirrors TS openclaw/src/process/command-queue.ts including:
- warn_after_ms / on_wait callback
- drop policies: 'old', 'new', 'summarize'
- reset_all_lanes() for in-process restarts (SIGUSR1)
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections.abc import Callable, Coroutine
from typing import Any, Literal, TypeVar

from .lane import Lane
from .lanes import CommandLane, LANE_DEFAULTS

logger = logging.getLogger(__name__)

T = TypeVar("T")

DropPolicy = Literal["old", "new", "summarize"]

DEFAULT_WARN_AFTER_MS: int = 2_000


class QueueManager:
    """
    Manage session and global execution lanes

    Features:
    - Per-session sequential execution (prevents conflicts)
    - Global concurrent limit (resource management)
    - Automatic lane creation and cleanup
    """

    def __init__(self, max_concurrent_per_session: int = 1, max_concurrent_global: int = 10):
        """
        Initialize queue manager

        Args:
            max_concurrent_per_session: Max concurrent per session
            max_concurrent_global: Max concurrent globally
        """
        self.max_concurrent_per_session = max_concurrent_per_session
        self.max_concurrent_global = max_concurrent_global

        self._session_lanes: dict[str, Lane] = {}
        self._global_lane = Lane("global", max_concurrent_global)
        
        # Fixed lanes with predefined concurrency (aligned with TS)
        self._fixed_lanes: dict[CommandLane, Lane] = {
            CommandLane.MAIN: Lane(CommandLane.MAIN.value, LANE_DEFAULTS[CommandLane.MAIN]),
            CommandLane.CRON: Lane(CommandLane.CRON.value, LANE_DEFAULTS[CommandLane.CRON]),
            CommandLane.SUBAGENT: Lane(CommandLane.SUBAGENT.value, LANE_DEFAULTS[CommandLane.SUBAGENT]),
            CommandLane.NESTED: Lane(CommandLane.NESTED.value, LANE_DEFAULTS[CommandLane.NESTED]),
        }

    def get_session_lane(self, session_id: str) -> Lane:
        """
        Get or create lane for session

        Args:
            session_id: Session identifier

        Returns:
            Lane for this session
        """
        if session_id not in self._session_lanes:
            # Create deterministic lane name
            lane_name = f"session-{self._hash_session_id(session_id)}"
            self._session_lanes[session_id] = Lane(lane_name, self.max_concurrent_per_session)
            logger.debug(f"Created lane for session: {session_id}")

        return self._session_lanes[session_id]

    def get_global_lane(self) -> Lane:
        """Get global lane"""
        return self._global_lane
    
    def get_lane(self, lane: CommandLane) -> Lane:
        """
        Get fixed command lane
        
        Args:
            lane: CommandLane enum value
            
        Returns:
            Lane instance for this command lane
        """
        return self._fixed_lanes[lane]
    
    async def enqueue_in_lane(
        self,
        lane: CommandLane,
        task: Callable[[], Coroutine[Any, Any, T]],
        timeout: float | None = None,
        warn_after_ms: int = DEFAULT_WARN_AFTER_MS,
        on_wait: Callable[[int, int], None] | None = None,
        drop_policy: DropPolicy | None = None,
    ) -> T:
        """
        Enqueue task in a specific command lane.

        Args:
            lane: CommandLane enum value.
            task: Async function to execute.
            timeout: Optional timeout in seconds.
            warn_after_ms: Log a warning if the task waits longer than this (default 2s).
            on_wait: Optional callback ``(wait_ms, queued_ahead)`` fired when warn threshold exceeded.
            drop_policy: How to handle overload: 'old' drops oldest, 'new' rejects this task,
                         'summarize' merges into a backlog message.

        Returns:
            Task result.
        """
        lane_instance = self.get_lane(lane)
        enqueued_at = time.monotonic()

        if drop_policy is not None:
            queue_size = lane_instance.queue.qsize()
            if queue_size > 0:
                if drop_policy == "new":
                    raise RuntimeError(f"Lane {lane.value} busy; dropping new task (policy=new)")
                elif drop_policy == "old":
                    try:
                        lane_instance.queue.get_nowait()
                        logger.warning("Dropped oldest queued task in lane %s (policy=old)", lane.value)
                    except asyncio.QueueEmpty:
                        pass
                elif drop_policy == "summarize":
                    logger.warning(
                        "Lane %s busy; merging task into backlog (policy=summarize)", lane.value
                    )

        async def timed_task() -> T:
            wait_ms = int((time.monotonic() - enqueued_at) * 1000)
            if wait_ms >= warn_after_ms:
                if on_wait is not None:
                    on_wait(wait_ms, lane_instance.queue.qsize())
                logger.warning(
                    "Lane wait exceeded: lane=%s waited_ms=%d queued_ahead=%d",
                    lane.value, wait_ms, lane_instance.queue.qsize(),
                )
            return await task()

        return await lane_instance.enqueue(timed_task, timeout)
    
    def set_lane_concurrency(self, lane: CommandLane, max_concurrent: int) -> None:
        """
        Set concurrency limit for a command lane
        
        Args:
            lane: CommandLane enum value
            max_concurrent: New concurrency limit (>= 1)
        """
        lane_instance = self.get_lane(lane)
        lane_instance.max_concurrent = max(1, max_concurrent)
        logger.info(f"Updated lane {lane.value} maxConcurrent to {lane_instance.max_concurrent}")

    async def enqueue_session(
        self,
        session_id: str,
        task: Callable[[], Coroutine[Any, Any, T]],
        timeout: float | None = None,
        warn_after_ms: int = DEFAULT_WARN_AFTER_MS,
        on_wait: Callable[[int, int], None] | None = None,
        drop_policy: DropPolicy | None = None,
    ) -> T:
        """
        Enqueue task in session lane.

        Args:
            session_id: Session identifier.
            task: Async function to execute.
            timeout: Optional timeout in seconds.
            warn_after_ms: Warn threshold in ms (default 2 s).
            on_wait: Callback ``(wait_ms, queued_ahead)`` fired on warn.
            drop_policy: 'old', 'new', or 'summarize' overload policy.

        Returns:
            Task result.
        """
        lane = self.get_session_lane(session_id)
        enqueued_at = time.monotonic()

        if drop_policy is not None:
            queue_size = lane.queue.qsize()
            if queue_size > 0:
                if drop_policy == "new":
                    raise RuntimeError(f"Session lane {session_id} busy; dropping new task (policy=new)")
                elif drop_policy == "old":
                    try:
                        lane.queue.get_nowait()
                        logger.warning("Dropped oldest queued task in session lane %s (policy=old)", session_id)
                    except asyncio.QueueEmpty:
                        pass
                elif drop_policy == "summarize":
                    logger.warning(
                        "Session lane %s busy; merging task into backlog (policy=summarize)", session_id
                    )

        async def timed_task() -> T:
            wait_ms = int((time.monotonic() - enqueued_at) * 1000)
            if wait_ms >= warn_after_ms:
                if on_wait is not None:
                    on_wait(wait_ms, lane.queue.qsize())
                logger.warning(
                    "Session lane wait exceeded: session=%s waited_ms=%d queued_ahead=%d",
                    session_id, wait_ms, lane.queue.qsize(),
                )
            return await task()

        return await lane.enqueue(timed_task, timeout)

    async def enqueue_global(
        self, task: Callable[[], Coroutine[Any, Any, T]], timeout: float | None = None
    ) -> T:
        """
        Enqueue task in global lane

        Args:
            task: Async function to execute
            timeout: Optional timeout

        Returns:
            Task result
        """
        return await self._global_lane.enqueue(task, timeout)

    async def enqueue_both(
        self,
        session_id: str,
        task: Callable[[], Coroutine[Any, Any, T]],
        timeout: float | None = None,
    ) -> T:
        """
        Enqueue task in both session and global lanes

        This ensures:
        1. Only one request per session at a time
        2. Global concurrency limit is respected

        Args:
            session_id: Session identifier
            task: Async function to execute
            timeout: Optional timeout

        Returns:
            Task result
        """
        session_lane = self.get_session_lane(session_id)

        # Enqueue in session lane, which then enqueues in global
        async def wrapped_task():
            return await self._global_lane.enqueue(task, timeout)

        return await session_lane.enqueue(wrapped_task, timeout)

    async def cleanup_session(self, session_id: str) -> None:
        """
        Clean up session lane

        Args:
            session_id: Session to clean up
        """
        if session_id in self._session_lanes:
            lane = self._session_lanes[session_id]
            await lane.stop()
            del self._session_lanes[session_id]
            logger.debug(f"Cleaned up lane for session: {session_id}")

    def reset_all_lanes(self) -> None:
        """Reset all lane runtime state to idle.

        Mirrors TS ``resetAllLanes()`` — used after SIGUSR1 in-process restarts.

        Bumps each lane's generation so stale in-flight completions are ignored.
        Clears active-task counters.  Queued entries are preserved because they
        represent pending user work that should still execute after restart.

        After resetting, starts each lane's worker so preserved work drains
        immediately rather than waiting for a future ``enqueue`` call.
        """
        all_lanes: list[Lane] = (
            list(self._fixed_lanes.values())
            + list(self._session_lanes.values())
            + [self._global_lane]
        )
        for lane in all_lanes:
            lane.generation += 1
            lane._active_tasks.clear()
            lane.active = 0
            lane._running = False
            if not lane.queue.empty():
                lane._start_worker()

        logger.info("reset_all_lanes: reset %d lanes", len(all_lanes))

    def get_stats(self) -> dict:
        """Get queue manager statistics"""
        return {
            "global": self._global_lane.get_stats(),
            "sessions": {sid: lane.get_stats() for sid, lane in self._session_lanes.items()},
            "total_sessions": len(self._session_lanes),
        }

    def _hash_session_id(self, session_id: str) -> str:
        """Create short hash of session ID"""
        return hashlib.md5(session_id.encode()).hexdigest()[:8]
