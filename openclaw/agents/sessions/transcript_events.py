"""Session transcript update events — matches openclaw/src/sessions/transcript-events.ts"""
from __future__ import annotations

from typing import Callable, Dict, Set

SessionTranscriptListener = Callable[[Dict[str, str]], None]

_SESSION_TRANSCRIPT_LISTENERS: Set[SessionTranscriptListener] = set()


def on_session_transcript_update(
    listener: SessionTranscriptListener,
) -> Callable[[], None]:
    """
    Subscribe to session transcript update events.

    Returns an unsubscribe callable.

    Matches TS onSessionTranscriptUpdate().
    """
    _SESSION_TRANSCRIPT_LISTENERS.add(listener)

    def unsubscribe() -> None:
        _SESSION_TRANSCRIPT_LISTENERS.discard(listener)

    return unsubscribe


def emit_session_transcript_update(session_file: str) -> None:
    """
    Emit a session transcript update event to all subscribers.

    No-op if session_file is empty.

    Matches TS emitSessionTranscriptUpdate().
    """
    trimmed = (session_file or "").strip()
    if not trimmed:
        return
    update = {"sessionFile": trimmed}
    for listener in list(_SESSION_TRANSCRIPT_LISTENERS):
        listener(update)


__all__ = [
    "SessionTranscriptListener",
    "on_session_transcript_update",
    "emit_session_transcript_update",
]
