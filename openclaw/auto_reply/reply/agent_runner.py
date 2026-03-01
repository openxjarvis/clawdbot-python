"""Agent runner orchestration for the auto-reply flow.

Mirrors TypeScript:
- ``openclaw/src/auto-reply/reply/agent-runner.ts``
- ``openclaw/src/auto-reply/reply/get-reply-run.ts`` (runPreparedReply)
- ``openclaw/src/auto-reply/reply/agent-runner-execution.ts``

Provides the high-level ``run_prepared_reply`` function that the channel
message handler calls.  It resolves the queue action and then either
steers, enqueues a followup, or starts a new agent turn — always
returning immediately (fire-and-forget semantics).
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)

# Agent run timeout — mirrors TS resolveAgentTimeoutMs default
DEFAULT_AGENT_TIMEOUT_MS = 10 * 60 * 1000  # 10 minutes


# ---------------------------------------------------------------------------
# ReplyContext — shared context for a message dispatch cycle
# ---------------------------------------------------------------------------

@dataclass
class ReplyContext:
    """Context shared across a single inbound-message dispatch cycle."""

    session_id: str
    session_key: str
    message_text: str
    runtime: Any                          # PiAgentRuntime
    session: Any                          # openclaw Session
    tools: list[Any]
    channel_send: Callable[..., Awaitable[None]]  # (text, target, **kw) -> None
    chat_target: Any                      # channel-specific target (chat_id etc.)
    channel_id: str
    reply_to_id: Any | None = None
    queue_settings: Any | None = None    # QueueSettings or None
    images: list[str] | None = None
    system_prompt: str | None = None
    originating_channel: str | None = None
    originating_to: Any | None = None
    typing_ctrl: Any | None = None       # TypingController or None
    timeout_ms: int = DEFAULT_AGENT_TIMEOUT_MS
    abort_event: asyncio.Event | None = None  # set to abort mid-run


# ---------------------------------------------------------------------------
# run_prepared_reply — mirrors TS runPreparedReply
# ---------------------------------------------------------------------------

async def run_prepared_reply(ctx: ReplyContext) -> None:
    """Route an inbound message to the agent according to the queue mode.

    Returns immediately (fire-and-forget).  Actual agent execution happens
    in background tasks via the session command lane.

    Mirrors TS ``runPreparedReply`` / ``runReplyAgent``.
    """
    from openclaw.auto_reply.reply.queue_policy import resolve_active_run_queue_action
    from openclaw.auto_reply.reply.queue import QueueSettings, enqueue_followup_run, FollowupRun

    queue_settings: Any = ctx.queue_settings or QueueSettings()
    action = resolve_active_run_queue_action(
        ctx.session_id,
        queue_settings,
    )

    logger.debug(
        "run_prepared_reply: session=%s action=%s", ctx.session_id[:8], action
    )

    if action == "drop":
        logger.debug("run_prepared_reply: dropping message (heartbeat or explicit drop)")
        if ctx.typing_ctrl:
            ctx.typing_ctrl.mark_run_complete()
            ctx.typing_ctrl.mark_dispatch_idle()
        return

    if action == "steer":
        from openclaw.agents.pi_embedded import queue_embedded_pi_message
        steered = queue_embedded_pi_message(ctx.session_id, ctx.message_text)
        if steered:
            logger.info(
                "run_prepared_reply: steered message into active run for %s",
                ctx.session_id[:8],
            )
            if ctx.typing_ctrl:
                ctx.typing_ctrl.mark_run_complete()
                ctx.typing_ctrl.mark_dispatch_idle()
            return
        # Steer failed (not streaming) — fall through to enqueue
        action = "enqueue-followup"

    if action == "interrupt":
        from openclaw.agents.pi_embedded import abort_embedded_pi_run
        from openclaw.auto_reply.reply.queue import clear_session_queues
        abort_embedded_pi_run(ctx.session_id)
        clear_session_queues([ctx.session_key])
        logger.info(
            "run_prepared_reply: interrupted active run for %s",
            ctx.session_id[:8],
        )
        # After abort, run immediately (fall through to "run-now")
        action = "run-now"

    if action == "enqueue-followup":
        run = FollowupRun(
            prompt=ctx.message_text,
            run={},
            originating_channel=ctx.originating_channel or ctx.channel_id,
            originating_to=str(ctx.originating_to or ctx.chat_target),
        )
        added = enqueue_followup_run(ctx.session_key, run, queue_settings)
        if added:
            logger.info(
                "run_prepared_reply: enqueued followup for %s (mode=%s)",
                ctx.session_id[:8],
                queue_settings.mode,
            )
        else:
            logger.debug("run_prepared_reply: followup deduplicated or dropped")
        if ctx.typing_ctrl:
            ctx.typing_ctrl.mark_run_complete()
            ctx.typing_ctrl.mark_dispatch_idle()
        return

    # action == "run-now": fire and forget
    asyncio.ensure_future(_run_agent_now(ctx))


async def _run_agent_now(ctx: ReplyContext) -> None:
    """Execute an agent turn and deliver the response.  Fire-and-forget.

    Mirrors TS ``runReplyAgent`` + ``runAgentTurnWithFallback``.
    """
    from openclaw.auto_reply.reply.followup_runner import finalize_with_followup

    run_id = str(uuid.uuid4())
    try:
        # Check abort before starting
        if ctx.abort_event and ctx.abort_event.is_set():
            logger.info("_run_agent_now: aborted before start for session %s", ctx.session_id[:8])
            return

        timeout_s = (ctx.timeout_ms or DEFAULT_AGENT_TIMEOUT_MS) / 1000.0

        try:
            response_text, has_error = await asyncio.wait_for(
                _execute_agent_turn(ctx, run_id),
                timeout=timeout_s,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "_run_agent_now: timed out after %.0fs for session %s",
                timeout_s,
                ctx.session_id[:8],
            )
            # Abort the active run
            from openclaw.agents.pi_embedded import abort_embedded_pi_run
            abort_embedded_pi_run(ctx.session_id)
            return

        await _deliver_response(ctx, response_text, has_error)

    except asyncio.CancelledError:
        logger.info("_run_agent_now: cancelled for session %s", ctx.session_id[:8])
        raise
    except Exception as exc:
        logger.error("_run_agent_now: error for session %s: %s", ctx.session_id[:8], exc, exc_info=True)
        try:
            await ctx.channel_send(
                f"Sorry, I encountered an error: {str(exc)[:100]}",
                ctx.chat_target,
            )
        except Exception:
            pass
    finally:
        if ctx.typing_ctrl:
            ctx.typing_ctrl.mark_run_complete()
            ctx.typing_ctrl.mark_dispatch_idle()
        # Schedule followup drain — mirrors TS finalizeWithFollowup
        finalize_with_followup(ctx)


async def _execute_agent_turn(
    ctx: ReplyContext,
    run_id: str,
) -> tuple[str, bool]:
    """Run one agent turn and collect the response.

    Returns (response_text, has_error).
    Uses ``run_agent_turn_with_fallback`` for compaction + transient retry.
    """
    from openclaw.auto_reply.reply.agent_runner_execution import run_agent_turn_with_fallback

    return await run_agent_turn_with_fallback(
        ctx.runtime,
        ctx.session,
        ctx.message_text,
        tools=ctx.tools,
        model=None,
        system_prompt=ctx.system_prompt,
        images=ctx.images,
        run_id=run_id,
        session_key=ctx.session_key,
    )


async def _deliver_response(
    ctx: ReplyContext,
    response_text: str,
    has_error: bool,
) -> None:
    """Deliver accumulated response text back to the channel."""
    from openclaw.auto_reply.media_parse import split_media_from_output
    from pathlib import Path

    if not response_text and not has_error:
        return

    if not response_text:
        return

    try:
        media_result = split_media_from_output(response_text)
        display_text = media_result.text if media_result.text is not None else response_text

        if display_text:
            await ctx.channel_send(display_text, ctx.chat_target, reply_to=ctx.reply_to_id)

        # Send media files
        for media_url in ([media_result.media_url] if media_result.media_url else []) + (media_result.media_urls or []):
            if not media_url:
                continue
            try:
                if not media_url.startswith(("http://", "https://", "file://", "/")):
                    candidate = Path.home() / ".openclaw" / "workspace" / media_url
                    if candidate.exists():
                        media_url = str(candidate)
                from openclaw.media.mime import detect_mime, MediaKind, media_kind_from_mime
                mime = detect_mime(media_url)
                kind = media_kind_from_mime(mime)
                media_type = kind.value if kind != MediaKind.UNKNOWN else "document"
                await ctx.channel_send(None, ctx.chat_target, media_url=media_url, media_type=media_type)
            except Exception as me:
                logger.error("Failed to send media %s: %s", media_url, me)

    except Exception as exc:
        logger.error("_deliver_response error: %s", exc, exc_info=True)


__all__ = ["ReplyContext", "run_prepared_reply"]
