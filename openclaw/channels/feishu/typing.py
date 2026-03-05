"""Typing indicator for Feishu channel via 'Typing' emoji reaction.

Feishu does not have a native typing indicator API, so we use a special
'Typing' emoji reaction to signal that the bot is processing.

Mirrors TypeScript: extensions/feishu/src/typing.ts
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# Rate-limit error codes that trigger the circuit breaker
_RATE_LIMIT_CODES = {99991400, 99991403, 429}

# Messages older than this are skipped to avoid flooding replays
_MAX_AGE_SECONDS = 2 * 60  # 2 minutes

_TYPING_EMOJI = "Typing"


# ---------------------------------------------------------------------------
# Circuit breaker — per-account
# ---------------------------------------------------------------------------

class _TypingCircuitBreaker:
    """
    Simple circuit breaker for typing reactions.

    Trips when rate-limit errors are seen; resets after a cooldown.
    """

    COOLDOWN_SECONDS = 60.0

    def __init__(self) -> None:
        self._tripped: bool = False
        self._tripped_at: float = 0.0

    @property
    def open(self) -> bool:
        if self._tripped:
            if time.monotonic() - self._tripped_at > self.COOLDOWN_SECONDS:
                self._tripped = False
        return self._tripped

    def trip(self) -> None:
        self._tripped = True
        self._tripped_at = time.monotonic()
        logger.warning("[feishu] Typing indicator circuit breaker tripped — pausing for %ss", self.COOLDOWN_SECONDS)


_circuit_breakers: dict[str, _TypingCircuitBreaker] = {}


def _get_circuit_breaker(account_id: str) -> _TypingCircuitBreaker:
    if account_id not in _circuit_breakers:
        _circuit_breakers[account_id] = _TypingCircuitBreaker()
    return _circuit_breakers[account_id]


# ---------------------------------------------------------------------------
# Reaction add / remove
# ---------------------------------------------------------------------------

async def _add_reaction(client: Any, message_id: str, account_id: str) -> str | None:
    """
    Add 'Typing' emoji reaction to a message.

    Returns the reaction_id (needed to delete it later), or None on failure.
    """
    cb = _get_circuit_breaker(account_id)
    if cb.open:
        return None

    try:
        from lark_oapi.api.im.v1 import CreateMessageReactionRequest, CreateMessageReactionRequestBody
        from lark_oapi.api.im.v1.model import Emoji

        emoji = Emoji.builder().emoji_type(_TYPING_EMOJI).build()
        request = (
            CreateMessageReactionRequest.builder()
            .message_id(message_id)
            .request_body(
                CreateMessageReactionRequestBody.builder()
                .reaction_type(emoji)
                .build()
            )
            .build()
        )

        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.im.v1.message_reaction.create(request),
        )

        if not response.success():
            code = response.code
            if code in _RATE_LIMIT_CODES:
                cb.trip()
            else:
                logger.warning(
                    "[feishu] Failed to add typing reaction to %s: code=%s msg=%s "
                    "(hint: ensure im:message.reaction:write scope is granted)",
                    message_id, code, response.msg,
                )
            return None

        reaction_id = response.data.reaction_id if response.data else None
        logger.debug("[feishu] Added typing reaction to %s -> reaction_id=%s", message_id, reaction_id)
        return reaction_id

    except Exception as e:
        logger.warning("[feishu] Error adding typing reaction to %s: %s", message_id, e)
        return None


async def _remove_reaction(client: Any, message_id: str, reaction_id: str, account_id: str) -> None:
    """Remove the 'Typing' emoji reaction."""
    cb = _get_circuit_breaker(account_id)
    if cb.open:
        return

    try:
        from lark_oapi.api.im.v1 import DeleteMessageReactionRequest

        request = (
            DeleteMessageReactionRequest.builder()
            .message_id(message_id)
            .reaction_id(reaction_id)
            .build()
        )

        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.im.v1.message_reaction.delete(request),
        )

        if not response.success():
            code = response.code
            if code in _RATE_LIMIT_CODES:
                cb.trip()

    except Exception as e:
        logger.debug("[feishu] Error removing typing reaction %s from %s: %s", reaction_id, message_id, e)


# ---------------------------------------------------------------------------
# High-level typing indicator context manager
# ---------------------------------------------------------------------------

class FeishuTypingIndicator:
    """
    Context manager that adds 'Typing' reaction while processing,
    then removes it when done.

    Usage:
        async with FeishuTypingIndicator(client, message_id, message_ts, account_id):
            # process message
            ...
    """

    def __init__(
        self,
        client: Any,
        message_id: str,
        message_timestamp: float,   # Unix timestamp of the original message
        account_id: str,
    ) -> None:
        self._client = client
        self._message_id = message_id
        self._message_ts = message_timestamp
        self._account_id = account_id
        self._reaction_id: str | None = None

    async def __aenter__(self) -> FeishuTypingIndicator:
        # Skip typing indicator for old messages to avoid replay flooding
        age = time.time() - self._message_ts
        if age > _MAX_AGE_SECONDS:
            return self

        self._reaction_id = await _add_reaction(
            self._client, self._message_id, self._account_id
        )
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._reaction_id:
            await _remove_reaction(
                self._client, self._message_id, self._reaction_id, self._account_id
            )
            self._reaction_id = None
