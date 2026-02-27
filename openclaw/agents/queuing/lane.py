"""
Queue lane for managing concurrent execution
"""
from __future__ import annotations


import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class Lane:
    """
    A queue lane for sequential or limited concurrent execution

    Lanes ensure that tasks are executed in order or with limited
    concurrency, preventing race conditions and managing resources.
    """

    def __init__(self, name: str, max_concurrent: int = 1):
        """
        Initialize lane

        Args:
            name: Lane identifier
            max_concurrent: Maximum concurrent tasks (1 = sequential)
        """
        self.name = name
        self.max_concurrent = max_concurrent
        self.queue: asyncio.Queue = asyncio.Queue()
        self.active = 0
        self._worker_task: asyncio.Task | None = None
        self._running = False
        
        # Generation tracking (aligned with TS) - prevents stale task completions
        self.generation = 0
        self._next_task_id = 1
        self._active_tasks: dict[int, int] = {}  # {task_id: generation}

    async def enqueue(
        self, task: Callable[[], Coroutine[Any, Any, T]], timeout: float | None = None
    ) -> T:
        """
        Enqueue a task for execution

        Args:
            task: Async function to execute
            timeout: Optional timeout in seconds

        Returns:
            Task result
        """
        # Create future for result
        future: asyncio.Future[T] = asyncio.Future()
        
        # Assign task ID and generation
        task_id = self._next_task_id
        self._next_task_id += 1
        generation = self.generation

        # Add to queue with metadata
        await self.queue.put((task, future, task_id, generation))

        # Start worker if not running
        if not self._running:
            self._start_worker()

        # Wait for result
        try:
            if timeout:
                return await asyncio.wait_for(future, timeout=timeout)
            else:
                return await future
        except TimeoutError:
            logger.error(f"Task timed out in lane {self.name}")
            raise

    def _start_worker(self) -> None:
        """Start background worker"""
        if self._worker_task is None or self._worker_task.done():
            self._running = True
            self._worker_task = asyncio.create_task(self._worker())

    async def _worker(self) -> None:
        """Background worker that processes queue"""
        logger.debug(f"Lane {self.name} worker started")

        try:
            while self._running:
                try:
                    # Get next task (with timeout to check _running)
                    task, future, task_id, generation = await asyncio.wait_for(
                        self.queue.get(), timeout=1.0
                    )

                    # Wait if max concurrent reached
                    while self.active >= self.max_concurrent:
                        await asyncio.sleep(0.1)

                    # Register task
                    self._active_tasks[task_id] = generation
                    self.active += 1
                    
                    # Execute task
                    asyncio.create_task(self._execute_task(task, future, task_id, generation))

                except TimeoutError:
                    # Check if queue is empty and no active tasks
                    if self.queue.empty() and self.active == 0:
                        self._running = False
                        break

        except Exception as e:
            logger.error(f"Lane {self.name} worker error: {e}")
        finally:
            logger.debug(f"Lane {self.name} worker stopped")

    async def _execute_task(
        self, 
        task: Callable[[], Coroutine[Any, Any, T]], 
        future: asyncio.Future[T],
        task_id: int,
        generation: int
    ) -> None:
        """
        Execute a single task with generation tracking
        
        Args:
            task: Task to execute
            future: Future to resolve
            task_id: Unique task identifier
            generation: Lane generation when task was enqueued
        """
        try:
            result = await task()
            # Only update state if generation matches (prevents stale completions)
            if self._active_tasks.get(task_id) == generation and not future.done():
                future.set_result(result)
        except Exception as e:
            # Only update state if generation matches
            if self._active_tasks.get(task_id) == generation and not future.done():
                future.set_exception(e)
        finally:
            # Clean up task tracking
            if task_id in self._active_tasks:
                del self._active_tasks[task_id]
            self.active -= 1
            self.queue.task_done()

    async def stop(self) -> None:
        """Stop the worker"""
        self._running = False
        if self._worker_task:
            await self._worker_task

    def reset_generation(self) -> None:
        """
        Reset generation counter (for testing or lane resets)
        
        Increments generation to invalidate all pending tasks.
        Active tasks from old generation will complete but won't update state.
        """
        self.generation += 1
        logger.info(f"Lane {self.name} generation reset to {self.generation}")
    
    def get_stats(self) -> dict:
        """Get lane statistics"""
        return {
            "name": self.name,
            "max_concurrent": self.max_concurrent,
            "active": self.active,
            "queued": self.queue.qsize(),
            "running": self._running,
            "generation": self.generation,
            "active_task_ids": list(self._active_tasks.keys()),
        }
