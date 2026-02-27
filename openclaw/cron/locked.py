"""
Per-store-path lock mechanism for cron operations

Matching TypeScript openclaw/src/cron/service/locked.ts
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

T = TypeVar("T")

# Per-store-path lock map (aligned with TS)
_locks: dict[str, asyncio.Lock] = {}


async def locked(
    store_path: str,
    fn: Callable[[], Coroutine[Any, Any, T]]
) -> T:
    """
    Execute function under store-path lock
    
    Ensures that operations on the same store path are serialized,
    preventing concurrent writes and data corruption.
    
    Aligned with TS: openclaw/src/cron/service/locked.ts
    
    Args:
        store_path: Path to the store file
        fn: Async function to execute under lock
        
    Returns:
        Result of fn
    """
    # Get or create lock for this store path
    if store_path not in _locks:
        _locks[store_path] = asyncio.Lock()
    
    lock = _locks[store_path]
    
    async with lock:
        return await fn()
