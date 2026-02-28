"""Subagent follow-up detection and waiting for cron isolated agent runs.

Mirrors TypeScript: openclaw/src/cron/isolated-agent/subagent-followup.ts
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

CRON_SUBAGENT_WAIT_POLL_MS = 500
CRON_SUBAGENT_WAIT_MIN_MS = 30_000
CRON_SUBAGENT_FINAL_REPLY_GRACE_MS = 5_000

# Token used to suppress cron delivery (matches TS SILENT_REPLY_TOKEN)
SILENT_REPLY_TOKEN = "\u25fb\ufe0f"

_INTERIM_HINTS: list[str] = [
    "on it",
    "pulling everything together",
    "give me a few",
    "give me a few min",
    "few minutes",
    "let me compile",
    "i'll gather",
    "i will gather",
    "working on it",
    "retrying now",
    "should be about",
    "should have your summary",
    "subagent spawned",
    "spawned a subagent",
    "it'll auto-announce when done",
    "it will auto-announce when done",
    "auto-announce when done",
    "both subagents are running",
    "wait for them to report back",
]

_FOLLOWUP_HINTS: list[str] = [
    "subagent spawned",
    "spawned a subagent",
    "auto-announce when done",
    "both subagents are running",
    "wait for them to report back",
]


def is_likely_interim_cron_message(value: str) -> bool:
    """Return True if the text looks like an in-progress / interim message.

    Mirrors TS isLikelyInterimCronMessage.
    """
    text = value.strip()
    if not text:
        return True
    normalized = " ".join(text.lower().split())
    words = [w for w in normalized.split(" ") if w]
    return len(words) <= 45 and any(hint in normalized for hint in _INTERIM_HINTS)


def expects_subagent_followup(value: str) -> bool:
    """Return True if the message hints that a subagent will report back later.

    Mirrors TS expectsSubagentFollowup.
    """
    normalized = " ".join(value.strip().lower().split())
    if not normalized:
        return False
    return any(hint in normalized for hint in _FOLLOWUP_HINTS)


async def read_descendant_subagent_fallback_reply(
    session_key: str,
    run_started_at: int,
) -> str | None:
    """Read the latest reply from completed descendant subagents.

    Mirrors TS readDescendantSubagentFallbackReply.

    Args:
        session_key: The cron job session key (requester).
        run_started_at: Millisecond timestamp when the cron run started.

    Returns:
        Combined reply text from descendant subagents, or None.
    """
    try:
        from openclaw.agents.subagent_registry import get_global_registry
        from openclaw.agents.subagent_announce import read_latest_subagent_output
    except ImportError:
        return None

    registry = get_global_registry()
    all_runs: list[Any] = registry.list_runs_for_requester(session_key)

    # Keep only runs that finished after run_started_at
    finished = [
        r for r in all_runs
        if r.ended_at is not None
        and r.ended_at >= run_started_at
        and r.child_session_key.strip()
    ]
    # Sort ascending by end time
    finished.sort(key=lambda r: r.ended_at or 0)

    if not finished:
        return None

    # Deduplicate: keep latest entry per child_session_key
    latest_by_child: dict[str, Any] = {}
    for entry in finished:
        key = entry.child_session_key.strip()
        if not key:
            continue
        existing = latest_by_child.get(key)
        if existing is None or (entry.ended_at or 0) >= (existing.ended_at or 0):
            latest_by_child[key] = entry

    # Take up to 4 most-recent children
    latest_runs = sorted(
        latest_by_child.values(), key=lambda r: r.ended_at or 0
    )[-4:]

    replies: list[str] = []
    for entry in latest_runs:
        try:
            reply_raw = await read_latest_subagent_output(
                entry.child_session_key, gateway=None
            )
            reply = (reply_raw or "").strip()
            if not reply:
                continue
            if reply.upper() == SILENT_REPLY_TOKEN.upper():
                continue
            replies.append(reply)
        except Exception as exc:
            logger.debug(
                f"read_descendant_subagent_fallback_reply: failed to read "
                f"reply for child {entry.child_session_key!r}: {exc}"
            )

    if not replies:
        return None
    if len(replies) == 1:
        return replies[0]
    return "\n\n".join(replies)


async def wait_for_descendant_subagent_summary(
    session_key: str,
    initial_reply: str | None = None,
    timeout_ms: int = CRON_SUBAGENT_WAIT_MIN_MS,
    observed_active_descendants: bool = False,
) -> str | None:
    """Poll until all descendant subagents have finished and a final reply is available.

    Mirrors TS waitForDescendantSubagentSummary.

    Args:
        session_key: The cron job session key (requester).
        initial_reply: The reply text observed at the start of the wait.
        timeout_ms: Maximum time to wait (ms). Enforced at minimum CRON_SUBAGENT_WAIT_MIN_MS.
        observed_active_descendants: True if active descendants were already observed.

    Returns:
        Final reply text, or None if no conclusive result.
    """
    try:
        from openclaw.agents.subagent_registry import get_global_registry
        from openclaw.agents.subagent_announce import read_latest_subagent_output
    except ImportError:
        return initial_reply

    registry = get_global_registry()

    initial = (initial_reply or "").strip()
    deadline = time.monotonic() + max(CRON_SUBAGENT_WAIT_MIN_MS, timeout_ms) / 1000.0
    saw_active = observed_active_descendants
    drained_at: float | None = None
    poll_s = CRON_SUBAGENT_WAIT_POLL_MS / 1000.0
    grace_s = CRON_SUBAGENT_FINAL_REPLY_GRACE_MS / 1000.0

    while time.monotonic() < deadline:
        active = registry.count_active_runs_for_session(session_key)

        if active > 0:
            saw_active = True
            drained_at = None
            await asyncio.sleep(poll_s)
            continue

        if not saw_active:
            return initial or None

        if drained_at is None:
            drained_at = time.monotonic()

        try:
            latest_raw = await read_latest_subagent_output(session_key, gateway=None)
            latest = (latest_raw or "").strip()
        except Exception:
            latest = ""

        if (
            latest
            and latest.upper() != SILENT_REPLY_TOKEN.upper()
            and (latest != initial or not is_likely_interim_cron_message(latest))
        ):
            return latest

        if time.monotonic() - drained_at >= grace_s:
            return None

        await asyncio.sleep(poll_s)

    # One last read after deadline
    try:
        latest_raw = await read_latest_subagent_output(session_key, gateway=None)
        latest = (latest_raw or "").strip()
    except Exception:
        latest = ""

    if (
        latest
        and latest.upper() != SILENT_REPLY_TOKEN.upper()
        and (latest != initial or not is_likely_interim_cron_message(latest))
    ):
        return latest

    return None
