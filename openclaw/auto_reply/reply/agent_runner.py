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

# Agent run timeout. TS default is 600s (10 min) but 3 minutes is more
# practical for interactive Telegram/Feishu sessions: it unblocks the followup
# queue faster when an agent run gets stuck (e.g. model hallucinating tool work
# that never completes). Complex tasks should set a higher timeout via config.
DEFAULT_AGENT_TIMEOUT_MS = 3 * 60 * 1000  # 3 minutes


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
    session_workspace: str | None = None  # agent workspace dir for media root search
    typing_ctrl: Any | None = None       # TypingController or None
    # Raw send_typing callback — stored so followup runner can create fresh
    # TypingControllers for each queued turn (mirrors TS: typing passed through
    # to createFollowupRunner so each followup can restart the indicator).
    typing_send_fn: Callable[[], Awaitable[None]] | None = None
    timeout_ms: int = DEFAULT_AGENT_TIMEOUT_MS
    abort_event: asyncio.Event | None = None  # set to abort mid-run
    # Streaming preview support — channel creates and passes these
    stream_callback: Callable[[str], None] | None = None  # called with full accumulated text on each delta
    draft_stream: Any | None = None  # streaming session reference for lifecycle (clear/stop)
    # Status reactions — emoji on the inbound user message showing agent state
    # Mirrors TS StatusReactionController (Telegram, Discord, etc.)
    status_reactions: Any | None = None
    # Two-lane reasoning streaming — separate draft stream for <think> content.
    # reasoning_level: "off" | "on" | "stream"
    # reasoning_stream_callback: called with accumulated reasoning text on each delta
    # reasoning_draft_stream: TelegramDraftStream for the reasoning lane
    reasoning_level: str = "off"
    reasoning_stream_callback: Callable[[str], None] | None = None
    reasoning_draft_stream: Any | None = None
    # Block reply dispatcher — sends each text block (before a tool call) as a
    # separate visible message. Mirrors TS sendBlockReply in reply-dispatcher.ts.
    # Enabled for Telegram DMs and Feishu thread replies where intermediate steps
    # should appear as individual messages rather than a single streaming preview.
    block_send_fn: Callable[[str], Awaitable[None]] | None = None


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
            # steer-backlog dual action: mirrors TS shouldSteer && shouldFollowup.
            # When mode is "steer-backlog", steer the active run AND also enqueue
            # the message as a followup so it is re-processed after the run ends.
            mode = (ctx.queue_settings.mode if ctx.queue_settings else None) or "followup"
            if mode not in ("steer-backlog", "steer+backlog"):
                if ctx.typing_ctrl:
                    ctx.typing_ctrl.mark_run_complete()
                    ctx.typing_ctrl.mark_dispatch_idle()
                return
            # Fall through to enqueue-followup for steer-backlog modes
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
    asyncio.create_task(_run_agent_now(ctx))


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
            await _cleanup_draft_stream_on_abort(ctx)
            return

        timeout_s = (ctx.timeout_ms or DEFAULT_AGENT_TIMEOUT_MS) / 1000.0

        # Transition status reaction from "queued" → "thinking" just before the
        # agent turn starts. Mirrors TS: statusReactionController.setThinking()
        # called in bot-message-dispatch.ts before dispatchReplyWithBufferedBlockDispatcher.
        if ctx.status_reactions:
            try:
                await ctx.status_reactions.set_thinking()
            except Exception:
                pass

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
            from openclaw.agents.pi_embedded import abort_embedded_pi_run, clear_active_embedded_run
            abort_embedded_pi_run(ctx.session_id)
            # Defense-in-depth: explicitly clear the stale handle so new messages
            # get "run-now" instead of "enqueue-followup" forever.  The run_id
            # guard inside clear_active_embedded_run prevents clearing a newer run.
            clear_active_embedded_run(ctx.session_id, run_id)
            await _cleanup_draft_stream_on_abort(ctx)
            return

        # Handle streaming preview lifecycle before delivering the final response.
        #
        # Feishu (FeishuReplyDispatcher):
        #   - When streaming card is active → stream_finalize() sends the final
        #     text, patches settings (streaming_mode: false), and stops typing.
        #     _deliver_response() is skipped — finalize already delivered the text.
        #   - When streaming is NOT active (CardKit failed / disabled) →
        #     stop_typing() first, then _deliver_response() → _channel_send()
        #     → dispatcher.send() which handles render_mode.
        #
        # Telegram (TelegramDraftStream):
        #   - clear() deletes the editMessageText preview bubble.
        #   - _deliver_response() then sends the final formatted message fresh.
        _skip_deliver = False
        if ctx.draft_stream is not None:
            _has_finalize = hasattr(ctx.draft_stream, "stream_finalize")
            _has_active = hasattr(ctx.draft_stream, "is_streaming_active")
            if _has_finalize and _has_active:
                # FeishuReplyDispatcher path
                if ctx.draft_stream.is_streaming_active():
                    # Parse buttons from response before finalizing — they'll be
                    # patched onto the card after streaming_mode is turned off.
                    from openclaw.auto_reply.directive_tags import parse_inline_directives
                    _finalize_text = response_text or ""
                    _finalize_buttons = None
                    try:
                        _dir = parse_inline_directives(_finalize_text, strip_reply_tags=True)
                        _finalize_buttons = _dir.buttons
                        _finalize_text = _dir.text or _finalize_text
                    except Exception:
                        pass
                    # Streaming card is live — finalize it with the full response text
                    try:
                        await ctx.draft_stream.stream_finalize(
                            _finalize_text, buttons=_finalize_buttons
                        )
                    except Exception as _fe:
                        logger.debug("stream_finalize failed (non-fatal): %s", _fe)
                    _skip_deliver = True
                else:
                    # Streaming was not started (CardKit failed or disabled) — stop
                    # the typing indicator so it doesn't linger, then fall through to
                    # _deliver_response() which will call dispatcher.send() via _channel_send.
                    try:
                        if hasattr(ctx.draft_stream, "stop_typing"):
                            await ctx.draft_stream.stop_typing()
                    except Exception:
                        pass
            else:
                # TelegramDraftStream lifecycle - mirrors TS lane-delivery.ts finalization.
                # Try to finalize the preview message by editing it to the final text.
                # If successful, skip _deliver_response to avoid duplicate messages.
                # Mirrors TS: canFinalizeDraftPreviewDirectly + tryUpdatePreviewForLane.
                _can_try_finalize = False
                try:
                    # Check if we can finalize via editing the preview:
                    # - Must be message transport (groups) with an active preview message
                    # - Text must fit within Telegram's 4096 char limit
                    # - No media attachments (media requires new message)
                    # - No buttons (buttons require separate handling)
                    _is_msg_transport = (
                        hasattr(ctx.draft_stream, "is_draft_transport")
                        and not ctx.draft_stream.is_draft_transport()
                        and ctx.draft_stream.message_id() is not None
                    )
                    _text_ok = response_text and len(response_text) <= 4096
                    _no_media = not (
                        getattr(ctx, "media_urls", None) or
                        getattr(ctx, "media_url", None)
                    )
                    # Check for buttons in response_text directives
                    _has_buttons = False
                    if _text_ok:
                        try:
                            from openclaw.auto_reply.directive_tags import parse_inline_directives
                            _dir = parse_inline_directives(response_text, strip_reply_tags=False)
                            _has_buttons = bool(_dir.buttons)
                        except Exception:
                            pass
                    
                    _can_try_finalize = (
                        _is_msg_transport and _text_ok and _no_media and not _has_buttons
                    )
                except Exception as _check_exc:
                    logger.debug("Error checking finalize conditions: %s", _check_exc)
                
                if _can_try_finalize:
                    # Try to edit the preview message to the final text.
                    # Mirrors TS: lane.stream.update(text) + flushDraftLane + stopDraftLane.
                    try:
                        # Update with final text and flush
                        ctx.draft_stream.update(response_text)
                        await ctx.draft_stream.stop()
                        
                        # Check if the final text was successfully delivered
                        # Mirrors TS: finalTextAlreadyDelivered check via previewRevision
                        _last_sent = getattr(ctx.draft_stream, "_last_sent_text", "")
                        _final_trimmed = response_text.rstrip()
                        if _last_sent == _final_trimmed:
                            # Preview was successfully finalized — skip _deliver_response.
                            # Mirrors TS: return "preview-finalized"
                            _skip_deliver = True
                            logger.debug(
                                "Telegram: finalized preview as final message (len=%d)",
                                len(_final_trimmed),
                            )
                        else:
                            logger.debug(
                                "Telegram: preview finalization incomplete, will send new message"
                            )
                    except Exception as _fin_exc:
                        logger.debug(
                            "Telegram: preview finalization failed, will send new message: %s",
                            _fin_exc,
                        )
                
                # Fallback: clear the preview if finalization didn't work
                if not _skip_deliver:
                    _should_clear = True
                    try:
                        # Draft transport (DMs): clear() is a no-op (just sets _stopped=True).
                        # Message transport (groups): if finalization failed, clear the preview
                        # so we don't leave a stale message visible.
                        if hasattr(ctx.draft_stream, "is_draft_transport"):
                            _is_draft = ctx.draft_stream.is_draft_transport()
                            if not _is_draft:
                                # Message transport — only clear if we didn't try finalization
                                # (if we tried and failed, preview is already stopped)
                                if not _can_try_finalize:
                                    _should_clear = True
                                else:
                                    # Finalization was tried but didn't complete — stop but don't clear
                                    # to avoid blank gap before new message arrives
                                    _should_clear = False
                                    ctx.draft_stream._stopped = True
                            else:
                                # Draft transport — always safe to clear (no-op)
                                _should_clear = True
                    except Exception:
                        _should_clear = True
                    
                    if _should_clear:
                        try:
                            if hasattr(ctx.draft_stream, "clear"):
                                await ctx.draft_stream.clear()
                        except Exception as _ds_exc:
                            logger.debug("draft_stream.clear() failed (non-fatal): %s", _ds_exc)

        # --- Reasoning lane cleanup ---
        # For "stream" mode: stop the reasoning draft stream (flushes any
        # remaining text to Telegram) and strip reasoning blocks from the
        # answer so the final reply contains only the visible answer.
        # For "on" mode: extract reasoning text and send it as a SEPARATE
        # message BEFORE the answer — this is the key difference vs "stream"
        # (which shows reasoning live) and "off" (which strips it silently).
        # Mirrors TS dispatchTelegramMessage lane cleanup + "on" mode delivery.
        if ctx.reasoning_level != "off" and response_text:
            from openclaw.channels.telegram.reasoning import split_telegram_reasoning_text
            _r_text, _a_text = split_telegram_reasoning_text(response_text)
            if ctx.reasoning_level == "on" and _r_text and not _skip_deliver:
                # "on" mode: send reasoning as a separate message before the answer.
                # Wrap in a blockquote so it's visually distinct.
                # Mirrors TS: reasoning delivered as its own message block before answer.
                _reasoning_msg = f"💭 <i>Thinking:</i>\n<blockquote>{_r_text}</blockquote>"
                try:
                    from openclaw.channels.telegram.formatter import markdown_to_html, wrap_file_references_in_html
                    _reasoning_msg = f"💭 <i>Thinking:</i>\n<blockquote>{wrap_file_references_in_html(markdown_to_html(_r_text))}</blockquote>"
                except Exception:
                    pass
                try:
                    await ctx.channel_send(_reasoning_msg, ctx.chat_target)
                except Exception as _re_exc:
                    logger.debug("_run_agent_now: failed to send reasoning message: %s", _re_exc)
            response_text = _a_text or response_text

        if ctx.reasoning_draft_stream is not None:
            try:
                if hasattr(ctx.reasoning_draft_stream, "stop"):
                    # stop() flushes any remaining streamed reasoning text to Telegram.
                    # Must be awaited BEFORE _deliver_response to preserve ordering.
                    await ctx.reasoning_draft_stream.stop()
            except Exception:
                pass

        if not _skip_deliver:
            await _deliver_response(ctx, response_text, has_error)

        # Set terminal status reaction after delivery.
        # Mirrors TS: setDone() / setError() at the end of dispatchTelegramMessage.
        if ctx.status_reactions:
            try:
                if has_error:
                    await ctx.status_reactions.set_error()
                else:
                    await ctx.status_reactions.set_done()
            except Exception:
                pass

    except asyncio.CancelledError:
        logger.info("_run_agent_now: cancelled for session %s", ctx.session_id[:8])
        await _cleanup_draft_stream_on_abort(ctx)
        raise
    except Exception as exc:
        logger.error("_run_agent_now: error for session %s: %s", ctx.session_id[:8], exc, exc_info=True)
        await _cleanup_draft_stream_on_abort(ctx)
        # Mark as error in status reactions on unexpected exception
        if ctx.status_reactions:
            try:
                await ctx.status_reactions.set_error()
            except Exception:
                pass
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


