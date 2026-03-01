"""Typing indicators — start/stop typing notifications during agent execution.

Port of TypeScript:
  openclaw/src/auto-reply/reply/typing.ts       (196 lines)
  openclaw/src/auto-reply/reply/typing-mode.ts

Sends periodic "typing…" notifications to the channel while the agent
is processing. Supports a TTL to prevent typing indicators from running
forever if something goes wrong.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_TYPING_INTERVAL_SECONDS = 6
DEFAULT_TYPING_TTL_MS = 2 * 60_000  # 2 minutes


# ---------------------------------------------------------------------------
# TypingController — mirrors TS TypingController interface
# ---------------------------------------------------------------------------

@dataclass
class TypingControllerConfig:
    on_reply_start: Callable[[], Awaitable[None]] | None = None
    on_cleanup: Callable[[], None] | None = None
    typing_interval_seconds: float = DEFAULT_TYPING_INTERVAL_SECONDS
    typing_ttl_ms: int = DEFAULT_TYPING_TTL_MS
    silent_token: str = "NO_REPLY"


class TypingController:
    """
    Controls typing indicator lifecycle.

    Usage:
        await typing.on_reply_start()   # called when the reply begins
        await typing.start_typing_loop()  # starts periodic typing events
        typing.refresh_typing_ttl()     # called on new text/events
        typing.mark_run_complete()      # agent run finished
        typing.mark_dispatch_idle()     # dispatcher finished sending
        typing.cleanup()                # tear down
    """

    def __init__(self, config: TypingControllerConfig) -> None:
        self._config = config
        self._started = False
        self._active = False
        self._run_complete = False
        self._dispatch_idle = False
        self._sealed = False
        self._typing_task: asyncio.Task | None = None
        self._ttl_task: asyncio.Task | None = None
        self._interval_ms = int(config.typing_interval_seconds * 1000)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def on_reply_start(self) -> None:
        """Called when the reply pipeline starts (before agent execution)."""
        if self._config.on_reply_start:
            try:
                await self._config.on_reply_start()
            except Exception as exc:
                logger.debug(f"typing on_reply_start callback failed: {exc}")

    async def start_typing_loop(self) -> None:
        """Start the periodic typing indicator loop."""
        if self._sealed or self._started:
            return
        self._started = True
        self._active = True
        self._typing_task = asyncio.create_task(self._loop())
        self._ttl_task = asyncio.create_task(self._ttl_cancel())

    async def start_typing_on_text(self, text: str | None = None) -> None:
        """Called on each text delta — refreshes TTL and starts loop if needed."""
        if text and text.strip() == self._config.silent_token:
            return
        self.refresh_typing_ttl()
        if not self._started:
            await self.start_typing_loop()

    def refresh_typing_ttl(self) -> None:
        """Reset the idle TTL timer."""
        if self._sealed:
            return
        if self._ttl_task and not self._ttl_task.done():
            self._ttl_task.cancel()
        if not self._sealed:
            self._ttl_task = asyncio.create_task(self._ttl_cancel())

    def is_active(self) -> bool:
        return self._active and not self._sealed

    def mark_run_complete(self) -> None:
        self._run_complete = True
        self._maybe_cleanup()

    def mark_dispatch_idle(self) -> None:
        self._dispatch_idle = True
        self._maybe_cleanup()

    def cleanup(self) -> None:
        """Tear down all timers and notify channel to stop typing."""
        if self._sealed:
            return
        self._cancel_tasks()
        if self._config.on_cleanup:
            try:
                self._config.on_cleanup()
            except Exception:
                pass
        self._active = False
        self._started = False
        self._run_complete = False
        self._dispatch_idle = False
        self._sealed = True

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _maybe_cleanup(self) -> None:
        """Cleanup if both run and dispatch are done."""
        if self._run_complete and self._dispatch_idle:
            self.cleanup()

    async def _loop(self) -> None:
        """Periodic typing indicator sender."""
        interval_s = self._config.typing_interval_seconds
        while self._active and not self._sealed:
            await asyncio.sleep(interval_s)
            if not self._active or self._sealed:
                break
            if self._config.on_reply_start:
                try:
                    await self._config.on_reply_start()
                except Exception:
                    pass

    async def _ttl_cancel(self) -> None:
        """Auto-cancel after TTL expires."""
        await asyncio.sleep(self._config.typing_ttl_ms / 1000)
        logger.debug("typing: TTL expired, stopping indicator")
        self.cleanup()

    def _cancel_tasks(self) -> None:
        for task in (self._typing_task, self._ttl_task):
            if task and not task.done():
                task.cancel()
        self._typing_task = None
        self._ttl_task = None


# ---------------------------------------------------------------------------
# Factory function (mirrors TS createTypingController)
# ---------------------------------------------------------------------------

def create_typing_controller(
    on_reply_start: Callable[[], Awaitable[None]] | None = None,
    on_cleanup: Callable[[], None] | None = None,
    typing_interval_seconds: float = DEFAULT_TYPING_INTERVAL_SECONDS,
    typing_ttl_ms: int = DEFAULT_TYPING_TTL_MS,
    silent_token: str = "NO_REPLY",
) -> TypingController:
    """Create a typing controller with the given callbacks."""
    return TypingController(TypingControllerConfig(
        on_reply_start=on_reply_start,
        on_cleanup=on_cleanup,
        typing_interval_seconds=typing_interval_seconds,
        typing_ttl_ms=typing_ttl_ms,
        silent_token=silent_token,
    ))


# ---------------------------------------------------------------------------
# TypingSignaler — mirrors TS createTypingSignaler from typing-mode.ts
# ---------------------------------------------------------------------------

SILENT_REPLY_TOKEN = "NO_REPLY"


class TypingSignaler:
    """Wraps a TypingController with mode-aware signal methods.

    Mirrors TS ``createTypingSignaler`` from ``auto-reply/reply/typing-mode.ts``.

    Different typing modes determine when the indicator starts:
    - "instant"  — start immediately when the run begins
    - "message"  — start when the first message block starts
    - "thinking" — start when reasoning/thinking text arrives
    - "never"    — never start
    """

    def __init__(
        self,
        typing: "TypingController",
        mode: str = "instant",
        is_heartbeat: bool = False,
    ) -> None:
        self._typing = typing
        self.mode = mode
        self._disabled = is_heartbeat or mode == "never"
        self._should_start_immediately = mode == "instant"
        self._should_start_on_message = mode == "message"
        self._should_start_on_text = mode in ("instant", "message")
        self._should_start_on_reasoning = mode == "thinking"
        self._has_renderable_text = False

    def _is_renderable(self, text: str | None) -> bool:
        trimmed = (text or "").strip()
        if not trimmed:
            return False
        return trimmed != SILENT_REPLY_TOKEN

    async def signal_run_start(self) -> None:
        """Called at the start of a model run."""
        if self._disabled or not self._should_start_immediately:
            return
        await self._typing.start_typing_loop()

    async def signal_message_start(self) -> None:
        """Called when the first message block begins."""
        if self._disabled or not self._should_start_on_message:
            return
        if not self._has_renderable_text:
            return
        await self._typing.start_typing_loop()

    async def signal_text_delta(self, text: str | None = None) -> None:
        """Called on each text chunk from the model."""
        if self._disabled:
            return
        renderable = self._is_renderable(text)
        if renderable:
            self._has_renderable_text = True
        elif (text or "").strip():
            return
        if self._should_start_on_text:
            await self._typing.start_typing_on_text(text)
            return
        if self._should_start_on_reasoning:
            if not self._typing.is_active():
                await self._typing.start_typing_loop()
            self._typing.refresh_typing_ttl()

    async def signal_reasoning_delta(self) -> None:
        """Called on reasoning/thinking text chunks."""
        if self._disabled or not self._should_start_on_reasoning:
            return
        if not self._has_renderable_text:
            return
        await self._typing.start_typing_loop()
        self._typing.refresh_typing_ttl()

    async def signal_tool_start(self) -> None:
        """Called when a tool call begins — keeps indicator alive during tool use."""
        if self._disabled:
            return
        if not self._typing.is_active():
            await self._typing.start_typing_loop()
            self._typing.refresh_typing_ttl()
            return
        self._typing.refresh_typing_ttl()


def create_typing_signaler(
    typing: "TypingController",
    mode: str = "instant",
    is_heartbeat: bool = False,
) -> TypingSignaler:
    """Create a TypingSignaler wrapping *typing* for the given *mode*.

    Mirrors TS ``createTypingSignaler`` from ``typing-mode.ts``.
    """
    return TypingSignaler(typing=typing, mode=mode, is_heartbeat=is_heartbeat)


# ---------------------------------------------------------------------------
# Typing mode resolution (mirrors typing-mode.ts)
# ---------------------------------------------------------------------------

_TYPING_MODES = {"always", "never", "auto"}


def resolve_typing_mode(cfg: dict | None, channel: str | None = None) -> str:
    """Resolve the typing indicator mode for a channel."""
    cfg = cfg or {}
    if channel:
        channel_cfg = cfg.get(channel.lower()) or {}
        mode = channel_cfg.get("typingMode") or channel_cfg.get("typing_mode")
        if mode and mode in _TYPING_MODES:
            return mode
    agents = cfg.get("agents", {}).get("defaults", {})
    mode = agents.get("typingMode") or agents.get("typing_mode")
    if mode and mode in _TYPING_MODES:
        return mode
    session = cfg.get("session", {})
    mode = session.get("typingMode") or session.get("typing_mode")
    if mode and mode in _TYPING_MODES:
        return mode
    return "auto"


def resolve_typing_interval_seconds(cfg: dict | None, channel: str | None = None) -> float:
    """Resolve typing interval in seconds from config."""
    cfg = cfg or {}
    if channel:
        channel_cfg = cfg.get(channel.lower()) or {}
        v = channel_cfg.get("typingIntervalSeconds") or channel_cfg.get("typing_interval_seconds")
        if isinstance(v, (int, float)) and v > 0:
            return float(v)
    agents = cfg.get("agents", {}).get("defaults", {})
    v = agents.get("typingIntervalSeconds") or agents.get("typing_interval_seconds")
    if isinstance(v, (int, float)) and v > 0:
        return float(v)
    session = cfg.get("session", {})
    v = session.get("typingIntervalSeconds") or session.get("typing_interval_seconds")
    if isinstance(v, (int, float)) and v > 0:
        return float(v)
    return float(DEFAULT_TYPING_INTERVAL_SECONDS)
