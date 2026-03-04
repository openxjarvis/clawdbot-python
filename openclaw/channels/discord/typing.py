"""
Discord typing indicator — mirrors src/discord/monitor/typing.ts
Uses discord.py channel.typing() context manager.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

logger = logging.getLogger(__name__)


async def send_typing(client: Any, channel_id: int | str) -> None:
    """
    Trigger a single typing indicator in the given channel.
    Wraps POST /channels/{id}/typing — lasts ~10 seconds on Discord.
    Mirrors sendTyping() in src/discord/monitor/typing.ts.

    Uses trigger_typing() (a one-shot POST) instead of the context-manager
    form of typing() to avoid leaving the async context manager open.
    """
    try:
        ch = client.get_channel(int(channel_id))
        if ch is None:
            ch = await client.fetch_channel(int(channel_id))
        if hasattr(ch, "trigger_typing"):
            await ch.trigger_typing()
        elif hasattr(ch, "typing"):
            # Fallback: use the context manager correctly via a no-op body
            async with ch.typing():
                pass
    except Exception as exc:
        logger.debug("[discord][typing] Failed to send typing: %s", exc)


@asynccontextmanager
async def typing_context(client: Any, channel_id: int | str):
    """
    Async context manager that keeps typing active for the duration.
    Usage::

        async with typing_context(client, channel_id):
            await long_running_agent_call()
    """
    try:
        ch = client.get_channel(int(channel_id))
        if ch is None:
            ch = await client.fetch_channel(int(channel_id))
        if hasattr(ch, "typing"):
            async with ch.typing():
                yield
            return
    except Exception as exc:
        logger.debug("[discord][typing] typing_context error: %s", exc)
    yield
