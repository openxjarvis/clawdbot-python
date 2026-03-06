"""Telegram status reactions — lifecycle emoji on the user's inbound message.

Shows the agent's processing state as a reaction on the message the user sent:
  👀  queued   — message received, waiting in queue
  🤔  thinking — agent is generating a response
  🔥  tool     — generic tool running
  👨‍💻  coding   — bash/code tool running
  ⚡  web      — web/search tool running
  👍  done     — reply delivered
  😱  error    — something went wrong
  🥱  stall_soft — no progress for 10s
  😨  stall_hard — no progress for 30s

Mirrors TypeScript:
  src/channels/status-reactions.ts
  src/telegram/status-reaction-variants.ts
  src/telegram/bot-message-context.ts (controller instantiation)
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Default emoji for each state (mirrors TS DEFAULT_EMOJIS)
EMOJI_DEFAULTS: dict[str, str] = {
    "queued":     "👀",
    "thinking":   "🤔",
    "tool":       "🔥",
    "coding":     "👨‍💻",
    "web":        "⚡",
    "done":       "👍",
    "error":      "😱",
    "stall_soft": "🥱",
    "stall_hard": "😨",
}

# Per-state fallback candidates (tried in order when Telegram rejects an emoji).
# Mirrors TS TELEGRAM_STATUS_REACTION_VARIANTS.
_REACTION_VARIANTS: dict[str, list[str]] = {
    "queued":     ["👀", "👍", "🔥"],
    "thinking":   ["🤔", "🤓", "👀"],
    "tool":       ["🔥", "⚡", "👍"],
    "coding":     ["👨‍💻", "🔥", "⚡"],
    "web":        ["⚡", "🔥", "👍"],
    "done":       ["👍", "🎉", "💯"],
    "error":      ["😱", "😨", "🤯"],
    "stall_soft": ["🥱", "😴", "🤔"],
    "stall_hard": ["😨", "😱", "⚡"],
}
_GENERIC_FALLBACKS = ["👍", "👀", "🔥"]

# Tool name → state key mapping
_TOOL_STATE_MAP: dict[str, str] = {
    "bash":   "coding",
    "shell":  "coding",
    "code":   "coding",
    "python": "coding",
    "web":    "web",
    "search": "web",
    "google": "web",
    "browse": "web",
}

# Timing (ms) — mirrors TS DEFAULT_TIMING
_DEBOUNCE_MS = 700
_STALL_SOFT_MS = 10_000
_STALL_HARD_MS = 30_000
_DONE_HOLD_MS = 1_500
_ERROR_HOLD_MS = 2_500


def _resolve_state_for_tool(tool_name: str) -> str:
    """Map a tool name to one of the emoji state keys."""
    name_lower = tool_name.lower()
    for key, state in _TOOL_STATE_MAP.items():
        if key in name_lower:
            return state
    return "tool"


class TelegramStatusReactions:
    """
    Manages a lifecycle emoji reaction on the inbound user message.

    Usage (mirrors TS createStatusReactionController):
        sr = TelegramStatusReactions(bot, chat_id, message_id)
        await sr.set_queued()       # immediately on message arrive
        await sr.set_thinking()     # before agent starts
        await sr.set_tool("bash")   # on each tool-start
        await sr.set_done()         # after reply delivered
        # OR:
        await sr.set_error()        # on failure
    """

    def __init__(
        self,
        bot: Any,
        chat_id: int,
        message_id: int,
        *,
        emojis: dict[str, str] | None = None,
        debounce_ms: int = _DEBOUNCE_MS,
        stall_soft_ms: int = _STALL_SOFT_MS,
        stall_hard_ms: int = _STALL_HARD_MS,
    ) -> None:
        self._bot = bot
        self._chat_id = chat_id
        self._message_id = message_id
        self._emojis = {**EMOJI_DEFAULTS, **(emojis or {})}
        self._debounce_ms = debounce_ms
        self._stall_soft_ms = stall_soft_ms
        self._stall_hard_ms = stall_hard_ms

        # Promise chain — ensures serialized delivery of reactions
        self._chain: asyncio.Future = asyncio.get_event_loop().create_future()
        self._chain.set_result(None)

        # Pending debounce task for intermediate states
        self._pending_task: asyncio.Task | None = None
        # Stall timers
        self._stall_soft_task: asyncio.Task | None = None
        self._stall_hard_task: asyncio.Task | None = None
        # Set True once a terminal state (done/error) is reached
        self._finished = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def set_queued(self) -> None:
        await self._debounce_set("queued")

    async def set_thinking(self) -> None:
        await self._debounce_set("thinking")
        self._restart_stall_timers()

    async def set_tool(self, tool_name: str = "") -> None:
        state = _resolve_state_for_tool(tool_name)
        await self._debounce_set(state)
        self._restart_stall_timers()

    async def set_done(self) -> None:
        if self._finished:
            return
        self._cancel_pending()
        self._cancel_stall_timers()
        self._finished = True
        await self._apply_reaction("done")

    async def set_error(self) -> None:
        if self._finished:
            return
        self._cancel_pending()
        self._cancel_stall_timers()
        self._finished = True
        await self._apply_reaction("error")

    async def clear(self) -> None:
        """Remove the reaction entirely."""
        self._cancel_pending()
        self._cancel_stall_timers()
        self._finished = True
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                lambda: self._bot.set_message_reaction(
                    self._chat_id, self._message_id, []
                ),
            )
        except Exception as exc:
            logger.debug("[tg-status] clear reaction failed: %s", exc)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _debounce_set(self, state: str) -> None:
        """Schedule a reaction update after a debounce delay."""
        if self._finished:
            return
        self._cancel_pending()

        async def _task() -> None:
            await asyncio.sleep(self._debounce_ms / 1000.0)
            if not self._finished:
                await self._apply_reaction(state)

        self._pending_task = asyncio.create_task(_task())

    def _cancel_pending(self) -> None:
        if self._pending_task and not self._pending_task.done():
            self._pending_task.cancel()
        self._pending_task = None

    def _restart_stall_timers(self) -> None:
        """Reset stall timers so they count from the last state change."""
        self._cancel_stall_timers()
        if self._finished:
            return

        async def _stall_soft() -> None:
            await asyncio.sleep(self._stall_soft_ms / 1000.0)
            if not self._finished:
                await self._apply_reaction("stall_soft")

        async def _stall_hard() -> None:
            await asyncio.sleep(self._stall_hard_ms / 1000.0)
            if not self._finished:
                await self._apply_reaction("stall_hard")

        self._stall_soft_task = asyncio.create_task(_stall_soft())
        self._stall_hard_task = asyncio.create_task(_stall_hard())

    def _cancel_stall_timers(self) -> None:
        for task in (self._stall_soft_task, self._stall_hard_task):
            if task and not task.done():
                task.cancel()
        self._stall_soft_task = None
        self._stall_hard_task = None

    async def _apply_reaction(self, state: str) -> None:
        """Send the reaction to Telegram, trying variant fallbacks on rejection."""
        # Build ordered candidate list: overridden emoji first, then variants
        primary = self._emojis.get(state, EMOJI_DEFAULTS.get(state, "👍"))
        variants = _REACTION_VARIANTS.get(state, [])
        candidates: list[str] = []
        if primary not in candidates:
            candidates.append(primary)
        for v in variants:
            if v not in candidates:
                candidates.append(v)
        for fb in _GENERIC_FALLBACKS:
            if fb not in candidates:
                candidates.append(fb)

        for emoji in candidates:
            try:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(
                    None,
                    lambda e=emoji: self._bot.set_message_reaction(
                        self._chat_id,
                        self._message_id,
                        [{"type": "emoji", "emoji": e}],
                        is_big=False,
                    ),
                )
                logger.debug("[tg-status] set reaction '%s' (state=%s)", emoji, state)
                return
            except Exception as exc:
                msg = str(exc).lower()
                # Telegram rejects reactions with "REACTION_INVALID" or "bad request"
                # when the emoji is not in the allowed set for the chat.
                if "reaction" in msg or "bad request" in msg or "invalid" in msg:
                    logger.debug(
                        "[tg-status] emoji '%s' rejected for state=%s, trying next",
                        emoji, state,
                    )
                    continue
                logger.debug("[tg-status] set_message_reaction failed (state=%s): %s", state, exc)
                return
