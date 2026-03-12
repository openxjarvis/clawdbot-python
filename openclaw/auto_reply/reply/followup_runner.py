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
import uuid
from typing import Callable, Awaitable, TYPE_CHECKING

if TYPE_CHECKING:
    from openclaw.auto_reply.reply.agent_runner import ReplyContext
    from openclaw.auto_reply.reply.queue import FollowupRun

logger = logging.getLogger(__name__)

# Followup runs use a shorter timeout than primary runs — a stuck followup
# must not block the entire drain queue forever.
FOLLOWUP_TIMEOUT_S = 300.0  # 5 minutes


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

    async def run_followup(queued: FollowupRun) -> None:
        """Execute a single queued followup turn."""
        from openclaw.auto_reply.reply.typing import create_typing_controller

        # Create a fresh TypingController for this followup so the user sees a
        # typing indicator while the queued message is being processed.
        # Mirrors TS createFollowupRunner — the TypingController reference is
        # shared across the primary run and followup runner, but in Python we
        # create a new one per followup since the original is sealed after the
        # primary run completes.
        followup_typing_ctrl = None
        if ctx.typing_send_fn:
            followup_typing_ctrl = create_typing_controller(
                on_reply_start=ctx.typing_send_fn,
            )

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
            typing_ctrl=followup_typing_ctrl,
            typing_send_fn=ctx.typing_send_fn,
        )

        run_id = str(uuid.uuid4())
        logger.info(
            "followup_runner: running followup for session %s (prompt=%s…)",
            followup_ctx.session_id[:8],
            queued.prompt[:40],
        )

        # Start typing indicator immediately so user sees "typing..." feedback
        # before the agent turn begins (can be a long-running operation).
        if followup_typing_ctrl:
            try:
                await followup_typing_ctrl.on_reply_start()
                await followup_typing_ctrl.start_typing_loop()
            except Exception:
                pass

        try:
            try:
                response_text, has_error, auto_compaction_completed = await asyncio.wait_for(
                    _execute_agent_turn(followup_ctx, run_id),
                    timeout=FOLLOWUP_TIMEOUT_S,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "followup_runner: timed out after %.0fs for session %s",
                    FOLLOWUP_TIMEOUT_S,
                    followup_ctx.session_id[:8],
                )
                from openclaw.agents.pi_embedded import abort_embedded_pi_run, clear_active_embedded_run
                abort_embedded_pi_run(followup_ctx.session_id)
                clear_active_embedded_run(followup_ctx.session_id, run_id)
                return

            # Gap 2: strip HEARTBEAT_OK tokens from followup response
            has_media = bool(queued.originating_to)  # conservative: if there's a target, allow through
            if response_text and "HEARTBEAT_OK" in response_text.upper():
                try:
                    from openclaw.gateway.heartbeat import strip_heartbeat_ok
                    _stripped = strip_heartbeat_ok(response_text)
                    if not _stripped and not has_media:
                        logger.debug(
                            "followup_runner: pure HEARTBEAT_OK — skipping delivery for session %s",
                            followup_ctx.session_id[:8],
                        )
                        return
                    response_text = _stripped
                except Exception:
                    pass

            # Gap 5: prepend auto-compaction notice when verbose
            if auto_compaction_completed and response_text is not None:
                try:
                    verbose_level = getattr(queued.run.get("verboseLevel", None) if isinstance(queued.run, dict) else getattr(queued.run, "verboseLevel", None), "__str__", lambda: None)() if False else (queued.run.get("verboseLevel") if isinstance(queued.run, dict) else getattr(queued.run, "verboseLevel", None))
                    if verbose_level and verbose_level != "off":
                        response_text = f"🧹 Auto-compaction complete.\n\n{response_text}" if response_text else "🧹 Auto-compaction complete."
                except Exception:
                    pass

            if response_text or has_error:
                await _deliver_response(followup_ctx, response_text, has_error)
        except Exception as exc:
            logger.warning(
                "followup_runner: error executing followup for %s: %s",
                followup_ctx.session_id[:8],
                exc,
            )
        finally:
            # Always stop typing indicator once the followup run finishes
            if followup_typing_ctrl:
                try:
                    followup_typing_ctrl.mark_run_complete()
                    followup_typing_ctrl.mark_dispatch_idle()
                except Exception:
                    pass

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
