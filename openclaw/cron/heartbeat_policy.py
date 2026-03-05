"""Cron heartbeat delivery policy helpers.

Mirrors TypeScript openclaw/src/cron/heartbeat-policy.ts.

Two key policy functions:
- ``should_skip_heartbeat_only_delivery`` — True when all delivery payloads
  are pure HEARTBEAT_OK acks with no real content.
- ``should_enqueue_cron_main_summary`` — decides whether to push the cron
  job's result text as a system event for the heartbeat to pick up.
"""
from __future__ import annotations

from typing import Any, Callable


def should_skip_heartbeat_only_delivery(
    payloads: list[dict[str, Any]],
    ack_max_chars: int = 300,
) -> bool:
    """Return True when all payloads are HEARTBEAT_OK-only with no real content.

    Mirrors TS shouldSkipHeartbeatOnlyDelivery().

    A payload is considered heartbeat-only when:
    - It has no media (no ``mediaUrl`` / ``mediaUrls``).
    - Its text, after stripping leading/trailing HEARTBEAT_OK tokens, is
      shorter than ``ack_max_chars``.

    An empty payloads list also triggers skip (nothing to deliver).
    """
    if not payloads:
        return True

    has_any_media = any(
        bool(p.get("mediaUrl")) or bool(p.get("mediaUrls"))
        for p in payloads
    )
    if has_any_media:
        return False

    def _strip_ok(text: str) -> str:
        stripped = text.strip()
        upper = stripped.upper()
        while upper.startswith("HEARTBEAT_OK"):
            stripped = stripped[len("HEARTBEAT_OK"):].strip()
            upper = stripped.upper()
        while upper.endswith("HEARTBEAT_OK"):
            stripped = stripped[: -len("HEARTBEAT_OK")].strip()
            upper = stripped.upper()
        return stripped

    return any(
        len(_strip_ok(p.get("text") or "")) <= ack_max_chars
        for p in payloads
    )


def should_enqueue_cron_main_summary(
    summary_text: str | None,
    delivery_requested: bool,
    delivered: bool | None,
    delivery_attempted: bool | None,
    suppress_main_summary: bool,
    is_cron_system_event: "Callable[[str], bool] | None" = None,
) -> bool:
    """Return True when the cron summary should be enqueued as a system event.

    Mirrors TS shouldEnqueueCronMainSummary().

    The summary is enqueued when:
    - ``summary_text`` is non-empty after stripping.
    - ``is_cron_system_event(summary_text)`` returns True (if provided).
    - Delivery was requested but not yet delivered.
    - ``suppress_main_summary`` is False.
    """
    text = (summary_text or "").strip()
    if not text:
        return False
    if is_cron_system_event is not None and not is_cron_system_event(text):
        return False
    if not delivery_requested:
        return False
    if delivered:
        return False
    if delivery_attempted:
        return False
    if suppress_main_summary:
        return False
    return True


__all__ = [
    "should_skip_heartbeat_only_delivery",
    "should_enqueue_cron_main_summary",
]
