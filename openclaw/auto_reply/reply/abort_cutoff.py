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
