"""Draft stream loop — mirrors src/channels/draft-stream-loop.ts"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Awaitable, Callable


@dataclass
class DraftStreamLoop:
    _throttle_ms: float
    _is_stopped: Callable[[], bool]
    _send_or_edit: Callable[[str], Awaitable[bool | None]]

    _last_sent_at: float = field(default=0.0, init=False)
    _pending_text: str = field(default="", init=False)
    _in_flight: asyncio.Task | None = field(default=None, init=False)
    _timer: asyncio.TimerHandle | None = field(default=None, init=False)

    def update(self, text: str) -> None:
        self._pending_text = text
        if self._timer is None and not self._in_flight:
            loop = asyncio.get_event_loop()
            self._timer = loop.call_later(
                self._throttle_ms / 1000.0,
                lambda: asyncio.ensure_future(self._do_flush()),
            )

    async def flush(self) -> None:
        if self._timer:
            self._timer.cancel()
            self._timer = None
        await self._do_flush()

    async def _do_flush(self) -> None:
        while not self._is_stopped():
            if self._in_flight:
                try:
                    await self._in_flight
                except Exception:
                    pass
                self._in_flight = None
                continue

            text = self._pending_text
            if not text.strip():
                self._pending_text = ""
                return

            self._pending_text = ""
            task = asyncio.ensure_future(self._send_or_edit(text))
            self._in_flight = task
            try:
                sent = await task
            except Exception:
                sent = None
            finally:
                if self._in_flight is task:
                    self._in_flight = None

            if sent is False:
                self._pending_text = text
                return

            self._last_sent_at = asyncio.get_event_loop().time() * 1000
            if not self._pending_text:
                return

    def stop(self) -> None:
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def reset_pending(self) -> None:
        self._pending_text = ""

    async def wait_for_in_flight(self) -> None:
        if self._in_flight:
            try:
                await self._in_flight
            except Exception:
                pass
            self._in_flight = None


def create_draft_stream_loop(
    *,
    throttle_ms: float,
    is_stopped: Callable[[], bool],
    send_or_edit_stream_message: Callable[[str], Awaitable[bool | None]],
) -> DraftStreamLoop:
    return DraftStreamLoop(
        _throttle_ms=throttle_ms,
        _is_stopped=is_stopped,
        _send_or_edit=send_or_edit_stream_message,
    )