async def _cleanup_draft_stream_on_abort(ctx: "ReplyContext") -> None:
    """Emergency cleanup of streaming sessions on timeout/cancel/error.

    Ensures Feishu streaming cards are closed (streaming_mode=false) and
    Telegram preview bubbles are cleared, even when the agent run is aborted
    mid-stream. Prevents worker task leaks and stale "⏳ Thinking..." cards.
    """
    if ctx.draft_stream is None:
        return
    try:
        _has_finalize = hasattr(ctx.draft_stream, "stream_finalize")
        _has_active = hasattr(ctx.draft_stream, "is_streaming_active")
        if _has_finalize and _has_active:
            # Feishu: finalize with empty text to close streaming_mode
            if ctx.draft_stream.is_streaming_active():
                try:
                    await ctx.draft_stream.stream_finalize("", buttons=None)
                except Exception as _e:
                    logger.debug("_cleanup_draft_stream_on_abort: finalize failed: %s", _e)
            elif hasattr(ctx.draft_stream, "stop_typing"):
                try:
                    await ctx.draft_stream.stop_typing()
                except Exception:
                    pass
        else:
            # Telegram: clear the preview bubble on abort/error (always clean up on abort)
            if hasattr(ctx.draft_stream, "clear"):
                try:
                    await ctx.draft_stream.clear()
                except Exception as _e:
                    logger.debug("_cleanup_draft_stream_on_abort: clear failed: %s", _e)
    except Exception as exc:
        logger.debug("_cleanup_draft_stream_on_abort: unexpected error: %s", exc)


