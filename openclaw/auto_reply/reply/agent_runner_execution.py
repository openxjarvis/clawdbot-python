"""Agent runner execution with fallback and error recovery.

Mirrors TypeScript ``openclaw/src/auto-reply/reply/agent-runner-execution.ts``.

Provides ``run_agent_turn_with_fallback`` that wraps ``PiAgentRuntime.run_turn``
with:
- Model fallback on failure (already handled in PiAgentRuntime, but surfaced here)
- Session corruption recovery after compaction failures
- Session recovery after role-ordering conflicts (Gemini)
- Transient HTTP error retry (up to 3 attempts with backoff)
- Structured error events
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, AsyncIterator

logger = logging.getLogger(__name__)

# Maximum transient HTTP retry attempts
MAX_TRANSIENT_RETRIES = 3

# Patterns that indicate a transient server error worth retrying
_TRANSIENT_HTTP_PATTERNS = [
    re.compile(r"\b(500|502|503|504)\b"),
    re.compile(r"server error", re.IGNORECASE),
    re.compile(r"internal error", re.IGNORECASE),
    re.compile(r"service unavailable", re.IGNORECASE),
    re.compile(r"overloaded", re.IGNORECASE),
    re.compile(r"try again", re.IGNORECASE),
]

# Patterns indicating compaction failure
_COMPACTION_FAILURE_PATTERNS = [
    re.compile(r"compaction", re.IGNORECASE),
    re.compile(r"conversation too long", re.IGNORECASE),
    re.compile(r"context.*overflow", re.IGNORECASE),
    re.compile(r"context.*too large", re.IGNORECASE),
]

# Patterns indicating role-ordering / function-call conflict
_ROLE_ORDER_PATTERNS = [
    re.compile(r"role.*ordering", re.IGNORECASE),
    re.compile(r"function.*call.*order", re.IGNORECASE),
    re.compile(r"invalid.*role.*sequence", re.IGNORECASE),
    re.compile(r"INVALID_ARGUMENT.*function", re.IGNORECASE),
]


def _is_transient_http_error(exc: BaseException) -> bool:
    msg = str(exc)
    return any(p.search(msg) for p in _TRANSIENT_HTTP_PATTERNS)


def _is_compaction_failure(exc: BaseException) -> bool:
    msg = str(exc)
    return any(p.search(msg) for p in _COMPACTION_FAILURE_PATTERNS)


def _is_role_ordering_conflict(exc: BaseException) -> bool:
    msg = str(exc)
    return any(p.search(msg) for p in _ROLE_ORDER_PATTERNS)


async def reset_session_after_compaction_failure(
    runtime: Any, session_id: str
) -> None:
    """Evict the pi_session pool entry so the next turn starts fresh.

    Mirrors TS ``resetSessionAfterCompactionFailure``.
    """
    try:
        if hasattr(runtime, "evict_session"):
            runtime.evict_session(session_id)
            logger.info("reset_session_after_compaction_failure: evicted session %s", session_id[:8])
    except Exception as exc:
        logger.debug("reset_session_after_compaction_failure: error: %s", exc)


async def reset_session_after_role_ordering_conflict(
    runtime: Any, session_id: str
) -> None:
    """Evict the pi_session pool entry after a Gemini role-ordering error.

    Mirrors TS ``resetSessionAfterRoleOrderingConflict``.
    """
    try:
        if hasattr(runtime, "evict_session"):
            runtime.evict_session(session_id)
            logger.info("reset_session_after_role_ordering_conflict: evicted session %s", session_id[:8])
    except Exception as exc:
        logger.debug("reset_session_after_role_ordering_conflict: error: %s", exc)


async def run_agent_turn_with_fallback(
    runtime: Any,
    session: Any,
    message: str,
    *,
    tools: list[Any] | None = None,
    model: str | None = None,
    system_prompt: str | None = None,
    images: list[str] | None = None,
    run_id: str | None = None,
    session_key: str | None = None,
    typing_signaler: Any | None = None,  # TypingSignaler | None
) -> tuple[str, bool]:
    """Execute an agent turn with automatic retry on transient errors.

    Returns ``(response_text, has_error)``.

    Mirrors TS ``runAgentTurnWithFallback``.

    Error handling priority:
    1. Transient HTTP errors (500/502/503/504): retry up to MAX_TRANSIENT_RETRIES.
    2. Compaction failures: reset session, re-raise.
    3. Role-ordering conflicts (Gemini): reset session, re-raise.
    4. Other errors: re-raise immediately.
    """
    from openclaw.events import EventType

    session_id = getattr(session, "session_id", "") or ""
    response_text = ""
    has_error = False
    attempt = 0

    while attempt < MAX_TRANSIENT_RETRIES:
        attempt += 1
        response_text = ""
        has_error = False

        # Signal run start for typing indicator (mode=instant starts immediately)
        if typing_signaler:
            try:
                await typing_signaler.signal_run_start()
            except Exception:
                pass

        try:
            async for event in runtime.run_turn(
                session,
                message,
                tools=tools,
                model=model,
                system_prompt=system_prompt,
                images=images,
                run_id=run_id,
                session_key=session_key,
            ):
                try:
                    evt_type = getattr(event, "type", "")
                    event_data: dict = {}
                    if hasattr(event, "data") and isinstance(event.data, dict):
                        event_data = event.data

                    if evt_type in (EventType.TEXT, EventType.TEXT_DELTA, "text", "text_delta"):
                        chunk = event_data.get("text") or event_data.get("delta") or ""
                        if isinstance(chunk, dict):
                            chunk = chunk.get("text", "")
                        if chunk:
                            response_text += str(chunk)
                            # Refresh typing TTL as text arrives — mirrors TS
                            # typing.startTypingOnText() on each text delta
                            if typing_signaler:
                                try:
                                    await typing_signaler.signal_text_delta(str(chunk))
                                except Exception:
                                    pass
                    elif evt_type in (EventType.AGENT_TOOL_USE, "tool_use", "tool_call", "agent.tool_use"):
                        # Tool execution started — keep typing indicator alive
                        if typing_signaler:
                            try:
                                await typing_signaler.signal_tool_start()
                            except Exception:
                                pass
                    elif evt_type in (EventType.ERROR, "error", "agent.error"):
                        err_msg = event_data.get("message", str(event_data))
                        logger.error("run_agent_turn_with_fallback: agent error: %s", err_msg)
                        has_error = True
                except Exception as evt_exc:
                    logger.error("Event processing error: %s", evt_exc)
                    has_error = True

            return response_text, has_error

        except asyncio.CancelledError:
            raise

        except Exception as exc:
            if _is_compaction_failure(exc):
                logger.warning(
                    "Compaction failure in session %s — resetting session: %s",
                    session_id[:8], exc,
                )
                await reset_session_after_compaction_failure(runtime, session_id)
                raise

            if _is_role_ordering_conflict(exc):
                logger.warning(
                    "Role-ordering conflict in session %s — resetting session: %s",
                    session_id[:8], exc,
                )
                await reset_session_after_role_ordering_conflict(runtime, session_id)
                raise

            if _is_transient_http_error(exc) and attempt < MAX_TRANSIENT_RETRIES:
                backoff = 2.0 ** (attempt - 1)
                logger.warning(
                    "Transient HTTP error (attempt %d/%d) — retrying in %.1fs: %s",
                    attempt, MAX_TRANSIENT_RETRIES, backoff, exc,
                )
                await asyncio.sleep(backoff)
                continue

            # Non-retryable error
            raise

    # Should not reach here, but return error state if we somehow exit the loop
    return response_text, True


__all__ = [
    "run_agent_turn_with_fallback",
    "reset_session_after_compaction_failure",
    "reset_session_after_role_ordering_conflict",
]
