"""Telegram lane delivery — manages answer/reasoning channels and preview finalization.

Mirrors TypeScript src/telegram/lane-delivery.ts:
  - LaneDeliveryResult: preview-finalized | preview-updated | sent | skipped
  - create_lane_text_deliverer(): factory for delivering text to lanes
  - Smart decision: edit preview vs send new message
  - Archived preview handling after forceNewMessage

Lane lifecycle:
  1. Partial updates → update draft stream
  2. Final text → try to finalize preview (edit) OR send new message
  3. Cleanup → stop/clear draft streams
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Literal

logger = logging.getLogger(__name__)

LaneDeliveryResult = Literal["preview-finalized", "preview-updated", "sent", "skipped"]
LaneName = Literal["answer", "reasoning"]


class ArchivedPreview:
    """Preview message that was superseded by forceNewMessage().
    
    Mirrors TS ArchivedPreview type.
    """
    def __init__(self, message_id: int, text_snapshot: str):
        self.message_id = message_id
        self.text_snapshot = text_snapshot


class DraftLaneState:
    """State for a single lane (answer or reasoning).
    
    Mirrors TS DraftLaneState type.
    """
    def __init__(self, stream: Any | None):
        self.stream = stream  # TelegramDraftStream instance
        self.last_partial_text = ""
        self.has_streamed_message = False
        self.preview_revision_baseline = (
            stream.preview_revision() if stream and hasattr(stream, "preview_revision") else 0
        )


def _should_skip_regressive_preview_update(
    current_preview_text: str | None,
    text: str,
    skip_regressive: Literal["always", "existingOnly"],
    had_preview_message: bool,
) -> bool:
    """Check if we should skip an update that makes the text shorter.
    
    Mirrors TS shouldSkipRegressivePreviewUpdate() in lane-delivery.ts.
    Prevents flicker when provider briefly emits shorter text snapshot.
    """
    if current_preview_text is None:
        return False
    
    # Skip if new text is a prefix of current (regression)
    is_regressive = (
        current_preview_text.startswith(text) and
        len(text) < len(current_preview_text)
    )
    if not is_regressive:
        return False
    
    # Skip based on mode
    if skip_regressive == "always":
        return True
    if skip_regressive == "existingOnly" and had_preview_message:
        return True
    
    return False


async def _try_edit_preview_message(
    lane_name: LaneName,
    message_id: int,
    text: str,
    context: Literal["final", "update"],
    lane: DraftLaneState,
    edit_preview_fn: Callable,
    mark_delivered_fn: Callable,
    log_fn: Callable,
    update_lane_snapshot: bool,
    treat_edit_failure_as_delivered: bool,
) -> bool:
    """Try to edit an existing preview message.
    
    Mirrors TS tryEditPreviewMessage() in lane-delivery.ts.
    Returns True if edit succeeded, False if it failed and should fallback.
    """
    try:
        await edit_preview_fn(
            lane_name=lane_name,
            message_id=message_id,
            text=text,
            context=context,
        )
        if update_lane_snapshot:
            lane.last_partial_text = text
        mark_delivered_fn()
        return True
    except Exception as exc:
        if treat_edit_failure_as_delivered:
            log_fn(
                f"telegram: {lane_name} preview {context} edit failed after stop-created flush; "
                f"treating as delivered ({exc})"
            )
            mark_delivered_fn()
            return True
        log_fn(
            f"telegram: {lane_name} preview {context} edit failed; "
            f"falling back to standard send ({exc})"
        )
        return False


async def _try_update_preview_for_lane(
    lane: DraftLaneState,
    lane_name: LaneName,
    text: str,
    stop_before_edit: bool,
    skip_regressive: Literal["always", "existingOnly"],
    context: Literal["final", "update"],
    update_lane_snapshot: bool,
    edit_preview_fn: Callable,
    flush_draft_fn: Callable,
    stop_draft_fn: Callable,
    mark_delivered_fn: Callable,
    log_fn: Callable,
    preview_message_id_override: int | None = None,
    preview_text_snapshot: str | None = None,
) -> bool:
    """Try to update the preview message for a lane.
    
    Mirrors TS tryUpdatePreviewForLane() in lane-delivery.ts.
    Returns True if preview was successfully updated/finalized.
    """
    if not lane.stream:
        return False
    
    # Resolve preview target
    lane_preview_msg_id = (
        lane.stream.message_id() if hasattr(lane.stream, "message_id") else None
    )
    preview_msg_id = (
        preview_message_id_override
        if preview_message_id_override is not None
        else lane_preview_msg_id
    )
    had_preview_message = (
        preview_message_id_override is not None or lane_preview_msg_id is not None
    )
    stop_creates_first_preview = (
        stop_before_edit and not had_preview_message and context == "final"
    )
    
    # If stop() will create the first preview, prime it with final text
    if stop_creates_first_preview:
        lane.stream.update(text)
        await stop_draft_fn(lane)
        # Re-check message ID after stop
        new_msg_id = (
            lane.stream.message_id() if hasattr(lane.stream, "message_id") else None
        )
        if new_msg_id is None:
            return False
        preview_msg_id = new_msg_id
        had_preview_message = False
    elif stop_before_edit:
        await stop_draft_fn(lane)
    
    # Final message ID check
    if preview_msg_id is None:
        return False
    
    # Check for regressive update (text getting shorter)
    current_preview_text = preview_text_snapshot or lane.last_partial_text
    should_skip = _should_skip_regressive_preview_update(
        current_preview_text, text, skip_regressive, had_preview_message
    )
    if should_skip:
        mark_delivered_fn()
        return True
    
    # Try to edit the preview message
    treat_edit_failure_as_delivered = stop_creates_first_preview
    return await _try_edit_preview_message(
        lane_name=lane_name,
        message_id=preview_msg_id,
        text=text,
        context=context,
        lane=lane,
        edit_preview_fn=edit_preview_fn,
        mark_delivered_fn=mark_delivered_fn,
        log_fn=log_fn,
        update_lane_snapshot=update_lane_snapshot,
        treat_edit_failure_as_delivered=treat_edit_failure_as_delivered,
    )


async def _consume_archived_answer_preview_for_final(
    lane: DraftLaneState,
    text: str,
    archived_previews: list[ArchivedPreview],
    can_edit_via_preview: bool,
    delete_preview_fn: Callable,
    send_payload_fn: Callable,
    edit_preview_fn: Callable,
    flush_draft_fn: Callable,
    stop_draft_fn: Callable,
    mark_delivered_fn: Callable,
    log_fn: Callable,
) -> LaneDeliveryResult | None:
    """Try to reuse an archived preview message for the final text.
    
    Mirrors TS consumeArchivedAnswerPreviewForFinal() in lane-delivery.ts.
    Returns delivery result if an archived preview was consumed, None otherwise.
    """
    if not archived_previews:
        return None
    
    archived_preview = archived_previews.pop(0)
    
    if can_edit_via_preview:
        # Try to edit the archived preview message
        finalized = await _try_update_preview_for_lane(
            lane=lane,
            lane_name="answer",
            text=text,
            stop_before_edit=False,
            skip_regressive="existingOnly",
            context="final",
            update_lane_snapshot=False,
            edit_preview_fn=edit_preview_fn,
            flush_draft_fn=flush_draft_fn,
            stop_draft_fn=stop_draft_fn,
            mark_delivered_fn=mark_delivered_fn,
            log_fn=log_fn,
            preview_message_id_override=archived_preview.message_id,
            preview_text_snapshot=archived_preview.text_snapshot,
        )
        if finalized:
            return "preview-finalized"
    
    # Delete the archived preview and send new message
    try:
        await delete_preview_fn(archived_preview.message_id)
    except Exception as exc:
        log_fn(
            f"telegram: archived answer preview cleanup failed "
            f"({archived_preview.message_id}): {exc}"
        )
    
    delivered = await send_payload_fn(text)
    return "sent" if delivered else "skipped"


def create_lane_text_deliverer(
    lanes: dict[LaneName, DraftLaneState],
    archived_answer_previews: list[ArchivedPreview],
    finalized_preview_by_lane: dict[LaneName, bool],
    draft_max_chars: int,
    send_payload_fn: Callable[[str], Any],  # async (text) -> bool
    flush_draft_lane_fn: Callable[[DraftLaneState], Any],  # async (lane) -> None
    stop_draft_lane_fn: Callable[[DraftLaneState], Any],  # async (lane) -> None
    edit_preview_fn: Callable,  # async (lane_name, message_id, text, context) -> None
    delete_preview_message_fn: Callable[[int], Any],  # async (message_id) -> None
    mark_delivered_fn: Callable[[], None],
    log_fn: Callable[[str], None],
) -> Callable:
    """Create a lane text deliverer function.
    
    Mirrors TS createLaneTextDeliverer() in lane-delivery.ts.
    Returns an async function that delivers text to the appropriate lane.
    """
    
    def _is_draft_preview_lane(lane: DraftLaneState) -> bool:
        """Check if lane uses draft transport (DM streaming bubble)."""
        if not lane.stream or not hasattr(lane.stream, "is_draft_transport"):
            return False
        try:
            return lane.stream.is_draft_transport()
        except Exception:
            return False
    
    async def deliver_lane_text(
        lane_name: LaneName,
        text: str,
        info_kind: str,
        has_media: bool = False,
        has_buttons: bool = False,
        allow_preview_update_for_non_final: bool = False,
    ) -> LaneDeliveryResult:
        """Deliver text to a lane (answer or reasoning).
        
        Mirrors TS deliverLaneText() returned by createLaneTextDeliverer().
        """
        lane = lanes[lane_name]
        can_edit_via_preview = (
            not has_media and
            text and len(text) <= draft_max_chars and
            not has_buttons
        )
        
        if info_kind == "final":
            # Final delivery — try to finalize preview, else send new message
            can_finalize_draft_directly = (
                _is_draft_preview_lane(lane) and
                lane.has_streamed_message and
                can_edit_via_preview and
                not has_buttons
            )
            draft_preview_stopped = False
            
            if can_finalize_draft_directly:
                # Draft transport (DM) — try to finalize via stop()
                preview_revision_before = (
                    lane.stream.preview_revision()
                    if hasattr(lane.stream, "preview_revision") else 0
                )
                final_text_snapshot = text.rstrip()
                has_emitted_preview = (
                    preview_revision_before > lane.preview_revision_baseline
                )
                delivered_text_before = (
                    lane.stream.last_delivered_text()
                    if hasattr(lane.stream, "last_delivered_text") else ""
                )
                final_already_delivered = (
                    delivered_text_before == final_text_snapshot and
                    has_emitted_preview
                )
                unchanged_final = text == lane.last_partial_text
                
                lane.stream.update(text)
                await flush_draft_lane_fn(lane)
                await stop_draft_lane_fn(lane)
                draft_preview_stopped = True
                
                preview_revision_after = (
                    lane.stream.preview_revision()
                    if hasattr(lane.stream, "preview_revision") else 0
                )
                preview_updated = preview_revision_after > preview_revision_before
                delivered_text_after = (
                    lane.stream.last_delivered_text()
                    if hasattr(lane.stream, "last_delivered_text")
                    else delivered_text_before
                )
                
                if (
                    (preview_updated and delivered_text_after == final_text_snapshot) or
                    (unchanged_final and final_already_delivered)
                ):
                    lane.last_partial_text = text
                    finalized_preview_by_lane[lane_name] = True
                    mark_delivered_fn()
                    return "preview-finalized"
                
                log_fn(
                    f"telegram: {lane_name} draft final text not emitted; "
                    f"falling back to standard send"
                )
            
            # Try archived preview (answer lane only)
            if lane_name == "answer":
                archived_result = await _consume_archived_answer_preview_for_final(
                    lane=lane,
                    text=text,
                    archived_previews=archived_answer_previews,
                    can_edit_via_preview=can_edit_via_preview,
                    delete_preview_fn=delete_preview_message_fn,
                    send_payload_fn=send_payload_fn,
                    edit_preview_fn=edit_preview_fn,
                    flush_draft_fn=flush_draft_lane_fn,
                    stop_draft_fn=stop_draft_lane_fn,
                    mark_delivered_fn=mark_delivered_fn,
                    log_fn=log_fn,
                )
                if archived_result:
                    return archived_result
            
            # Try to edit existing preview (message transport)
            if (
                can_edit_via_preview and
                not finalized_preview_by_lane[lane_name] and
                not draft_preview_stopped
            ):
                await flush_draft_lane_fn(lane)
                
                # Second chance for archived preview after flush
                if lane_name == "answer":
                    archived_result2 = await _consume_archived_answer_preview_for_final(
                        lane=lane,
                        text=text,
                        archived_previews=archived_answer_previews,
                        can_edit_via_preview=can_edit_via_preview,
                        delete_preview_fn=delete_preview_message_fn,
                        send_payload_fn=send_payload_fn,
                        edit_preview_fn=edit_preview_fn,
                        flush_draft_fn=flush_draft_lane_fn,
                        stop_draft_fn=stop_draft_lane_fn,
                        mark_delivered_fn=mark_delivered_fn,
                        log_fn=log_fn,
                    )
                    if archived_result2:
                        return archived_result2
                
                finalized = await _try_update_preview_for_lane(
                    lane=lane,
                    lane_name=lane_name,
                    text=text,
                    stop_before_edit=True,
                    skip_regressive="existingOnly",
                    context="final",
                    update_lane_snapshot=False,
                    edit_preview_fn=edit_preview_fn,
                    flush_draft_fn=flush_draft_lane_fn,
                    stop_draft_fn=stop_draft_lane_fn,
                    mark_delivered_fn=mark_delivered_fn,
                    log_fn=log_fn,
                )
                if finalized:
                    finalized_preview_by_lane[lane_name] = True
                    return "preview-finalized"
            elif not has_media and len(text) > draft_max_chars:
                log_fn(
                    f"telegram: preview final too long for edit "
                    f"({len(text)} > {draft_max_chars}); falling back to standard send"
                )
            
            # Fallback: stop and send new message
            if not draft_preview_stopped:
                await stop_draft_lane_fn(lane)
            
            delivered = await send_payload_fn(text)
            return "sent" if delivered else "skipped"
        
        # Non-final (partial update)
        if allow_preview_update_for_non_final and can_edit_via_preview:
            if _is_draft_preview_lane(lane):
                # Draft transport — check if update was emitted
                preview_revision_before = (
                    lane.stream.preview_revision()
                    if hasattr(lane.stream, "preview_revision") else 0
                )
                lane.stream.update(text)
                await flush_draft_lane_fn(lane)
                preview_revision_after = (
                    lane.stream.preview_revision()
                    if hasattr(lane.stream, "preview_revision") else 0
                )
                preview_updated = preview_revision_after > preview_revision_before
                
                if not preview_updated:
                    log_fn(
                        f"telegram: {lane_name} draft preview update not emitted; "
                        f"falling back to standard send"
                    )
                    delivered = await send_payload_fn(text)
                    return "sent" if delivered else "skipped"
                
                lane.last_partial_text = text
                mark_delivered_fn()
                return "preview-updated"
            
            # Message transport — try to edit
            updated = await _try_update_preview_for_lane(
                lane=lane,
                lane_name=lane_name,
                text=text,
                stop_before_edit=False,
                skip_regressive="always",
                context="update",
                update_lane_snapshot=True,
                edit_preview_fn=edit_preview_fn,
                flush_draft_fn=flush_draft_lane_fn,
                stop_draft_fn=stop_draft_lane_fn,
                mark_delivered_fn=mark_delivered_fn,
                log_fn=log_fn,
            )
            if updated:
                return "preview-updated"
        
        # Default: send as new message
        delivered = await send_payload_fn(text)
        return "sent" if delivered else "skipped"
    
    return deliver_lane_text


__all__ = [
    "LaneDeliveryResult",
    "LaneName",
    "ArchivedPreview",
    "DraftLaneState",
    "create_lane_text_deliverer",
]