async def _execute_agent_turn(
    ctx: ReplyContext,
    run_id: str,
) -> tuple[str, bool]:
    """Run one agent turn and collect the response.

    Returns (response_text, has_error).
    Uses ``run_agent_turn_with_fallback`` for compaction + transient retry.
    """
    from openclaw.auto_reply.reply.agent_runner_execution import run_agent_turn_with_fallback
    from openclaw.auto_reply.reply.typing import create_typing_signaler

    # Build a TypingSignaler for this turn so typing is refreshed on each text
    # delta and tool start — mirrors TS createTypingSignaler wiring in get-reply.ts
    typing_signaler = None
    if ctx.typing_ctrl:
        typing_signaler = create_typing_signaler(ctx.typing_ctrl, mode="instant")

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
        typing_signaler=typing_signaler,
        stream_callback=ctx.stream_callback,
        status_reactions=ctx.status_reactions,
        reasoning_stream_callback=ctx.reasoning_stream_callback,
        reasoning_level=ctx.reasoning_level,
        block_send_fn=ctx.block_send_fn,
    )


def _get_local_media_roots(session_workspace: str | None = None) -> list["Path"]:
    """Return ordered list of local directories to search for media files.

    Mirrors TS ``getAgentScopedMediaLocalRoots`` from
    ``openclaw/src/media/local-roots.ts``.  The search order mirrors TS:
    tmpDir → ~/.openclaw/media → agents → workspace → sandboxes → session workspace.
    """
    import tempfile
    from pathlib import Path

    state_dir = Path.home() / ".openclaw"
    roots: list[Path] = [
        Path(tempfile.gettempdir()) / "openclaw",
        state_dir / "media",
        state_dir / "agents",
        state_dir / "workspace",
        state_dir / "sandboxes",
    ]
    if session_workspace:
        ws = Path(session_workspace).resolve()
        if ws not in roots:
            roots.append(ws)
    return roots


