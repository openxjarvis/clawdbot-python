"""Schedule computation matching TypeScript openclaw/src/cron/schedule.ts"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter

from .types import AtSchedule, CronSchedule, CronScheduleType, EverySchedule

logger = logging.getLogger(__name__)


def _resolve_cron_timezone(tz: str | None) -> ZoneInfo | None:
    """Resolve effective timezone for a cron expression.

    Mirrors TS ``resolveCronTimezone(tz?)``:
    - Non-empty string → use that IANA TZ
    - None / empty → fall back to **system local timezone**

    Falls back to UTC if the system TZ is unknown/unresolvable.
    """
    trimmed = tz.strip() if isinstance(tz, str) else ""
    if trimmed:
        try:
            return ZoneInfo(trimmed)
        except (ZoneInfoNotFoundError, Exception) as exc:
            logger.warning("cron: unknown timezone %r — falling back to system TZ: %s", trimmed, exc)
            return None  # will fall through to system-TZ logic below

    # No explicit tz → use system local timezone (mirrors TS Intl.DateTimeFormat().resolvedOptions().timeZone)
    try:
        # datetime.now().astimezone() carries the local tzinfo; use it directly.
        local_tz = datetime.now().astimezone().tzinfo
        if local_tz is not None:
            return local_tz  # type: ignore[return-value]
    except Exception:
        pass
    # Ultimate fallback: UTC
    return ZoneInfo("UTC")


def compute_next_run(schedule: CronScheduleType, now_ms: int | None = None) -> int | None:
    """Compute next run time in milliseconds.

    Exceptions from ``_compute_cron_schedule`` (e.g. invalid cron expressions)
    are intentionally NOT caught here — they propagate to callers such as
    ``_recompute_job_next_run`` which tracks schedule errors via
    ``_record_schedule_error``.  This mirrors TS behaviour where
    ``computeJobNextRunAtMs`` throws on bad expressions.
    """
    if now_ms is None:
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    if isinstance(schedule, AtSchedule):
        return _compute_at_schedule(schedule, now_ms)
    elif isinstance(schedule, EverySchedule):
        return _compute_every_schedule(schedule, now_ms)
    elif isinstance(schedule, CronSchedule):
        return _compute_cron_schedule(schedule, now_ms)
    else:
        logger.error(f"Unknown schedule type: {type(schedule)}")
        return None


def _compute_at_schedule(schedule: AtSchedule, now_ms: int) -> int | None:
    """One-time timestamp schedule — matches TS computeNextRunAtMs for kind="at"."""
    from .normalize import parse_absolute_time_ms
    at_val = schedule.at or ""
    run_ms = parse_absolute_time_ms(at_val)
    if run_ms is None:
        logger.debug(f"at schedule: could not parse timestamp {at_val!r}")
        return None
    # One-shot jobs remain due (return atMs) regardless of whether it's past
    return run_ms


def _compute_every_schedule(schedule: EverySchedule, now_ms: int) -> int | None:
    """Interval schedule — mirrors TS computeNextRunAtMs for kind="every"."""
    every_ms = schedule.every_ms
    if every_ms <= 0:
        logger.error(f"Invalid everyMs: {every_ms}")
        return None

    # Resolve anchor (epoch ms)
    anchor_ms = schedule.anchor_ms if schedule.anchor_ms is not None else 0
    if anchor_ms <= 0:
        anchor_ms = 0

    elapsed_ms = now_ms - anchor_ms
    if elapsed_ms < 0:
        # Anchor is in the future
        return anchor_ms

    intervals_passed = elapsed_ms // every_ms
    return anchor_ms + (intervals_passed + 1) * every_ms


def _compute_cron_schedule(schedule: CronSchedule, now_ms: int) -> int:
    """Cron expression schedule — matches TS computeNextRunAtMs for kind="cron".

    Timezone resolution mirrors TS ``resolveCronTimezone(tz?)``:
    - ``schedule.tz`` is a non-empty IANA string → use it directly
    - ``schedule.tz`` is None/empty → fall back to the **system local timezone**
      (same as TS ``Intl.DateTimeFormat().resolvedOptions().timeZone``)

    Raises ``ValueError`` on invalid expression so that callers (e.g.
    ``_recompute_job_next_run``) can catch it and record a schedule error.
    """
    now_dt = datetime.fromtimestamp(now_ms / 1000, tz=timezone.utc)

    # Resolve effective timezone (None → system TZ, matches TS resolveCronTimezone)
    effective_tz = _resolve_cron_timezone(schedule.tz)
    if effective_tz is not None:
        now_dt = now_dt.astimezone(effective_tz)

    try:
        cron = croniter(schedule.expr, now_dt)
        next_dt = cron.get_next(datetime)
        return int(next_dt.timestamp() * 1000)
    except Exception as e:
        raise ValueError(f"invalid cron expression {schedule.expr!r}: {e}") from e


def format_next_run(next_run_ms: int | None) -> str:
    if next_run_ms is None:
        return "Never"
    try:
        dt = datetime.fromtimestamp(next_run_ms / 1000, tz=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = dt - now
        s = delta.total_seconds()
        if s < 0:
            return f"{dt.isoformat()} (overdue)"
        elif s < 60:
            return f"in {int(s)}s"
        elif s < 3600:
            return f"in {int(s / 60)}m"
        elif s < 86400:
            return f"in {int(s / 3600)}h"
        else:
            return f"in {int(s / 86400)}d"
    except Exception:
        return "Unknown"


def is_due(next_run_ms: int | None, now_ms: int | None = None) -> bool:
    if next_run_ms is None:
        return False
    if now_ms is None:
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    return next_run_ms <= now_ms
