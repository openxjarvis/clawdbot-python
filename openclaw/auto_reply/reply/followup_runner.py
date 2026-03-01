"""Followup runner — executes queued followup turns after an agent run completes.

Mirrors TypeScript ``openclaw/src/auto-reply/reply/followup-runner.ts``
and the ``finalizeWithFollowup`` / ``scheduleFollowupDrain`` pattern in
``openclaw/src/auto-reply/reply/agent-runner.ts``.

Usage::

    # After an agent run finishes:
    finalize_with_followup(reply_ctx)  # schedules background drain

    # To build a runner manually:
    runner = create_followup_runner(reply_ctx)
    # runner(queued_run) runs a single followup turn
"""
from __future__ import annotations

import asyncio
import logging
from typing import Callable, Awaitable, TYPE_CHECKING

if TYPE_CHECKING:
    from openclaw.auto_reply.reply.agent_runner import ReplyContext
    from openclaw.auto_reply.reply.queue import FollowupRun

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# create_followup_runner — mirrors TS createFollowupRunner
# ---------------------------------------------------------------------------

def create_followup_runner(ctx: "ReplyContext") -> Callable[["FollowupRun"], Awaitable[None]]:
    """Return an async callable that executes a single queued followup run.

    The returned function is passed to ``schedule_followup_drain`` so each
    queued item is processed with full agent execution and channel delivery.

    Mirrors TS ``createFollowupRunner``.
    """
    from openclaw.auto_reply.reply.agent_runner import ReplyContext, _execute_agent_turn, _deliver_response
    from openclaw.auto_reply.reply.queue import FollowupRun
    import uuid

    async def run_followup(queued: FollowupRun) -> None:
        """Execute a single queued followup turn."""
        # Build a ctx variant for the followup run
        followup_ctx = ReplyContext(
            session_id=ctx.session_id,
            session_key=ctx.session_key,
            message_text=queued.prompt,
            runtime=ctx.runtime,
            session=ctx.session,
            tools=ctx.tools,
            channel_send=ctx.channel_send,
            chat_target=queued.originating_to or ctx.chat_target,
            channel_id=queued.originating_channel or ctx.channel_id,
            reply_to_id=ctx.reply_to_id,
            queue_settings=ctx.queue_settings,
            images=None,  # followup images not preserved
            system_prompt=ctx.system_prompt,
            originating_channel=queued.originating_channel or ctx.originating_channel,
            originating_to=queued.originating_to or ctx.originating_to,
            typing_ctrl=None,  # no typing indicator for followups
        )

        run_id = str(uuid.uuid4())
        logger.info(
            "followup_runner: running followup for session %s (prompt=%s…)",
            followup_ctx.session_id[:8],
            queued.prompt[:40],
        )

        try:
            response_text, has_error = await _execute_agent_turn(followup_ctx, run_id)
            if response_text or has_error:
                await _deliver_response(followup_ctx, response_text, has_error)
        except Exception as exc:
            logger.warning(
                "followup_runner: error executing followup for %s: %s",
                followup_ctx.session_id[:8],
                exc,
            )

    return run_followup


# ---------------------------------------------------------------------------
# finalize_with_followup — mirrors TS finalizeWithFollowup
# ---------------------------------------------------------------------------

def finalize_with_followup(ctx: "ReplyContext") -> None:
    """Schedule the followup drain after an agent run completes.

    Call this from every exit path of ``_run_agent_now`` (success or error)
    to ensure queued messages are processed.

    Mirrors TS ``finalizeWithFollowup`` in ``agent-runner.ts``.
    """
    from openclaw.auto_reply.reply.queue import schedule_followup_drain, get_followup_queue_depth

    queue_key = ctx.session_key
    depth = get_followup_queue_depth(queue_key)
    if depth == 0:
        return

    runner = create_followup_runner(ctx)
    logger.debug(
        "finalize_with_followup: scheduling drain for %s (depth=%d)",
        queue_key[:20],
        depth,
    )
    schedule_followup_drain(queue_key, runner)


__all__ = ["create_followup_runner", "finalize_with_followup"]
