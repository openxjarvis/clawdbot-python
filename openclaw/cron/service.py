"""Cron job scheduling service — aligned with TypeScript openclaw/src/cron/

Matches: service/ops.ts, service/timer.ts, service/jobs.ts
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Awaitable, Dict, Literal, Optional

from .locked import locked
from .types import (
    CronJob,
    CronJobState,
    AgentTurnPayload,
    SystemEventPayload,
    AtSchedule,
    EverySchedule,
    CronSchedule as CronScheduleType,
    CronDelivery,
)
from .schedule import compute_next_run
from .timer import CronTimer, MAX_TIMER_DELAY_MS
from .store import CronStore, CronRunLog

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants (mirrors TS service/timer.ts)
# ---------------------------------------------------------------------------

MIN_REFIRE_GAP_MS = 2_000          # Safety net for cron spin-loops
DEFAULT_JOB_TIMEOUT_MS = 10 * 60_000  # 10 minutes per job
MAX_SCHEDULE_ERRORS = 3            # Auto-disable after this many consecutive schedule errors
STUCK_RUN_MS = 2 * 60 * 60 * 1000 # Clear stale running_at_ms after 2 h

# Exponential backoff indexed by consecutive error count (0-based)
ERROR_BACKOFF_SCHEDULE_MS = [
    30_000,        # 1st error  →  30 s
    60_000,        # 2nd error  →   1 min
    5 * 60_000,    # 3rd error  →   5 min
    15 * 60_000,   # 4th error  →  15 min
    60 * 60_000,   # 5th+ error →  60 min
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _error_backoff_ms(consecutive_errors: int) -> int:
    idx = min(consecutive_errors - 1, len(ERROR_BACKOFF_SCHEDULE_MS) - 1)
    return ERROR_BACKOFF_SCHEDULE_MS[max(0, idx)]


def _resolve_stable_cron_offset_ms(job_id: str, stagger_ms: int) -> int:
    """Deterministic per-job SHA256-based stagger offset in [0, stagger_ms)."""
    if stagger_ms <= 1:
        return 0
    digest = hashlib.sha256(job_id.encode()).digest()
    return int.from_bytes(digest[:4], "big") % stagger_ms


def _compute_staggered_cron_next_run(job: CronJob, now_ms: int) -> int | None:
    """Compute next run for cron schedule with deterministic stagger offset."""
    if not isinstance(job.schedule, CronScheduleType):
        return compute_next_run(job.schedule, now_ms)

    from .normalize import resolve_cron_stagger_ms
    stagger_ms = resolve_cron_stagger_ms(job.schedule)
    offset_ms = _resolve_stable_cron_offset_ms(job.id, stagger_ms)

    if offset_ms <= 0:
        return compute_next_run(job.schedule, now_ms)

    # Shift cursor backwards so we can still catch the current window
    cursor_ms = max(0, now_ms - offset_ms)
    for _ in range(4):
        base_next = compute_next_run(job.schedule, cursor_ms)
        if base_next is None:
            return None
        shifted = base_next + offset_ms
        if shifted > now_ms:
            return shifted
        cursor_ms = max(cursor_ms + 1, base_next + 1_000)
    return None


def compute_job_next_run_at_ms(job: CronJob, now_ms: int) -> int | None:
    """Compute next run time for a job (matches TS computeJobNextRunAtMs)."""
    if not job.enabled:
        return None

    if isinstance(job.schedule, EverySchedule):
        # Resolve anchor: explicit anchor_ms or job creation time
        anchor_ms = job.schedule.anchor_ms
        if anchor_ms is None:
            anchor_ms = job.created_at_ms
        sched_with_anchor = EverySchedule(
            every_ms=job.schedule.every_ms,
            type="every",
            anchor_ms=anchor_ms,
        )
        return compute_next_run(sched_with_anchor, now_ms)

    if isinstance(job.schedule, AtSchedule):
        # One-shot: stays due until it successfully finishes
        if job.state.last_status == "ok" and job.state.last_run_at_ms:
            return None
        from .normalize import parse_absolute_time_ms
        at_ms = parse_absolute_time_ms(job.schedule.at) if job.schedule.at else None
        return at_ms

    # CronSchedule — use staggered computation
    nxt = _compute_staggered_cron_next_run(job, now_ms)
    if nxt is None:
        # Retry with next-second cursor (TS does the same)
        next_second_ms = (now_ms // 1000 + 1) * 1000
        nxt = _compute_staggered_cron_next_run(job, next_second_ms)
    return nxt


def _record_schedule_error(job: CronJob, err: Exception) -> None:
    """Track consecutive schedule computation errors, auto-disable after threshold."""
    count = (job.state.schedule_error_count or 0) + 1
    job.state.schedule_error_count = count
    job.state.next_run_ms = None
    job.state.last_error = f"schedule error: {err}"

    if count >= MAX_SCHEDULE_ERRORS:
        job.enabled = False
        logger.error(
            f"cron: auto-disabled job {job.id!r} ({job.name!r}) "
            f"after {count} consecutive schedule errors: {err}"
        )
    else:
        logger.warning(
            f"cron: failed to compute next run for job {job.id!r} "
            f"(error {count}/{MAX_SCHEDULE_ERRORS}): {err}"
        )


def _recompute_job_next_run(job: CronJob, now_ms: int) -> bool:
    """Recompute nextRunAtMs for a single job. Returns True if changed."""
    try:
        new_next = compute_job_next_run_at_ms(job, now_ms)
        if job.state.next_run_ms != new_next:
            job.state.next_run_ms = new_next
            if job.state.schedule_error_count:
                job.state.schedule_error_count = None
            return True
        if job.state.schedule_error_count:
            job.state.schedule_error_count = None
            return True
    except Exception as err:
        _record_schedule_error(job, err)
        return True
    return False


def _normalize_job_tick_state(job: CronJob, now_ms: int) -> tuple[bool, bool]:
    """Normalize job state. Returns (changed, skip)."""
    changed = False

    if not job.enabled:
        if job.state.next_run_ms is not None:
            job.state.next_run_ms = None
            changed = True
        if job.state.running_at_ms is not None:
            job.state.running_at_ms = None
            changed = True
        return changed, True

    # Clear stuck running_at_ms (> 2 h)
    if job.state.running_at_ms is not None and now_ms - job.state.running_at_ms > STUCK_RUN_MS:
        logger.warning(f"cron: clearing stuck running marker for job {job.id!r}")
        job.state.running_at_ms = None
        changed = True

    return changed, False


def _recompute_next_runs(jobs: list[CronJob], now_ms: int | None = None) -> bool:
    """Full recompute: recompute nextRunAtMs if missing or past-due."""
    now = now_ms or _now_ms()
    changed = False
    for job in jobs:
        tick_changed, skip = _normalize_job_tick_state(job, now)
        if tick_changed:
            changed = True
        if skip:
            continue
        nxt = job.state.next_run_ms
        if nxt is None or now >= nxt:
            if _recompute_job_next_run(job, now):
                changed = True
    return changed


def _recompute_next_runs_for_maintenance(jobs: list[CronJob], now_ms: int | None = None) -> bool:
    """Maintenance-only recompute: only fills missing nextRunAtMs, never advances existing.

    Used during timer ticks when no due jobs were found, to avoid silently
    advancing past-due nextRunAtMs values without execution.
    """
    now = now_ms or _now_ms()
    changed = False
    for job in jobs:
        tick_changed, skip = _normalize_job_tick_state(job, now)
        if tick_changed:
            changed = True
        if skip:
            continue
        if job.state.next_run_ms is None:
            if _recompute_job_next_run(job, now):
                changed = True
    return changed


def _next_wake_at_ms(jobs: list[CronJob]) -> int | None:
    """Find earliest nextRunAtMs across enabled jobs."""
    earliest: int | None = None
    for j in jobs:
        if not j.enabled:
            continue
        nxt = j.state.next_run_ms
        if nxt is not None and (earliest is None or nxt < earliest):
            earliest = nxt
    return earliest


def _apply_job_result(
    job: CronJob,
    status: Literal["ok", "error", "skipped"],
    error: str | None,
    started_at: int,
    ended_at: int,
) -> bool:
    """Apply execution result to job state. Returns True if job should be deleted."""
    job.state.running_at_ms = None
    job.state.last_run_at_ms = started_at
    job.state.last_status = status
    job.state.last_duration_ms = max(0, ended_at - started_at)
    job.state.last_error = error
    job.updated_at_ms = ended_at

    # Track consecutive errors
    if status == "error":
        job.state.consecutive_errors = (job.state.consecutive_errors or 0) + 1
    else:
        job.state.consecutive_errors = 0

    should_delete = (
        isinstance(job.schedule, AtSchedule)
        and job.delete_after_run is True
        and status == "ok"
    )

    if not should_delete:
        if isinstance(job.schedule, AtSchedule):
            # One-shot: disable after any terminal status
            job.enabled = False
            job.state.next_run_ms = None
            if status == "error":
                logger.warning(
                    f"cron: disabling one-shot job {job.id!r} after error — "
                    f"consecutiveErrors={job.state.consecutive_errors}"
                )
        elif status == "error" and job.enabled:
            # Exponential backoff
            backoff = _error_backoff_ms(job.state.consecutive_errors or 1)
            normal_next = compute_job_next_run_at_ms(job, ended_at)
            backoff_next = ended_at + backoff
            job.state.next_run_ms = (
                max(normal_next, backoff_next) if normal_next is not None else backoff_next
            )
            logger.info(
                f"cron: error backoff for job {job.id!r} — "
                f"consecutiveErrors={job.state.consecutive_errors}, "
                f"backoffMs={backoff}, nextRunAtMs={job.state.next_run_ms}"
            )
        elif job.enabled:
            natural_next = compute_job_next_run_at_ms(job, ended_at)
            if isinstance(job.schedule, CronScheduleType):
                # MIN_REFIRE_GAP_MS safety net
                min_next = ended_at + MIN_REFIRE_GAP_MS
                job.state.next_run_ms = (
                    max(natural_next, min_next) if natural_next is not None else min_next
                )
            else:
                job.state.next_run_ms = natural_next
        else:
            job.state.next_run_ms = None

    return should_delete


def _is_job_runnable(
    job: CronJob,
    now_ms: int,
    skip_ids: frozenset[str] | None = None,
    skip_at_if_already_ran: bool = False,
) -> bool:
    if not job.enabled:
        return False
    if skip_ids and job.id in skip_ids:
        return False
    if job.state.running_at_ms is not None:
        return False
    if skip_at_if_already_ran and isinstance(job.schedule, AtSchedule) and job.state.last_status:
        return False
    nxt = job.state.next_run_ms
    return isinstance(nxt, int) and now_ms >= nxt


# ---------------------------------------------------------------------------
# CronEvent
# ---------------------------------------------------------------------------

CronEventAction = Literal["added", "updated", "removed", "started", "finished"]


class CronEvent(dict):
    """Structured cron event."""
    pass


def _make_event(**kwargs: Any) -> CronEvent:
    return CronEvent({k: v for k, v in kwargs.items() if v is not None})


# ---------------------------------------------------------------------------
# CronService
# ---------------------------------------------------------------------------

class CronService:
    """
    Complete Cron scheduling service — aligned with TypeScript CronService.

    Matches: service/ops.ts + service/timer.ts + service/jobs.ts
    """

    def __init__(
        self,
        store_path: Optional[Path] = None,
        log_dir: Optional[Path] = None,
        cron_enabled: bool = True,
        # Callbacks matching TypeScript CronServiceDeps
        enqueue_system_event: Optional[Callable[..., Any]] = None,
        request_heartbeat_now: Optional[Callable[..., Any]] = None,
        run_heartbeat_once: Optional[Callable[..., Any]] = None,
        run_isolated_agent_job: Optional[Callable[..., Awaitable[Dict[str, Any]]]] = None,
        on_event: Optional[Callable[[CronEvent], None]] = None,
        resolve_session_store_path: Optional[Callable[[str], str]] = None,
        session_store_path: Optional[str] = None,
        cron_config: Optional[Dict[str, Any]] = None,
        default_agent_id: Optional[str] = None,
        lane_manager: Optional[Any] = None,  # QueueManager for lane-based execution
        # Legacy callback names (backward compat)
        on_system_event: Optional[Callable[..., Any]] = None,
        on_isolated_agent: Optional[Callable[..., Awaitable[Dict[str, Any]]]] = None,
    ):
        self.jobs: Dict[str, CronJob] = {}
        self._service_running = False
        self._cron_enabled = cron_enabled

        # Store
        self.store_path = store_path
        self.log_dir = log_dir
        self._store: Optional[CronStore] = None
        if store_path:
            self._store = CronStore(store_path)

        # Callbacks (TypeScript-aligned)
        self.enqueue_system_event = enqueue_system_event or on_system_event
        self.request_heartbeat_now = request_heartbeat_now
        self.run_heartbeat_once = run_heartbeat_once
        self.run_isolated_agent_job = run_isolated_agent_job or on_isolated_agent
        self.on_event = on_event
        self.resolve_session_store_path = resolve_session_store_path
        self.session_store_path = session_store_path
        self.cron_config = cron_config or {}
        self.default_agent_id = default_agent_id or "default"
        self.lane_manager = lane_manager

        # Store path for per-store-path locking (aligned with TS)
        self._store_path = str(store_path) if store_path else ""

        # Timer
        self._timer: Optional[CronTimer] = None

        # Running flag (matches TS state.running guard)
        self._timer_running = False

        # Warned-disabled once
        self._warned_disabled = False

        logger.info("CronService initialized")

    # ------------------------------------------------------------------
    # Lock helper (aligned with TS locked.ts)
    # ------------------------------------------------------------------

    async def _locked(self, fn: Callable[..., Awaitable[Any]], *args: Any) -> Any:
        """Execute function under per-store-path lock"""
        async def wrapper():
            return await fn(*args)
        return await locked(self._store_path, wrapper)

    # ------------------------------------------------------------------
    # Store helpers
    # ------------------------------------------------------------------

    async def _ensure_loaded(
        self,
        force_reload: bool = False,
        skip_recompute: bool = False,
    ) -> None:
        if self._store is None:
            return
        if self.jobs and not force_reload:
            return

        jobs = self._store.load()
        self.jobs = {j.id: j for j in jobs}

        if not skip_recompute:
            _recompute_next_runs(list(self.jobs.values()))

        logger.debug(f"Store loaded: {len(self.jobs)} jobs (force={force_reload})")

    async def _persist(self) -> None:
        if self._store is None:
            return
        self._store.save(list(self.jobs.values()))

    # ------------------------------------------------------------------
    # Emit helper
    # ------------------------------------------------------------------

    def _emit(self, **kwargs: Any) -> None:
        evt = _make_event(**kwargs)
        try:
            if self.on_event:
                self.on_event(evt)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Warn-if-disabled
    # ------------------------------------------------------------------

    def _warn_if_disabled(self, action: str) -> None:
        if self._cron_enabled:
            return
        if self._warned_disabled:
            return
        self._warned_disabled = True
        logger.warning(
            f"cron: scheduler disabled; jobs will not run automatically (action={action})"
        )

    # ------------------------------------------------------------------
    # Timer management
    # ------------------------------------------------------------------

    def _arm_timer(self) -> None:
        """Arm timer at next wake time (clamped to MAX_TIMER_DELAY_MS)."""
        if not self._timer or not self._cron_enabled:
            return
        nxt = _next_wake_at_ms(list(self.jobs.values()))
        self._timer.arm(nxt)

    # ------------------------------------------------------------------
    # Public operations
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start cron service."""
        async def _do_start() -> None:
            if not self._cron_enabled:
                logger.info("cron: disabled")
                return

            await self._ensure_loaded()

            # Clear stale running markers and run missed jobs
            now = _now_ms()
            for job in self.jobs.values():
                if job.state.running_at_ms is not None:
                    logger.warning(f"cron: clearing stale running marker for job {job.id!r}")
                    job.state.running_at_ms = None

            _recompute_next_runs(list(self.jobs.values()), now)
            await self._persist()

            # Create timer
            self._timer = CronTimer(on_timer_callback=self._on_timer)

            # Run overdue jobs (missed while process was down)
            await self._run_missed_jobs(now)

            self._arm_timer()
            self._service_running = True

            nxt = _next_wake_at_ms(list(self.jobs.values()))
            logger.info(f"cron: started (jobs={len(self.jobs)}, nextWakeAtMs={nxt})")

        await self._locked(_do_start)

    def stop(self) -> None:
        """Stop cron service."""
        if self._timer:
            self._timer.stop()
            self._timer = None
        self._service_running = False
        logger.info("cron: stopped")

    def shutdown(self) -> None:
        self.stop()

    async def status(self) -> Dict[str, Any]:
        async def _do() -> Dict[str, Any]:
            await self._ensure_loaded()
            nxt = _next_wake_at_ms(list(self.jobs.values())) if self._cron_enabled else None
            return {
                "enabled": self._cron_enabled,
                "storePath": str(self.store_path) if self.store_path else None,
                "jobs": len(self.jobs),
                "nextWakeAtMs": nxt,
            }
        return await self._locked(_do)

    async def list_jobs(self, include_disabled: bool = False) -> list[Dict[str, Any]]:
        async def _do() -> list[Dict[str, Any]]:
            await self._ensure_loaded()
            jobs = list(self.jobs.values())
            if not include_disabled:
                jobs = [j for j in jobs if j.enabled]
            jobs.sort(key=lambda j: j.state.next_run_ms or 0)
            return [self._job_to_dict(j) for j in jobs]
        return await self._locked(_do)

    async def add_job(self, job: CronJob) -> CronJob:
        async def _do() -> CronJob:
            self._warn_if_disabled("add")
            await self._ensure_loaded()

            now = _now_ms()
            if job.state.next_run_ms is None:
                job.state.next_run_ms = compute_job_next_run_at_ms(job, now)

            self.jobs[job.id] = job
            await self._persist()
            self._arm_timer()

            self._emit(jobId=job.id, action="added", nextRunAtMs=job.state.next_run_ms)
            logger.info(f"cron: added job {job.name!r} (id={job.id})")
            return job

        return await self._locked(_do)

    async def update_job(self, job_id: str, patch: Dict[str, Any]) -> CronJob:
        async def _do() -> CronJob:
            self._warn_if_disabled("update")
            await self._ensure_loaded()

            job = self.jobs.get(job_id)
            if not job:
                raise ValueError(f"cron: unknown job id: {job_id}")

            now = _now_ms()
            _apply_job_patch(job, patch)
            job.updated_at_ms = now

            if job.enabled:
                job.state.next_run_ms = compute_job_next_run_at_ms(job, now)
            else:
                job.state.next_run_ms = None
                job.state.running_at_ms = None

            await self._persist()
            self._arm_timer()
            self._emit(jobId=job_id, action="updated", nextRunAtMs=job.state.next_run_ms)
            logger.info(f"cron: updated job {job_id!r}")
            return job

        return await self._locked(_do)

    async def remove_job(self, job_id: str) -> Dict[str, Any]:
        async def _do() -> Dict[str, Any]:
            self._warn_if_disabled("remove")
            await self._ensure_loaded()

            removed = job_id in self.jobs
            if removed:
                del self.jobs[job_id]

            await self._persist()
            self._arm_timer()

            if removed:
                self._emit(jobId=job_id, action="removed")
                logger.info(f"cron: removed job {job_id!r}")

            return {"ok": True, "removed": removed}

        return await self._locked(_do)

    async def run(self, job_id: str, mode: Literal["due", "force"] = "force") -> Dict[str, Any]:
        async def _do() -> Dict[str, Any]:
            self._warn_if_disabled("run")
            await self._ensure_loaded()

            job = self.jobs.get(job_id)
            if not job:
                raise ValueError(f"cron: unknown job id: {job_id}")

            now = _now_ms()
            forced = mode == "force"

            if not forced and not _is_job_runnable(job, now):
                return {"ok": True, "ran": False, "reason": "not-due"}

            await self._execute_job(job, forced=forced)
            await self._persist()
            self._arm_timer()
            return {"ok": True, "ran": True}

        return await self._locked(_do)

    async def run_job_now(self, job_id: str) -> Dict[str, Any]:
        return await self.run(job_id, mode="force")

    def wake(
        self,
        text: str,
        mode: Literal["now", "next-heartbeat"] = "now",
    ) -> Dict[str, Any]:
        text = text.strip()
        if not text:
            return {"ok": False}

        if self.enqueue_system_event:
            try:
                result = self.enqueue_system_event(text)
                if asyncio.iscoroutine(result):
                    asyncio.ensure_future(result)
            except Exception as e:
                logger.error(f"cron: error in enqueue_system_event: {e}")

        if mode == "now" and self.request_heartbeat_now:
            try:
                self.request_heartbeat_now(reason="wake")
            except Exception as e:
                logger.error(f"cron: error in request_heartbeat_now: {e}")

        return {"ok": True}

    def get_job(self, job_id: str) -> Optional[CronJob]:
        return self.jobs.get(job_id)

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        job = self.jobs.get(job_id)
        return self._job_to_dict(job) if job else None

    # ------------------------------------------------------------------
    # Timer callback (matches TS onTimer)
    # ------------------------------------------------------------------

    async def _on_timer(self) -> None:
        """Timer callback — matches TS onTimer with running-guard + re-arm."""
        if self._timer_running:
            # Re-arm at MAX_TIMER_DELAY_MS to keep scheduler alive
            if self._timer:
                self._timer.arm_at_max_delay()
            return

        self._timer_running = True
        try:
            due_snapshots = await self._locked(self._pick_due_jobs)

            results: list[Dict[str, Any]] = []
            for snap in due_snapshots:
                job_id: str = snap["id"]
                job: CronJob = snap["job"]
                started_at = _now_ms()
                job.state.running_at_ms = started_at
                self._emit(jobId=job_id, action="started", runAtMs=started_at)

                # Per-job timeout
                timeout_ms = self._resolve_job_timeout_ms(job)

                try:
                    # Execute in CommandLane.CRON if lane_manager available (aligned with TS)
                    if self.lane_manager:
                        from openclaw.agents.queuing.lanes import CommandLane
                        
                        async def job_task():
                            return await self._execute_job_core(job)
                        
                        if timeout_ms is not None:
                            core_result = await asyncio.wait_for(
                                self.lane_manager.enqueue_in_lane(CommandLane.CRON, job_task),
                                timeout=timeout_ms / 1000,
                            )
                        else:
                            core_result = await self.lane_manager.enqueue_in_lane(
                                CommandLane.CRON, job_task
                            )
                    else:
                        # Fallback to direct execution (backward compat)
                        if timeout_ms is not None:
                            core_result = await asyncio.wait_for(
                                self._execute_job_core(job),
                                timeout=timeout_ms / 1000,
                            )
                        else:
                            core_result = await self._execute_job_core(job)
                    results.append({
                        "id": job_id,
                        "job": job,
                        "started_at": started_at,
                        "ended_at": _now_ms(),
                        **core_result,
                    })
                except asyncio.TimeoutError:
                    logger.warning(f"cron: job {job_id!r} timed out after {timeout_ms}ms")
                    results.append({
                        "id": job_id,
                        "job": job,
                        "started_at": started_at,
                        "ended_at": _now_ms(),
                        "status": "error",
                        "error": "cron: job execution timed out",
                    })
                except Exception as err:
                    logger.warning(f"cron: job {job_id!r} failed: {err}")
                    results.append({
                        "id": job_id,
                        "job": job,
                        "started_at": started_at,
                        "ended_at": _now_ms(),
                        "status": "error",
                        "error": str(err),
                    })

            if results:
                await self._locked(self._apply_results, results)

            # Session reaper (outside lock, self-throttled)
            await self._sweep_sessions()

        finally:
            self._timer_running = False
            self._arm_timer()

    async def _pick_due_jobs(self) -> list[Dict[str, Any]]:
        """Under lock: reload store, find due jobs, mark running, persist."""
        await self._ensure_loaded(force_reload=True, skip_recompute=True)
        now = _now_ms()
        due = [
            j for j in self.jobs.values()
            if _is_job_runnable(j, now)
        ]

        if not due:
            jobs_list = list(self.jobs.values())
            if _recompute_next_runs_for_maintenance(jobs_list, now):
                await self._persist()
            return []

        for job in due:
            job.state.running_at_ms = now
            job.state.last_error = None
        await self._persist()

        return [{"id": j.id, "job": j} for j in due]

    async def _apply_results(self, results: list[Dict[str, Any]]) -> None:
        """Under lock: apply execution results, recompute, persist."""
        await self._ensure_loaded(force_reload=True, skip_recompute=True)

        for r in results:
            job = self.jobs.get(r["id"])
            if not job:
                continue

            status: Literal["ok", "error", "skipped"] = r.get("status", "error")
            error: str | None = r.get("error")
            started_at: int = r["started_at"]
            ended_at: int = r["ended_at"]

            should_delete = _apply_job_result(job, status, error, started_at, ended_at)

            self._emit_job_finished(job, r, started_at)
            self._append_run_log(job, r)

            if should_delete and job.id in self.jobs:
                del self.jobs[job.id]
                self._emit(jobId=job.id, action="removed")

        # Maintenance-only recompute (don't advance past-due values)
        now = _now_ms()
        _recompute_next_runs_for_maintenance(list(self.jobs.values()), now)
        await self._persist()

    async def _run_missed_jobs(self, now_ms: int) -> None:
        """Run overdue jobs after startup (matches TS runMissedJobs)."""
        missed = [
            j for j in self.jobs.values()
            if _is_job_runnable(j, now_ms, skip_at_if_already_ran=True)
        ]

        if missed:
            logger.info(
                f"cron: running {len(missed)} missed jobs after restart: "
                f"{[j.id for j in missed]}"
            )
            for job in missed:
                await self._execute_job(job, forced=False)

    async def _sweep_sessions(self) -> None:
        """Call session reaper (self-throttled, outside lock)."""
        try:
            from .session_reaper import sweep_cron_run_sessions
        except ImportError:
            return

        try:
            store_paths: set[str] = set()
            if self.resolve_session_store_path:
                agent_id = self.default_agent_id
                if self.jobs:
                    for job in self.jobs.values():
                        aid = job.agent_id or agent_id
                        store_paths.add(self.resolve_session_store_path(aid))
                else:
                    store_paths.add(self.resolve_session_store_path(agent_id))
            elif self.session_store_path:
                store_paths.add(self.session_store_path)

            now = _now_ms()
            for sp in store_paths:
                try:
                    await sweep_cron_run_sessions(
                        cron_config=self.cron_config,
                        session_store_path=sp,
                        now_ms=now,
                    )
                except Exception as e:
                    logger.warning(f"cron: session reaper sweep failed for {sp!r}: {e}")
        except Exception as e:
            logger.debug(f"cron: session reaper error: {e}")

    # ------------------------------------------------------------------
    # Job execution
    # ------------------------------------------------------------------

    def _resolve_job_timeout_ms(self, job: CronJob) -> int | None:
        """Resolve per-job execution timeout."""
        if isinstance(job.payload, AgentTurnPayload):
            ts = job.payload.timeout_seconds
            if ts is not None:
                configured = int(ts * 1000)
                return None if configured <= 0 else configured
        return DEFAULT_JOB_TIMEOUT_MS

    async def _execute_job(self, job: CronJob, *, forced: bool = False) -> Dict[str, Any]:
        """Execute a single job with full state management (used by run command)."""
        started_at = _now_ms()
        job.state.running_at_ms = started_at
        job.state.last_error = None
        self._emit(jobId=job.id, action="started", runAtMs=started_at)

        try:
            core_result = await self._execute_job_core(job)
        except Exception as err:
            core_result = {"status": "error", "error": str(err)}

        ended_at = _now_ms()
        status: Literal["ok", "error", "skipped"] = core_result.get("status", "error")
        error: str | None = core_result.get("error")

        should_delete = _apply_job_result(job, status, error, started_at, ended_at)

        self._emit_job_finished(job, core_result, started_at)
        self._append_run_log(job, {**core_result, "started_at": started_at, "ended_at": ended_at})

        if should_delete and job.id in self.jobs:
            del self.jobs[job.id]
            self._emit(jobId=job.id, action="removed")

        return core_result

    async def _execute_job_core(self, job: CronJob) -> Dict[str, Any]:
        """Core execution — matches TS executeJobCore."""
        if job.session_target == "main":
            return await self._execute_main_session_job(job)
        else:
            return await self._execute_isolated_job(job)

    async def _execute_main_session_job(self, job: CronJob) -> Dict[str, Any]:
        """Execute main session job (systemEvent). Matches TS executeJobCore main branch."""
        text = _resolve_job_payload_text_for_main(job)
        if not text:
            kind = getattr(job.payload, "kind", "unknown")
            reason = (
                "main job requires non-empty systemEvent text"
                if kind == "systemEvent"
                else 'main job requires payload.kind="systemEvent"'
            )
            return {"status": "skipped", "error": reason}

        if self.enqueue_system_event:
            try:
                res = self.enqueue_system_event(
                    text,
                    agent_id=job.agent_id,
                    session_key=job.session_key,
                    context_key=f"cron:{job.id}",
                )
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                logger.error(f"cron: error enqueuing system event: {e}")

        if job.wake_mode == "now" and self.run_heartbeat_once:
            reason = f"cron:{job.id}"
            max_wait_ms = 2 * 60_000
            retry_delay_ms = 250
            wait_started = _now_ms()

            heartbeat_result: Dict[str, Any] = {"status": "error", "reason": "not-run"}
            while True:
                try:
                    heartbeat_result = await self.run_heartbeat_once(
                        reason=reason,
                        agent_id=job.agent_id,
                        session_key=job.session_key,
                    )
                except Exception as e:
                    heartbeat_result = {"status": "error", "reason": str(e)}
                    break

                hb_status = heartbeat_result.get("status")
                hb_reason = heartbeat_result.get("reason")
                if hb_status != "skipped" or hb_reason != "requests-in-flight":
                    break
                if _now_ms() - wait_started > max_wait_ms:
                    # Timeout: fall back to request
                    if self.request_heartbeat_now:
                        self.request_heartbeat_now(
                            reason=reason,
                            agent_id=job.agent_id,
                            session_key=job.session_key,
                        )
                    return {"status": "ok", "summary": text}
                await asyncio.sleep(retry_delay_ms / 1000)

            hb_status = heartbeat_result.get("status", "error")
            if hb_status == "ran":
                return {"status": "ok", "summary": text}
            elif hb_status == "skipped":
                return {"status": "skipped", "error": heartbeat_result.get("reason"), "summary": text}
            else:
                return {"status": "error", "error": heartbeat_result.get("reason"), "summary": text}
        else:
            if self.request_heartbeat_now:
                try:
                    self.request_heartbeat_now(
                        reason=f"cron:{job.id}",
                        agent_id=job.agent_id,
                        session_key=job.session_key,
                    )
                except Exception as e:
                    logger.error(f"cron: error requesting heartbeat: {e}")
            return {"status": "ok", "summary": text}

    async def _execute_isolated_job(self, job: CronJob) -> Dict[str, Any]:
        """Execute isolated agent job. Matches TS executeJobCore isolated branch."""
        if not isinstance(job.payload, AgentTurnPayload):
            return {"status": "skipped", "error": "isolated job requires payload.kind=agentTurn"}

        if not self.run_isolated_agent_job:
            return {"status": "error", "error": "isolated agent callback not configured"}

        # TS passes {job, message: job.payload.message}
        res = await self.run_isolated_agent_job(
            job=job,
            message=job.payload.message,
        )

        # Post summary to main session (only if delivery was NOT already done)
        summary_text = (res.get("summary") or "").strip()
        from .normalize import resolve_cron_delivery_plan
        delivery_plan = resolve_cron_delivery_plan(job)
        delivered = bool(res.get("delivered"))

        if summary_text and delivery_plan.get("requested") and not delivered:
            prefix = "Cron"
            if res.get("status") == "error":
                label = f"{prefix} (error): {summary_text}"
            else:
                label = f"{prefix}: {summary_text}"

            if self.enqueue_system_event:
                try:
                    r = self.enqueue_system_event(
                        label,
                        agent_id=job.agent_id,
                        session_key=job.session_key,
                        context_key=f"cron:{job.id}",
                    )
                    if asyncio.iscoroutine(r):
                        await r
                except Exception as e:
                    logger.error(f"cron: error posting summary to main: {e}")

            if job.wake_mode == "now" and self.request_heartbeat_now:
                try:
                    self.request_heartbeat_now(
                        reason=f"cron:{job.id}",
                        agent_id=job.agent_id,
                        session_key=job.session_key,
                    )
                except Exception as e:
                    logger.error(f"cron: error requesting heartbeat: {e}")

        return {
            "status": res.get("status", "ok"),
            "error": res.get("error"),
            "summary": res.get("summary"),
            "session_id": res.get("session_id") or res.get("sessionId"),
            "session_key": res.get("session_key") or res.get("sessionKey"),
            "model": res.get("model"),
            "provider": res.get("provider"),
            "usage": res.get("usage"),
        }

    # ------------------------------------------------------------------
    # Emit / log helpers
    # ------------------------------------------------------------------

    def _emit_job_finished(
        self,
        job: CronJob,
        result: Dict[str, Any],
        run_at_ms: int,
    ) -> None:
        self._emit(
            jobId=job.id,
            action="finished",
            status=result.get("status"),
            error=result.get("error"),
            summary=result.get("summary"),
            sessionId=result.get("session_id") or result.get("sessionId"),
            sessionKey=result.get("session_key") or result.get("sessionKey"),
            runAtMs=run_at_ms,
            durationMs=job.state.last_duration_ms,
            nextRunAtMs=job.state.next_run_ms,
            model=result.get("model"),
            provider=result.get("provider"),
            usage=result.get("usage"),
        )

    def _append_run_log(self, job: CronJob, result: Dict[str, Any]) -> None:
        if not self.log_dir:
            return
        try:
            run_log = CronRunLog(self.log_dir, job.id)
            run_log.append({
                "ts": _now_ms(),
                "jobId": job.id,
                "action": "finished",
                "status": result.get("status"),
                "error": result.get("error"),
                "summary": result.get("summary"),
                "runAtMs": job.state.last_run_at_ms,
                "durationMs": job.state.last_duration_ms,
                "nextRunAtMs": job.state.next_run_ms,
                "sessionId": result.get("session_id") or result.get("sessionId"),
                "sessionKey": result.get("session_key") or result.get("sessionKey"),
                "model": result.get("model"),
                "provider": result.get("provider"),
                "usage": result.get("usage"),
            })
        except Exception as e:
            logger.warning(f"cron: failed to write run log: {e}")

    def _job_to_dict(self, job: CronJob) -> Dict[str, Any]:
        from openclaw.cron.serialization import convert_job_to_api
        return convert_job_to_api(job.to_dict())


