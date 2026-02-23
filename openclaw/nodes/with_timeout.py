"""Async timeout utility — mirrors src/node-host/with-timeout.ts"""
from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, TypeVar

T = TypeVar("T")


async def with_timeout(
    work: Callable[[Any], Awaitable[T]],
    timeout_ms: int | float | None = None,
    label: str | None = None,
) -> T:
    """Run an async callable with optional timeout.

    Mirrors withTimeout() from node-host/with-timeout.ts.

    :param work: Async callable that accepts an optional cancel signal (None in Python).
    :param timeout_ms: Timeout in milliseconds. None means no timeout.
    :param label: Label for timeout error messages.
    :raises asyncio.TimeoutError: if timeout_ms is exceeded.
    """
    resolved: float | None = None
    if isinstance(timeout_ms, (int, float)) and timeout_ms > 0:
        resolved = max(0.001, timeout_ms / 1000.0)  # convert ms to seconds

    if resolved is None:
        return await work(None)

    timeout_msg = f"{label or 'request'} timed out"
    try:
        return await asyncio.wait_for(work(None), timeout=resolved)
    except asyncio.TimeoutError:
        raise asyncio.TimeoutError(timeout_msg)
