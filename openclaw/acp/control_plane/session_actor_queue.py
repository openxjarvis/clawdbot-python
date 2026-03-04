"""Per-session serialized async queue — mirrors src/acp/control-plane/session-actor-queue.ts

Wraps a per-key async queue so that operations on the same actor key (session)
are serialized in FIFO order, while operations on different keys run in parallel.
This is the Python equivalent of the TS KeyedAsyncQueue adapter.
"""
from __future__ import annotations

import asyncio
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class SessionActorQueue:
    """
    Serializes async operations per actor key (session).

    Usage:
        queue = SessionActorQueue()
        result = await queue.run("session-key-abc", my_coroutine_fn)
    """

    def __init__(self) -> None:
        # Maps actor key → tail task (the last-enqueued coroutine)
        self._tails: dict[str, asyncio.Task] = {}
        # pending counts per actor key
        self._pending: dict[str, int] = {}

    def get_total_pending_count(self) -> int:
        return sum(self._pending.values())

    def get_pending_count_for_session(self, actor_key: str) -> int:
        return self._pending.get(actor_key, 0)

    async def run(self, actor_key: str, op: Callable[[], Any]) -> Any:
        """
        Enqueue an operation for actor_key.  Returns the result of op().

        All operations for the same actor_key are serialized; operations for
        different keys run concurrently.
        """
        prev_tail = self._tails.get(actor_key)
        self._pending[actor_key] = self._pending.get(actor_key, 0) + 1

        loop = asyncio.get_running_loop()
        result_future: asyncio.Future = loop.create_future()

        async def _run_after_prev() -> None:
            if prev_tail and not prev_tail.done():
                try:
                    await prev_tail
                except Exception:
                    pass
            try:
                value = await op()
                if not result_future.done():
                    result_future.set_result(value)
            except Exception as exc:
                if not result_future.done():
                    result_future.set_exception(exc)
            finally:
                remaining = self._pending.get(actor_key, 1) - 1
                if remaining <= 0:
                    self._pending.pop(actor_key, None)
                else:
                    self._pending[actor_key] = remaining

        task: asyncio.Task = asyncio.create_task(_run_after_prev())
        self._tails[actor_key] = task

        # Clean up stale tail reference when the task completes
        def _on_done(t: asyncio.Task) -> None:
            if self._tails.get(actor_key) is t:
                self._tails.pop(actor_key, None)

        task.add_done_callback(_on_done)

        return await result_future