# ---------------------------------------------------------------------------
# Patch helper (matches TS applyJobPatch)
# ---------------------------------------------------------------------------

def _apply_job_patch(job: CronJob, patch: Dict[str, Any]) -> None:
    """Apply a patch to a CronJob."""
    if "name" in patch:
        job.name = str(patch["name"]).strip() or job.name
    if "description" in patch:
        job.description = patch.get("description")
    if "enabled" in patch:
        job.enabled = bool(patch["enabled"])
    if "delete_after_run" in patch or "deleteAfterRun" in patch:
        job.delete_after_run = bool(
            patch.get("delete_after_run", patch.get("deleteAfterRun", False))
        )
    if "session_target" in patch or "sessionTarget" in patch:
        val = patch.get("session_target", patch.get("sessionTarget"))
        if val in ("main", "isolated"):
            job.session_target = val
    if "wake_mode" in patch or "wakeMode" in patch:
        val = patch.get("wake_mode", patch.get("wakeMode"))
        if val in ("now", "next-heartbeat"):
            job.wake_mode = val
    if "agent_id" in patch or "agentId" in patch:
        job.agent_id = patch.get("agent_id", patch.get("agentId"))
    if "session_key" in patch or "sessionKey" in patch:
        job.session_key = patch.get("session_key", patch.get("sessionKey"))

    # Schedule patch
    if "schedule" in patch:
        sched = patch["schedule"]
        stype = sched.get("kind") or sched.get("type")
        if stype == "at":
            at_val = sched.get("at") or sched.get("timestamp") or ""
            job.schedule = AtSchedule(at=at_val, type="at")
        elif stype == "every":
            every_ms = sched.get("every_ms") or sched.get("everyMs") or sched.get("interval_ms") or 0
            anchor_ms = sched.get("anchor_ms") or sched.get("anchorMs")
            job.schedule = EverySchedule(every_ms=int(every_ms), type="every", anchor_ms=anchor_ms)
        elif stype == "cron":
            expr = sched.get("expr") or sched.get("expression") or ""
            tz = sched.get("tz") or sched.get("timezone") or "UTC"
            stagger_ms = sched.get("stagger_ms") or sched.get("staggerMs")
            job.schedule = CronScheduleType(
                expr=expr, type="cron", tz=tz,
                stagger_ms=int(stagger_ms) if stagger_ms is not None else None,
            )

    # Payload patch
    if "payload" in patch:
        p = patch["payload"]
        kind = p.get("kind")
        if kind == "systemEvent":
            job.payload = SystemEventPayload(text=p.get("text", ""))
        elif kind == "agentTurn":
            msg = p.get("message") or p.get("prompt") or ""
            existing = job.payload if isinstance(job.payload, AgentTurnPayload) else None
            job.payload = AgentTurnPayload(
                message=msg or (existing.message if existing else ""),
                kind="agentTurn",
                model=p.get("model", existing.model if existing else None),
                thinking=p.get("thinking", existing.thinking if existing else None),
                timeout_seconds=(
                    p.get("timeout_seconds")
                    or p.get("timeoutSeconds")
                    or (existing.timeout_seconds if existing else None)
                ),
                allow_unsafe_external_content=bool(
                    p.get("allow_unsafe_external_content")
                    or p.get("allowUnsafeExternalContent")
                    or (existing.allow_unsafe_external_content if existing else False)
                ),
            )

    # Delivery patch
    if "delivery" in patch:
        d = patch["delivery"]
        if d is None:
            job.delivery = None
        else:
            existing_d = job.delivery
            job.delivery = CronDelivery(
                mode=d.get("mode", existing_d.mode if existing_d else "announce"),
                channel=d.get("channel", existing_d.channel if existing_d else None),
                to=d.get("to") or d.get("target") or (existing_d.to if existing_d else None),
                best_effort=bool(
                    d.get("best_effort", d.get("bestEffort",
                        existing_d.best_effort if existing_d else False))
                ),
            )


def _is_job_due(job: CronJob, now_ms: int, *, forced: bool = False) -> bool:
    if forced:
        return True
    return _is_job_runnable(job, now_ms)


def _resolve_job_payload_text_for_main(job: CronJob) -> str | None:
    if isinstance(job.payload, SystemEventPayload):
        text = (job.payload.text or "").strip()
        return text if text else None
    return None


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_cron_service: Optional[CronService] = None


def get_cron_service() -> Optional[CronService]:
    return _cron_service


def set_cron_service(service: CronService) -> None:
    global _cron_service
    _cron_service = service
