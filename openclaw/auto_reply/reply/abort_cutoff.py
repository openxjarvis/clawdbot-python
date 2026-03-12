"""
Abort cutoff mechanism - mirrors openclaw/src/auto-reply/reply/abort-cutoff.ts

When user sends /stop, subsequent messages before abort completes should be skipped.
This prevents stale messages from being processed after the user has requested to stop.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict

__all__ = [
    "AbortCutoff",
    "set_abort_cutoff",
    "should_skip_message_by_abort_cutoff",
    "should_skip_message_by_abort_cutoff_v2",
    "clear_abort_cutoff",
    "apply_abort_cutoff_to_session_entry",
]


@dataclass
class AbortCutoff:
    """Abort cutoff information for a session."""
    timestamp: float  # Unix timestamp in seconds
    cutoff_id: str    # Message ID that triggered abort


# Global abort cutoffs registry
_ABORT_CUTOFFS: Dict[str, AbortCutoff] = {}


def set_abort_cutoff(session_key: str, cutoff_timestamp: float, cutoff_id: str) -> None:
    """
    Set abort cutoff for a session.
    
    Args:
        session_key: Session identifier
        cutoff_timestamp: Unix timestamp (seconds) when abort was triggered
        cutoff_id: Message ID that triggered the abort
    """
    _ABORT_CUTOFFS[session_key] = AbortCutoff(
        timestamp=cutoff_timestamp,
        cutoff_id=cutoff_id
    )


def should_skip_message_by_abort_cutoff(
    session_key: str, 
    message_timestamp: float,
    message_id: str | None = None
) -> bool:
    """
    Check if message should be skipped due to abort cutoff.
    
    Messages with timestamp <= cutoff timestamp are considered stale
    and should be skipped.
    
    Args:
        session_key: Session identifier
        message_timestamp: Unix timestamp (seconds) of the message
        message_id: Optional message ID (for logging/debugging)
        
    Returns:
        True if message should be skipped, False otherwise
    """
    cutoff = _ABORT_CUTOFFS.get(session_key)
    if not cutoff:
        return False
    
    # Skip messages that are older than or equal to the cutoff timestamp
    return message_timestamp <= cutoff.timestamp


def clear_abort_cutoff(session_key: str) -> None:
    """
    Clear abort cutoff after agent restart.
    
    Called when agent successfully restarts after abort,
    allowing new messages to be processed.
    
    Args:
        session_key: Session identifier
    """
    _ABORT_CUTOFFS.pop(session_key, None)


def apply_abort_cutoff_to_session_entry(session_entry: dict, session_key: str) -> None:
    """
    Apply abort cutoff timestamp to session entry.
    
    Mirrors TS applyAbortCutoffToSessionEntry - stores cutoff info
    in session metadata for persistence.
    
    Args:
        session_entry: Session entry dict to update
        session_key: Session identifier
    """
    cutoff = _ABORT_CUTOFFS.get(session_key)
    if cutoff:
        # Store in session metadata
        if "metadata" not in session_entry:
            session_entry["metadata"] = {}
        session_entry["metadata"]["abortCutoff"] = {
            "timestamp": cutoff.timestamp,
            "cutoffId": cutoff.cutoff_id
        }


def should_skip_message_by_abort_cutoff_v2(
    *,
    cutoff_message_sid: str | None = None,
    cutoff_timestamp: float | None = None,
    message_sid: str | None = None,
    timestamp: float | None = None,
) -> bool:
    """Session-entry-aware abort cutoff check.

    Mirrors TS ``shouldSkipMessageByAbortCutoff`` from abort-cutoff.ts.

    Prefers SID-based comparison (WhatsApp message SIDs are numeric strings
    that increase monotonically). Falls back to timestamp comparison.

    Returns True if the incoming message predates the cutoff and should be
    skipped.
    """
    cutoff_sid = (cutoff_message_sid or "").strip() or None
    current_sid = (message_sid or "").strip() or None

    if cutoff_sid and current_sid:
        # Numeric SID comparison (mirrors TS toNumericMessageSid logic)
        try:
            cutoff_num = int(cutoff_sid) if cutoff_sid.isdigit() else None
            current_num = int(current_sid) if current_sid.isdigit() else None
            if cutoff_num is not None and current_num is not None:
                return current_num <= cutoff_num
        except (ValueError, OverflowError):
            pass
        if current_sid == cutoff_sid:
            return True

    if (
        cutoff_timestamp is not None
        and isinstance(cutoff_timestamp, (int, float))
        and timestamp is not None
        and isinstance(timestamp, (int, float))
    ):
        return timestamp <= cutoff_timestamp

    return False


def get_abort_cutoff_from_session_entry(session_entry: dict, session_key: str) -> None:
    """
    Restore abort cutoff from session entry metadata.
    
    Called when loading session to restore abort state.
    
    Args:
        session_entry: Session entry dict
        session_key: Session identifier
    """
    metadata = session_entry.get("metadata", {})
    abort_cutoff_data = metadata.get("abortCutoff")
    
    if abort_cutoff_data:
        set_abort_cutoff(
            session_key=session_key,
            cutoff_timestamp=abort_cutoff_data.get("timestamp", 0),
            cutoff_id=abort_cutoff_data.get("cutoffId", "")
        )
