"""
Echo detection to prevent responding to own messages.

Tracks outbound messages to detect when they echo back,
preventing infinite reply loops.

Matches openclaw/src/web/auto-reply/echo-tracker.ts

TS alignment: TS echoTracker tracks by TEXT CONTENT (not message ID).
The bot hashes the text of every outbound reply and checks incoming
messages against that set. This prevents the bot from replying to its
own outbound messages that arrive back on the inbound stream.
"""
from __future__ import annotations

import hashlib
import time


def _text_key(text: str) -> str:
    """Stable key for a text string — trim + lowercase hash."""
    normalized = text.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8", errors="replace")).hexdigest()[:32]


class EchoTracker:
    """
    Tracks outbound messages to detect echoes by TEXT CONTENT.

    Mirrors TS EchoTracker which tracks sent text, not message IDs.
    Usage:
        tracker = EchoTracker(window_seconds=30)

        # When we send a message, remember its text
        tracker.remember_text("Hello, how can I help?")

        # Check an incoming message
        if tracker.has_text("Hello, how can I help?"):
            return  # skip — this is our own echo
    """

    def __init__(self, window_seconds: int = 30):
        self._outbound_by_id: dict[str, float] = {}   # message_id -> timestamp (legacy)
        self._outbound_by_text: dict[str, float] = {}  # text_key  -> timestamp
        self._window = window_seconds

    # ------------------------------------------------------------------
    # Text-based tracking (primary, mirrors TS behaviour)
    # ------------------------------------------------------------------

    def remember_text(self, text: str) -> None:
        """Record outbound *text* so we can detect its echo.

        Mirrors TS ``echoTracker.remember(text)``.
        """
        if not text or not text.strip():
            return
        key = _text_key(text)
        self._outbound_by_text[key] = time.time()
        self._cleanup()

    def has_text(self, text: str) -> bool:
        """Return True and consume the entry if *text* matches a remembered outbound reply.

        Mirrors TS ``echoTracker.has(text)``.
        """
        if not text or not text.strip():
            return False
        key = _text_key(text)
        ts = self._outbound_by_text.get(key)
        if ts is None:
            return False
        now = time.time()
        if now - ts > self._window:
            del self._outbound_by_text[key]
            return False
        del self._outbound_by_text[key]
        return True

    def forget_text(self, text: str) -> None:
        """Explicitly remove a text entry (e.g. after confirmed delivery)."""
        if not text or not text.strip():
            return
        self._outbound_by_text.pop(_text_key(text), None)

    # ------------------------------------------------------------------
    # ID-based tracking (legacy / backward compat)
    # ------------------------------------------------------------------

    def mark_outbound(self, message_id: str) -> None:
        """Mark a message ID as outbound (legacy API)."""
        if not message_id:
            return
        self._outbound_by_id[message_id] = time.time()
        self._cleanup()

    def is_echo(self, message_id: str) -> bool:
        """Check if *message_id* was sent by us (legacy API)."""
        if not message_id:
            return False
        if message_id in self._outbound_by_id:
            del self._outbound_by_id[message_id]
            return True
        return False

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def _cleanup(self) -> None:
        now = time.time()
        for d in (self._outbound_by_id, self._outbound_by_text):
            expired = [k for k, ts in d.items() if now - ts > self._window]
            for k in expired:
                del d[k]

    def clear(self) -> None:
        self._outbound_by_id.clear()
        self._outbound_by_text.clear()

    def count(self) -> int:
        return len(self._outbound_by_id) + len(self._outbound_by_text)


__all__ = [
    "EchoTracker",
]
