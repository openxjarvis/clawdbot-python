"""
Followup run queue — aligned with TypeScript
openclaw/src/auto-reply/reply/queue/*.ts.

Manages per-session queues for deferring / batching followup agent runs
that arrive while another turn is executing.

Public API:
  clear_session_queues(keys)          → ClearSessionQueueResult
  enqueue_followup_run(key, run, ...) → bool
  schedule_followup_drain(key, fn)    → None
  get_followup_queue_depth(key)       → int
  clear_followup_queue(key)           → int
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Literal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Types — mirrors TS queue/types.ts
# ---------------------------------------------------------------------------

QueueMode = Literal["steer", "followup", "collect", "steer-backlog", "interrupt", "queue"]
QueueDropPolicy = Literal["old", "new", "summarize"]
QueueDedupeMode = Literal["message-id", "prompt", "none"]


@dataclass
class QueueSettings:
    mode: QueueMode = "followup"
    debounce_ms: int | None = None
    cap: int | None = None
    drop_policy: QueueDropPolicy | None = None


@dataclass
class FollowupRun:
    """A single deferred agent turn — mirrors TS FollowupRun."""
    prompt: str
    run: dict[str, Any]
    enqueued_at: int = field(default_factory=lambda: int(time.time() * 1000))
    message_id: str | None = None
    summary_line: str | None = None
    originating_channel: str | None = None
    originating_to: str | None = None
    originating_account_id: str | None = None
    originating_thread_id: str | int | None = None
    originating_chat_type: str | None = None


@dataclass
class ClearSessionQueueResult:
    followup_cleared: int = 0
    lane_cleared: int = 0
    keys: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# State — mirrors TS queue/state.ts
# ---------------------------------------------------------------------------

DEFAULT_QUEUE_DEBOUNCE_MS = 1_000
DEFAULT_QUEUE_CAP = 20
DEFAULT_QUEUE_DROP: QueueDropPolicy = "summarize"

_FOLLOWUP_QUEUES: dict[str, "_FollowupQueueState"] = {}


@dataclass
class _FollowupQueueState:
    items: list[FollowupRun] = field(default_factory=list)
    draining: bool = False
    last_enqueued_at: int = 0
    mode: QueueMode = "followup"
    debounce_ms: int = DEFAULT_QUEUE_DEBOUNCE_MS
    cap: int = DEFAULT_QUEUE_CAP
    drop_policy: QueueDropPolicy = DEFAULT_QUEUE_DROP
    dropped_count: int = 0
    summary_lines: list[str] = field(default_factory=list)
    last_run: dict[str, Any] | None = None


def _get_followup_queue(key: str, settings: QueueSettings) -> _FollowupQueueState:
    """Get or create a queue for *key*, updating mutable settings."""
    existing = _FOLLOWUP_QUEUES.get(key)
    if existing is not None:
        existing.mode = settings.mode
        if settings.debounce_ms is not None and isinstance(settings.debounce_ms, int):
            existing.debounce_ms = max(0, settings.debounce_ms)
        if settings.cap is not None and isinstance(settings.cap, int) and settings.cap > 0:
            existing.cap = int(settings.cap)
        if settings.drop_policy is not None:
            existing.drop_policy = settings.drop_policy
        return existing

    created = _FollowupQueueState(
        mode=settings.mode,
        debounce_ms=(
            max(0, settings.debounce_ms) if settings.debounce_ms is not None else DEFAULT_QUEUE_DEBOUNCE_MS
        ),
        cap=(
            int(settings.cap) if settings.cap is not None and settings.cap > 0 else DEFAULT_QUEUE_CAP
        ),
        drop_policy=settings.drop_policy if settings.drop_policy is not None else DEFAULT_QUEUE_DROP,
    )
    _FOLLOWUP_QUEUES[key] = created
    return created


def clear_followup_queue(key: str) -> int:
    """Clear a session's followup queue.

    Mirrors TS clearFollowupQueue().
    Returns the number of items cleared (queued + dropped).
    """
    cleaned = key.strip()
    if not cleaned:
        return 0
    queue = _FOLLOWUP_QUEUES.get(cleaned)
    if not queue:
        return 0
    cleared = len(queue.items) + queue.dropped_count
    queue.items.clear()
    queue.dropped_count = 0
    queue.summary_lines = []
    queue.last_run = None
    queue.last_enqueued_at = 0
    del _FOLLOWUP_QUEUES[cleaned]
    return cleared


# ---------------------------------------------------------------------------
# Cleanup — mirrors TS queue/cleanup.ts
# ---------------------------------------------------------------------------

def clear_session_queues(keys: list[str | None]) -> ClearSessionQueueResult:
    """Clear followup queues for a list of session keys.

    Mirrors TS clearSessionQueues().
    Also attempts to clear embedded session command lanes if available.
    """
    seen: set[str] = set()
    followup_cleared = 0
    lane_cleared = 0
    cleared_keys: list[str] = []

    for key in keys:
        cleaned = (key or "").strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        cleared_keys.append(cleaned)
        followup_cleared += clear_followup_queue(cleaned)

        # Attempt to clear the embedded session command lane (optional)
        try:
            from openclaw.agents.pi_embedded import resolve_embedded_session_lane  # type: ignore[import]
            from openclaw.process.command_queue import clear_command_lane  # type: ignore[import]
            lane = resolve_embedded_session_lane(cleaned)
            lane_cleared += clear_command_lane(lane)
        except Exception:
            pass

    return ClearSessionQueueResult(
        followup_cleared=followup_cleared,
        lane_cleared=lane_cleared,
        keys=cleared_keys,
    )


# ---------------------------------------------------------------------------
# Enqueue — mirrors TS queue/enqueue.ts
# ---------------------------------------------------------------------------

def _is_run_already_queued(
    run: FollowupRun,
    items: list[FollowupRun],
    allow_prompt_fallback: bool = False,
) -> bool:
    def has_same_routing(item: FollowupRun) -> bool:
        return (
            item.originating_channel == run.originating_channel
            and item.originating_to == run.originating_to
            and item.originating_account_id == run.originating_account_id
            and item.originating_thread_id == run.originating_thread_id
        )

    message_id = (run.message_id or "").strip()
    if message_id:
        return any(
            (item.message_id or "").strip() == message_id and has_same_routing(item)
            for item in items
        )
    if not allow_prompt_fallback:
        return False
    return any(item.prompt == run.prompt and has_same_routing(item) for item in items)


def _apply_drop_policy(queue: _FollowupQueueState, item: FollowupRun) -> bool:
    """Apply drop policy; return True if the item should be enqueued."""
    if len(queue.items) < queue.cap:
        return True
    if queue.drop_policy == "new":
        # Drop the incoming item
        queue.dropped_count += 1
        summary = (item.summary_line or "").strip() or item.prompt.strip()
        if summary:
            queue.summary_lines.append(summary)
        return False
    if queue.drop_policy == "old":
        # Drop the oldest item
        removed = queue.items.pop(0)
        queue.dropped_count += 1
        old_summary = (removed.summary_line or "").strip() or removed.prompt.strip()
        if old_summary:
            queue.summary_lines.append(old_summary)
        return True
    # "summarize" — same as "old" but accumulate summary lines
    removed = queue.items.pop(0)
    queue.dropped_count += 1
    old_summary = (removed.summary_line or "").strip() or removed.prompt.strip()
    if old_summary:
        queue.summary_lines.append(old_summary)
    return True


def enqueue_followup_run(
    key: str,
    run: FollowupRun,
    settings: QueueSettings,
    dedupe_mode: QueueDedupeMode = "message-id",
) -> bool:
    """Enqueue a followup run for the given session key.

    Mirrors TS enqueueFollowupRun().
    Returns True if the run was added, False if it was deduplicated or dropped.
    """
    queue = _get_followup_queue(key, settings)

    if dedupe_mode != "none":
        allow_prompt_fallback = dedupe_mode == "prompt"
        if _is_run_already_queued(run, queue.items, allow_prompt_fallback):
            return False

    queue.last_enqueued_at = int(time.time() * 1000)
    queue.last_run = run.run

    if not _apply_drop_policy(queue, run):
        return False

    queue.items.append(run)
    return True


def get_followup_queue_depth(key: str) -> int:
    """Return the number of items in the queue for *key*.

    Mirrors TS getFollowupQueueDepth().
    """
    cleaned = key.strip()
    if not cleaned:
        return 0
    queue = _FOLLOWUP_QUEUES.get(cleaned)
    return len(queue.items) if queue else 0


# ---------------------------------------------------------------------------
# Drain — mirrors TS queue/drain.ts
# ---------------------------------------------------------------------------

def _has_cross_channel_items(items: list[FollowupRun]) -> bool:
    """Return True when items originate from multiple channels.

    Mirrors TS ``hasCrossChannelItems`` in ``queue/drain.ts``.
    """
    channels: set[str] = set()
    for item in items:
        ch = (item.originating_channel or "").strip()
        to = str((item.originating_to or "")).strip()
        channels.add(f"{ch}::{to}")
    return len(channels) > 1


def _build_collect_prompt(items: list[FollowupRun], summary_lines: list[str]) -> str:
    """Build a merged prompt for collect mode.

    Mirrors TS ``buildCollectPrompt`` in ``utils/queue-helpers.ts``.
    """
    title = "[Queued messages while agent was busy]"
    body_parts: list[str] = []
    if summary_lines:
        preview = "Dropped messages (summarized):\n" + "\n".join(f"- {s}" for s in summary_lines)
        body_parts.append(preview)
    for item in items:
        body_parts.append(item.prompt.strip())
    return title + "\n\n" + "\n\n".join(body_parts)


async def _wait_for_debounce(queue: "_FollowupQueueState") -> None:
    """Wait until debounce window has elapsed since the last enqueue.

    Mirrors TS ``waitForQueueDebounce``: waits until
    ``now - last_enqueued_at >= debounce_ms``, polling every 50 ms.
    """
    if queue.debounce_ms <= 0:
        return
    deadline_s = queue.debounce_ms / 1000.0
    while True:
        elapsed = time.time() - queue.last_enqueued_at / 1000.0
        remaining = deadline_s - elapsed
        if remaining <= 0:
            return
        await asyncio.sleep(min(remaining, 0.05))


def schedule_followup_drain(
    key: str,
    run_followup: Callable[[FollowupRun], Awaitable[None]],
) -> None:
    """Schedule asynchronous draining of the followup queue for *key*.

    Mirrors TS scheduleFollowupDrain().
    Fires a background asyncio task; does nothing if already draining.
    """
    queue = _FOLLOWUP_QUEUES.get(key)
    if not queue or queue.draining:
        return
    queue.draining = True

    async def _drain() -> None:
        try:
            while queue.items or queue.dropped_count > 0:
                # Debounce: wait until debounce_ms has passed since last enqueue
                # (mirrors TS waitForQueueDebounce — NOT a fixed sleep)
                await _wait_for_debounce(queue)

                if not queue.items:
                    break

                cross_channel = _has_cross_channel_items(queue.items)

                if queue.mode == "collect" and len(queue.items) > 1 and not cross_channel:
                    # Collect mode: merge all queued prompts into one run
                    first = queue.items[0]
                    merged_prompt = _build_collect_prompt(queue.items, queue.summary_lines)
                    queue.items.clear()
                    queue.dropped_count = 0
                    queue.summary_lines = []
                    merged = FollowupRun(
                        prompt=merged_prompt,
                        run=first.run,
                        enqueued_at=first.enqueued_at,
                        originating_channel=first.originating_channel,
                        originating_to=first.originating_to,
                        originating_account_id=first.originating_account_id,
                        originating_thread_id=first.originating_thread_id,
                    )
                    try:
                        await run_followup(merged)
                    except Exception as exc:
                        logger.warning(f"Followup drain error (collect): {exc}")
                else:
                    # Individual drain (cross-channel or non-collect mode)
                    # Flush dropped-item summary into the next run if needed
                    if queue.dropped_count > 0 and queue.summary_lines:
                        summary = "Previous messages:\n" + "\n".join(queue.summary_lines)
                        queue.dropped_count = 0
                        queue.summary_lines = []
                        if queue.items:
                            first = queue.items[0]
                            queue.items[0] = FollowupRun(
                                prompt=summary + "\n\n" + first.prompt,
                                run=first.run,
                                enqueued_at=first.enqueued_at,
                                message_id=first.message_id,
                                summary_line=first.summary_line,
                                originating_channel=first.originating_channel,
                                originating_to=first.originating_to,
                                originating_account_id=first.originating_account_id,
                                originating_thread_id=first.originating_thread_id,
                            )

                    if not queue.items:
                        break

                    run = queue.items.pop(0)
                    try:
                        await run_followup(run)
                    except Exception as exc:
                        logger.warning(f"Followup drain error: {exc}")
        finally:
            queue.draining = False
            # Mirrors TS: if new items arrived while we were draining, schedule
            # another drain pass so they are not silently lost.
            if queue.items:
                schedule_followup_drain(key, run_followup)
            elif queue.dropped_count == 0:
                _FOLLOWUP_QUEUES.pop(key, None)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_drain())
    except RuntimeError:
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(_drain())
        except RuntimeError:
            pass