def _is_path_under_allowed_roots(resolved: "Path", session_workspace: str | None) -> bool:
    """Return True if *resolved* (symlinks already expanded) is inside an allowed media root.

    Mirrors TS assertLocalMediaAllowed() in src/web/media.ts — prevents an agent from
    exfiltrating arbitrary host files (e.g. /etc/passwd) via a MEDIA: token.
    """
    import os
    from pathlib import Path

    resolved_str = str(resolved)
    for root in _get_local_media_roots(session_workspace):
        try:
            root_real = root.resolve()
        except Exception:
            continue
        root_str = str(root_real)
        # Path must be strictly under (or equal to) an allowed root.
        if resolved_str == root_str or resolved_str.startswith(root_str + os.sep):
            return True
    return False


def _resolve_media_path(raw_url: str, session_workspace: str | None = None) -> str:
    """Resolve a raw media URL/path to an existing absolute path.

    1. HTTP(S) / file:// URLs → returned as-is.
    2. Absolute paths that exist AND are inside an allowed media root → returned as-is.
       Paths outside allowed roots are rejected (path-traversal / exfiltration guard).
    3. Otherwise: search local media roots for the filename (TS alignment).
    Returns the resolved path, or the original string if nothing is found.
    """
    from pathlib import Path

    if raw_url.startswith(("http://", "https://", "file://")):
        return raw_url

    p = Path(raw_url).expanduser()
    if p.is_absolute() and p.exists():
        # Resolve symlinks before the containment check (prevents symlink bypass).
        real_p = p.resolve()
        if _is_path_under_allowed_roots(real_p, session_workspace):
            return str(p)
        logger.warning(
            "MEDIA: blocked absolute path outside allowed workspace roots: %s", raw_url
        )
        return raw_url  # caller will skip non-existent / non-URL entries

    for root in _get_local_media_roots(session_workspace):
        # Try full relative path first (e.g. "presentations/file.pptx" under workspace)
        if not p.is_absolute():
            candidate = root / p
            if candidate.exists():
                logger.debug("Resolved media %r → %s", raw_url, candidate)
                return str(candidate)
        # Fall back to filename-only search (mirrors TS local-roots fallback)
        candidate = root / p.name
        if candidate.exists():
            logger.debug("Resolved media %r → %s", raw_url, candidate)
            return str(candidate)

    return raw_url


