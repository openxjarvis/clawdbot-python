"""Reminder commitment guard — appends a note when the model commits to scheduling a
reminder but did not actually create a cron job in the same turn.

Mirrors TypeScript ``src/auto-reply/reply/agent-runner-reminder-guard.ts``.
"""
from __future__ import annotations

import re
from typing import Any

from openclaw.auto_reply.reply.get_reply import ReplyPayload

UNSCHEDULED_REMINDER_NOTE = (
    "Note: I did not schedule a reminder in this turn, so this will not trigger automatically."
)

_REMINDER_COMMITMENT_PATTERNS: list[re.Pattern] = [
    re.compile(
        r"\b(?:i\s*['']?ll|i will)\s+(?:make sure to\s+)?(?:remember|remind|ping|follow up|follow-up|check back|circle back)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:i\s*['']?ll|i will)\s+(?:set|create|schedule)\s+(?:a\s+)?reminder\b",
        re.IGNORECASE,
    ),
]


def has_unbacked_reminder_commitment(text: str) -> bool:
    """Return True when *text* contains a reminder promise without a guard note.

    Mirrors TS ``hasUnbackedReminderCommitment``.
    """
    normalized = text.lower()
    if not normalized.strip():
        return False
    if UNSCHEDULED_REMINDER_NOTE.lower() in normalized:
        return False
    return any(p.search(text) for p in _REMINDER_COMMITMENT_PATTERNS)


async def has_session_related_cron_jobs(
    *,
    cron_store_path: str | None = None,
    session_key: str | None = None,
) -> bool:
    """Return True when an existing enabled cron job covers this session.

    Mirrors TS ``hasSessionRelatedCronJobs``.  Reads the cron store to check
    whether any active job is associated with *session_key*.
    """
    if not session_key:
        return False
    try:
        from openclaw.cron.store import load_cron_store, resolve_cron_store_path
        store_path = resolve_cron_store_path(cron_store_path)
        store = await load_cron_store(store_path)
        jobs = getattr(store, "jobs", None) or (store.get("jobs") if isinstance(store, dict) else []) or []
        if not jobs:
            return False
        for job in jobs:
            if isinstance(job, dict):
                if job.get("enabled") and job.get("sessionKey") == session_key:
                    return True
            else:
                if getattr(job, "enabled", False) and getattr(job, "session_key", None) == session_key:
                    return True
    except Exception:
        pass
    return False


def append_unscheduled_reminder_note(payloads: list[ReplyPayload]) -> list[ReplyPayload]:
    """Append the unscheduled-reminder note to the first matching payload.

    Mirrors TS ``appendUnscheduledReminderNote``.
    Only the first payload that contains a reminder commitment is annotated.
    Error payloads and non-text payloads are skipped.
    """
    appended = False
    result: list[ReplyPayload] = []
    for payload in payloads:
        if appended or getattr(payload, "is_error", False) or not isinstance(payload.text, str):
            result.append(payload)
            continue
        if not has_unbacked_reminder_commitment(payload.text):
            result.append(payload)
            continue
        appended = True
        trimmed = payload.text.rstrip()
        new_payload = ReplyPayload(
            text=f"{trimmed}\n\n{UNSCHEDULED_REMINDER_NOTE}",
            **{k: v for k, v in vars(payload).items() if k != "text"},
        )
        result.append(new_payload)
    return result


__all__ = [
    "UNSCHEDULED_REMINDER_NOTE",
    "has_unbacked_reminder_commitment",
    "has_session_related_cron_jobs",
    "append_unscheduled_reminder_note",
]
