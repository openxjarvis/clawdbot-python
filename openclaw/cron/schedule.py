"""Schedule computation matching TypeScript openclaw/src/cron/schedule.ts"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter

from .types import AtSchedule, CronSchedule, CronScheduleType, EverySchedule

logger = logging.getLogger(__name__)


def compute_next_run(schedule: CronScheduleType, now_ms: int | None = None) -> int | None:
    """Compute next run time in milliseconds."""
    if now_ms is None:
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    try:
        if isinstance(schedule, AtSchedule):
            return _compute_at_schedule(schedule, now_ms)
        elif isinstance(schedule, EverySchedule):
            return _compute_every_schedule(schedule, now_ms)
        elif isinstance(schedule, CronSchedule):
            return _compute_cron_schedule(schedule, now_ms)
        else:
            logger.error(f"Unknown schedule type: {type(schedule)}")
            return None
    except Exception as e:
        logger.error(f"Error computing next run: {e}", exc_info=True)
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


def _compute_cron_schedule(schedule: CronSchedule, now_ms: int) -> int | None:
    """Cron expression schedule — matches TS computeNextRunAtMs for kind="cron"."""
    try:
        now_dt = datetime.fromtimestamp(now_ms / 1000, tz=timezone.utc)

        # Apply timezone if specified
        tz_str = schedule.tz or "UTC"
        try:
            tz = ZoneInfo(tz_str)
            now_dt = now_dt.astimezone(tz)
        except (ZoneInfoNotFoundError, Exception):
            pass  # Fallback to UTC

        cron = croniter(schedule.expr, now_dt)
        next_dt = cron.get_next(datetime)
        return int(next_dt.timestamp() * 1000)
    except Exception as e:
        logger.error(f"Error computing cron schedule for expr={schedule.expr!r}: {e}")
        return None


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
