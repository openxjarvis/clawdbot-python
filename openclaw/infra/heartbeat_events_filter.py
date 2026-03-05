"""Heartbeat events filter utilities.

Mirrors TypeScript openclaw/src/infra/heartbeat-events-filter.ts.

Provides helpers for building LLM prompts and classifying system events
used by cron jobs and exec-completion heartbeats.
"""
from __future__ import annotations

HEARTBEAT_OK_PREFIX = "heartbeat_ok"


# ---------------------------------------------------------------------------
# Prompt builders (mirrors TS buildCronEventPrompt / buildExecEventPrompt)
# ---------------------------------------------------------------------------


def build_cron_event_prompt(
    pending_events: list[str],
    deliver_to_user: bool = True,
) -> str:
    """Build the LLM prompt for a cron-triggered heartbeat.

    Mirrors TS buildCronEventPrompt().
    """
    event_text = "\n".join(pending_events).strip()
    if not event_text:
        if not deliver_to_user:
            return (
                "A scheduled cron event was triggered, but no event content was found. "
                "Handle this internally and reply HEARTBEAT_OK when nothing needs user-facing follow-up."
            )
        return (
            "A scheduled cron event was triggered, but no event content was found. "
            "Reply HEARTBEAT_OK."
        )
    if not deliver_to_user:
        return (
            "A scheduled reminder has been triggered. The reminder content is:\n\n"
            + event_text
            + "\n\nHandle this reminder internally. Do not relay it to the user unless explicitly requested."
        )
    return (
        "A scheduled reminder has been triggered. The reminder content is:\n\n"
        + event_text
        + "\n\nPlease relay this reminder to the user in a helpful and friendly way."
    )


def build_exec_event_prompt(deliver_to_user: bool = True) -> str:
    """Build the LLM prompt for an exec-event triggered heartbeat.

    Mirrors TS buildExecEventPrompt().
    """
    if not deliver_to_user:
        return (
            "An async command you ran earlier has completed. "
            "The result is shown in the system messages above. "
            "Handle the result internally. Do not relay it to the user unless explicitly requested."
        )
    return (
        "An async command you ran earlier has completed. "
        "The result is shown in the system messages above. "
        "Please relay the command output to the user in a helpful way. "
        "If the command succeeded, share the relevant output. "
        "If it failed, explain what went wrong."
    )


# ---------------------------------------------------------------------------
# Event classifiers (mirrors TS isCronSystemEvent / isExecCompletionEvent)
# ---------------------------------------------------------------------------


def _is_heartbeat_ack_event(evt: str) -> bool:
    trimmed = evt.strip()
    if not trimmed:
        return False
    lower = trimmed.lower()
    if not lower.startswith(HEARTBEAT_OK_PREFIX):
        return False
    suffix = lower[len(HEARTBEAT_OK_PREFIX):]
    if not suffix:
        return True
    # Not an ack if the next char is alphanumeric or underscore (e.g. "HEARTBEAT_OK_EXTRA")
    return not (suffix[0].isalnum() or suffix[0] == "_")


def _is_heartbeat_noise_event(evt: str) -> bool:
    lower = evt.strip().lower()
    if not lower:
        return False
    return (
        _is_heartbeat_ack_event(lower)
        or "heartbeat poll" in lower
        or "heartbeat wake" in lower
    )


def is_exec_completion_event(evt: str) -> bool:
    """Return True when the event string signals an exec-finished completion."""
    return "exec finished" in evt.lower()


def is_cron_system_event(evt: str) -> bool:
    """Return True when a system event should be treated as real cron reminder content.

    Mirrors TS isCronSystemEvent().
    """
    if not evt.strip():
        return False
    return not _is_heartbeat_noise_event(evt) and not is_exec_completion_event(evt)


__all__ = [
    "build_cron_event_prompt",
    "build_exec_event_prompt",
    "is_cron_system_event",
    "is_exec_completion_event",
]
