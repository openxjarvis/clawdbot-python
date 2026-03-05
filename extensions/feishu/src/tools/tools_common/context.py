"""AsyncLocalStorage equivalent for Feishu tool context.

Mirrors: clawdbot-feishu/src/tools-common/tool-context.ts

Uses Python's contextvars.ContextVar so the active account id propagates
automatically through asyncio tasks spawned during a Feishu message dispatch.
"""
from __future__ import annotations

import contextvars
from contextlib import asynccontextmanager
from typing import AsyncIterator

_feishu_account_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "feishu_account_id", default=None
)


def get_current_feishu_account_id() -> str | None:
    """Return the Feishu account id active in the current async context, or None."""
    return _feishu_account_id.get()


@asynccontextmanager
async def run_with_feishu_tool_context(account_id: str) -> AsyncIterator[None]:
    """Context manager that sets the active Feishu account id for the duration."""
    token = _feishu_account_id.set(account_id)
    try:
        yield
    finally:
        _feishu_account_id.reset(token)