async def _deliver_response(
    ctx: ReplyContext,
    response_text: str,
    has_error: bool,
) -> None:
    """Deliver accumulated response text back to the channel."""
    from openclaw.auto_reply.media_parse import split_media_from_output
    from openclaw.auto_reply.directive_tags import parse_inline_directives

    if not response_text and not has_error:
        return

    if not response_text:
        return

    try:
        # DEBUG: Log raw response before any processing to help diagnose media delivery issues
        logger.info("[DELIVER-DEBUG] Raw response length: %d chars", len(response_text))
        if "MEDIA:" in response_text.upper():
            logger.info("[DELIVER-DEBUG] Found MEDIA token in raw response")
        if "![" in response_text or "](file://" in response_text:
            logger.info("[DELIVER-DEBUG] Found Markdown image/link syntax in response - this will NOT send files!")
            logger.info("[DELIVER-DEBUG] Response preview: %s", response_text[:800])
        
        # Parse [[buttons:...]] directive before splitting media
        directive_result = parse_inline_directives(response_text, strip_reply_tags=True)
        buttons = directive_result.buttons  # list[list[dict]] | None
        # Use the text with the buttons directive stripped for further processing
        cleaned_text = directive_result.text if directive_result.text else response_text

        media_result = split_media_from_output(cleaned_text)
        logger.info(
            "Media parse result: text=%s chars, media_url=%s, media_urls=%s",
            len(media_result.text) if media_result.text else 0,
            media_result.media_url[:100] if media_result.media_url else None,
            [u[:100] for u in (media_result.media_urls or [])] if media_result.media_urls else None,
        )
        display_text = media_result.text if media_result.text is not None else cleaned_text

        if display_text:
            await ctx.channel_send(
                display_text,
                ctx.chat_target,
                reply_to=ctx.reply_to_id,
                buttons=buttons,
            )

        # Send media files
        # Deduplicate media URLs to prevent sending the same file multiple times
        # (can happen when MEDIA tokens accumulate in session history)
        session_workspace: str | None = getattr(ctx, "session_workspace", None)
        all_media_urls = ([media_result.media_url] if media_result.media_url else []) + (media_result.media_urls or [])
        
        # Normalize and deduplicate paths before sending
        # This handles cases where the same file is referenced with different paths
        # (e.g., relative vs absolute, or with/without ./ prefix)
        from pathlib import Path
        seen_normalized = set()
        unique_media_urls = []
        for url in all_media_urls:
            if not url:
                continue
            # Normalize the path: resolve relative paths and remove redundant components
            try:
                if not url.startswith(("http://", "https://")):
                    # Local file - normalize path
                    normalized = str(Path(url).expanduser().resolve())
                else:
                    # Remote URL - use as-is
                    normalized = url
                
                if normalized not in seen_normalized:
                    seen_normalized.add(normalized)
                    unique_media_urls.append(url)  # Keep original URL for delivery
            except Exception:
                # If normalization fails, still try to dedupe by string
                if url not in seen_normalized:
                    seen_normalized.add(url)
                    unique_media_urls.append(url)
        
        if len(unique_media_urls) < len(all_media_urls):
            logger.info("[DELIVER-DEBUG] Deduped %d media URLs to %d unique URLs", len(all_media_urls), len(unique_media_urls))
        
        for media_url in unique_media_urls:
            if not media_url:
                continue
            try:
                media_url = _resolve_media_path(media_url, session_workspace)
                from openclaw.media.mime import detect_mime, MediaKind, media_kind_from_mime, is_gif_media
                mime = detect_mime(media_url)
                kind = media_kind_from_mime(mime)
                # GIF auto-detection: if MIME didn't identify it but filename ends in .gif,
                # override to ANIMATION — mirrors TS isGifMedia() in send.ts
                if kind == MediaKind.IMAGE and is_gif_media(mime, media_url):
                    kind = MediaKind.ANIMATION
                media_type = kind.value if kind != MediaKind.UNKNOWN else "document"
                await ctx.channel_send(None, ctx.chat_target, media_url=media_url, media_type=media_type)
            except Exception as me:
                logger.error("Failed to send media %s: %s", media_url, me)
                # Notify user so they don't see silent failure (mirrors TS delivery error handling)
                try:
                    import os
                    fname = os.path.basename(media_url) if media_url else "file"
                    await ctx.channel_send(
                        f"⚠️ Failed to send file `{fname}`: {me}",
                        ctx.chat_target,
                    )
                except Exception:
                    pass

    except Exception as exc:
        logger.error("_deliver_response error: %s", exc, exc_info=True)


__all__ = ["ReplyContext", "run_prepared_reply"]
