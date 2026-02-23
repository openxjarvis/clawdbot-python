"""Channel typing callbacks — mirrors src/channels/typing.ts"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable


@dataclass
class TypingCallbacks:
    on_reply_start: Callable[[], Awaitable[None]]
    on_idle: Callable[[], None] | None = None
    on_cleanup: Callable[[], None] | None = None


def create_typing_callbacks(
    *,
    start: Callable[[], Awaitable[None]],
    stop: Callable[[], Awaitable[None]] | None = None,
    on_start_error: Callable[[object], None],
    on_stop_error: Callable[[object], None] | None = None,
) -> TypingCallbacks:
    async def on_reply_start() -> None:
        try:
            await start()
        except Exception as err:
            on_start_error(err)

    fire_stop: Callable[[], None] | None = None
    if stop is not None:
        _stop = stop

        def fire_stop() -> None:
            import asyncio

            err_handler = on_stop_error or on_start_error

            async def _do() -> None:
                try:
                    await _stop()
                except Exception as e:
                    err_handler(e)

            asyncio.ensure_future(_do())

    return TypingCallbacks(
        on_reply_start=on_reply_start,
        on_idle=fire_stop,
        on_cleanup=fire_stop,
    )
