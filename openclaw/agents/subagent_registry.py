"""Subagent registry system

Tracks and manages sub-agent runs across Gateway restarts.
Matches TypeScript openclaw/src/agents/subagent-registry.ts
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from .subagent_registry_store import (
    load_subagent_registry_from_disk,
    save_subagent_registry_to_disk,
)

logger = logging.getLogger(__name__)

# Mirrors TS LIFECYCLE_ERROR_RETRY_GRACE_MS
LIFECYCLE_ERROR_RETRY_GRACE_MS = 15_000
# Announce retry constants — aligned with TS subagent-registry.ts
MIN_ANNOUNCE_RETRY_DELAY_MS = 1_000
MAX_ANNOUNCE_RETRY_DELAY_MS = 8_000
MAX_ANNOUNCE_RETRY_COUNT = 3
ANNOUNCE_EXPIRY_MS = 5 * 60_000  # 5 min

SUBAGENT_ENDED_REASON_COMPLETE = "complete"
SUBAGENT_ENDED_REASON_ERROR = "error"
SUBAGENT_ENDED_REASON_TIMEOUT = "timeout"
SUBAGENT_ENDED_REASON_KILLED = "killed"


@dataclass
class SubagentRunRecord:
    """Record of a subagent run (mirrors TS SubagentRunRecord from subagent-registry.ts)"""
    
    run_id: str
    child_session_key: str
    requester_session_key: str
    requester_origin: dict[str, Any] | None
    requester_display_key: str
    task: str
    cleanup: str  # "delete" or "keep"
    label: str | None = None
    model: str | None = None  # NEW: Model used for subagent
    run_timeout_seconds: int | None = None  # NEW: Run timeout
    created_at: int = 0  # timestamp ms
    started_at: int | None = None
    ended_at: int | None = None
    outcome: dict[str, Any] | None = None
    archive_at_ms: int | None = None
    cleanup_completed_at: int | None = None
    cleanup_handled: bool = False
    suppress_announce_reason: str | None = None  # "steer-restart" or "killed"
    expects_completion_message: bool = False  # Whether to announce on completion
    announce_retry_count: int = 0  # Number of announce retry attempts
    last_announce_retry_at: int | None = None  # Timestamp of last retry
    ended_reason: str | None = None  # TS: endedReason typed field
    spawn_mode: str = "run"  # TS: spawnMode on run record ("run" | "session")
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for serialization"""
        return asdict(self)


class SubagentRegistry:
    """
    Subagent run registry
    
    Tracks all sub-agent runs and manages their lifecycle:
    - Registration when spawned
    - Waiting for completion
    - Cleanup (delete or keep session)
    - Persistence across Gateway restarts
    """
    
    def __init__(self, config: dict[str, Any] | None = None, hook_runner: Any | None = None):
        self._runs: dict[str, SubagentRunRecord] = {}
        self._resumed_runs: set[str] = set()
        self._restore_attempted = False
        self._event_listeners: dict[str, list[asyncio.Event]] = {}
        self._lock = asyncio.Lock()
        self._config = config or {}
        self._lifecycle_listener_installed = False
        # Pending lifecycle errors with grace period (mirrors TS schedulePendingLifecycleError)
        self._pending_lifecycle_errors: dict[str, asyncio.TimerHandle | asyncio.Task] = {}
        # Optional hook runner for subagent lifecycle hooks
        self._hook_runner: Any | None = hook_runner

    def set_hook_runner(self, hook_runner: Any) -> None:
        """Wire in a PluginHookRunner to fire subagent lifecycle hooks."""
        self._hook_runner = hook_runner
    
    def _resolve_archive_after_ms(self) -> int | None:
        """
        Resolve archiveAfterMinutes config to milliseconds
        
        Aligned with TS: subagent-registry.ts resolveArchiveAfterMs()
        
        Returns:
            Archive delay in milliseconds, or None if disabled
        """
        minutes = (
            self._config.get("agents", {})
            .get("defaults", {})
            .get("subagents", {})
            .get("archiveAfterMinutes", 60)
        )
        
        if not isinstance(minutes, (int, float)) or minutes <= 0:
            return None
        
        return max(1, int(minutes)) * 60_000
    
    def register_subagent_run(
        self,
        child_session_key: str,
        requester_session_key: str,
        task: str,
        requester_origin: dict[str, Any] | None = None,
        requester_display_key: str | None = None,
        cleanup: str = "delete",
        label: str | None = None,
        model: str | None = None,
        run_timeout_seconds: int | None = None,
        expects_completion_message: bool = False,
        spawn_mode: str = "run",
    ) -> SubagentRunRecord:
        """
        Register a new subagent run.

        Args:
            child_session_key: Session key of child agent
            requester_session_key: Session key of requester
            task: Task description
            requester_origin: Origin context
            requester_display_key: Display key for requester
            cleanup: "delete" or "keep" session after completion
            label: Optional label
            spawn_mode: Spawn mode ("run" | "session")

        Returns:
            Created SubagentRunRecord
        """
        run_id = str(uuid.uuid4())
        now_ms = int(time.time() * 1000)

        # Calculate archive time (aligned with TS); session mode runs never archive
        archive_after_ms = self._resolve_archive_after_ms()
        spawn_mode = "session" if spawn_mode == "session" else "run"
        archive_at_ms = (
            None
            if spawn_mode == "session"
            else (now_ms + archive_after_ms) if archive_after_ms else None
        )

        record = SubagentRunRecord(
            run_id=run_id,
            child_session_key=child_session_key,
            requester_session_key=requester_session_key,
            requester_origin=requester_origin,
            requester_display_key=requester_display_key or requester_session_key,
            task=task,
            cleanup=cleanup,
            label=label,
            model=model,
            run_timeout_seconds=run_timeout_seconds,
            expects_completion_message=expects_completion_message,
            spawn_mode=spawn_mode,
            created_at=now_ms,
            started_at=now_ms,
            archive_at_ms=archive_at_ms,
        )
        
        self._runs[run_id] = record
        self._persist()
        
        logger.info(f"Registered subagent run: {run_id} (session: {child_session_key})")
        
        return record
    
    # ------------------------------------------------------------------
    # Lifecycle event listener — mirrors TS ensureLifecycleListener/onAgentEvent
    # ------------------------------------------------------------------

    def ensure_lifecycle_listener(self, gateway: Any) -> None:
        """Install a lifecycle event listener on the gateway.

        When the gateway emits ``agent`` lifecycle events (start, error, end),
        this handler updates the corresponding SubagentRunRecord.  A 15-second
        grace period is used for transient errors before treating them as
        terminal, matching the TS ``LIFECYCLE_ERROR_RETRY_GRACE_MS``.
        """
        if self._lifecycle_listener_installed:
            return
        self._lifecycle_listener_installed = True

        async def _on_lifecycle(event_data: dict[str, Any]) -> None:
            run_id = event_data.get("runId")
            phase = event_data.get("phase")
            if not run_id or not phase:
                return
            entry = self._runs.get(run_id)
            if not entry:
                return

            # Forward to global pub-sub (mirrors TS onAgentEvent emission in subagent-lifecycle-events.ts)
            try:
                from openclaw.infra.agent_events import emit_agent_event
                emit_agent_event({"type": "agent_lifecycle", "phase": phase, "runId": run_id, **event_data})
            except Exception:
                pass

            if phase == "start":
                # Clear any pending lifecycle error since the run actually started
                pending = self._pending_lifecycle_errors.pop(run_id, None)
                if pending and hasattr(pending, "cancel"):
                    pending.cancel()
                entry.started_at = int(time.time() * 1000)
                self._persist()

            elif phase == "error":
                reason = event_data.get("reason", "unknown")
                # Schedule a pending lifecycle error with grace period
                pending = self._pending_lifecycle_errors.pop(run_id, None)
                if pending and hasattr(pending, "cancel"):
                    pending.cancel()

                async def _fire_lifecycle_error() -> None:
                    await asyncio.sleep(LIFECYCLE_ERROR_RETRY_GRACE_MS / 1000.0)
                    self._pending_lifecycle_errors.pop(run_id, None)
                    # Re-check: if run ended normally in the meantime, skip
                    re_entry = self._runs.get(run_id)
                    if re_entry and re_entry.ended_at is None:
                        self.mark_subagent_ended(run_id, outcome={"status": "error", "error": reason})
                        logger.warning(
                            "Subagent %s ended via lifecycle error (after %dms grace): %s",
                            run_id, LIFECYCLE_ERROR_RETRY_GRACE_MS, reason,
                        )

                self._pending_lifecycle_errors[run_id] = asyncio.create_task(_fire_lifecycle_error())

            elif phase == "end":
                # Clear pending error and mark completed
                pending = self._pending_lifecycle_errors.pop(run_id, None)
                if pending and hasattr(pending, "cancel"):
                    pending.cancel()
                if entry.ended_at is None:
                    self.mark_subagent_ended(run_id, outcome={"status": "completed"})

        # Register listener on gateway
        if hasattr(gateway, "add_lifecycle_listener"):
            gateway.add_lifecycle_listener(_on_lifecycle)
        elif hasattr(gateway, "on"):
            gateway.on("agent_lifecycle", _on_lifecycle)
        else:
            logger.debug("Gateway does not support lifecycle listener registration")

    async def wait_for_subagent_completion(
        self,
        run_id: str,
        timeout_ms: int = 300000,  # 5 minutes
    ) -> dict[str, Any]:
        """
        Wait for subagent to complete
        
        Args:
            run_id: Run ID to wait for
            timeout_ms: Timeout in milliseconds
            
        Returns:
            Dict with completion info (success, outcome, etc.)
        """
        entry = self._runs.get(run_id)
        if not entry:
            return {"success": False, "error": "Run not found"}
        
        # If already ended, return immediately
        if entry.ended_at is not None:
            return {
                "success": True,
                "ended_at": entry.ended_at,
                "outcome": entry.outcome,
            }
        
        # Create event for this run
        event = asyncio.Event()
        if run_id not in self._event_listeners:
            self._event_listeners[run_id] = []
        self._event_listeners[run_id].append(event)
        
        try:
            # Wait with timeout
            await asyncio.wait_for(
                event.wait(),
                timeout=timeout_ms / 1000.0
            )
            
            # Get updated entry
            entry = self._runs.get(run_id)
            if entry:
                return {
                    "success": True,
                    "ended_at": entry.ended_at,
                    "outcome": entry.outcome,
                }
            
            return {"success": False, "error": "Run disappeared"}
            
        except asyncio.TimeoutError:
            logger.warning(f"Subagent run {run_id} timed out after {timeout_ms}ms")
            
            # Mark as timed out
            if entry:
                entry.ended_at = int(time.time() * 1000)
                entry.outcome = {"status": "timeout"}
                self._persist()
            
            return {
                "success": False,
                "error": "timeout",
                "timeout_ms": timeout_ms,
            }
    
    def mark_subagent_started(self, run_id: str):
        """Mark subagent as started"""
        entry = self._runs.get(run_id)
        if entry:
            entry.started_at = int(time.time() * 1000)
            self._persist()
    
    def mark_subagent_ended(
        self,
        run_id: str,
        outcome: dict[str, Any] | None = None,
        ended_reason: str | None = None,
    ):
        """
        Mark subagent as ended.

        Args:
            run_id: Run ID
            outcome: Outcome information
            ended_reason: Typed ended reason (complete/error/timeout/killed)
        """
        entry = self._runs.get(run_id)
        if not entry:
            return

        now_ms = int(time.time() * 1000)
        entry.ended_at = now_ms
        entry.outcome = outcome
        if ended_reason:
            entry.ended_reason = ended_reason
        elif outcome:
            # Infer from outcome dict
            status = outcome.get("status")
            if status == "ok":
                entry.ended_reason = SUBAGENT_ENDED_REASON_COMPLETE
            elif status == "error":
                entry.ended_reason = SUBAGENT_ENDED_REASON_ERROR
            elif status == "timeout":
                entry.ended_reason = SUBAGENT_ENDED_REASON_TIMEOUT
        self._persist()

        # Notify waiters
        if run_id in self._event_listeners:
            for event in self._event_listeners[run_id]:
                event.set()
            del self._event_listeners[run_id]

        logger.info("Subagent run %s ended (reason=%s)", run_id, entry.ended_reason)

        # Fire subagent_ended hook (void, parallel) — mirrors TS subagent_ended hook
        if self._hook_runner is not None and self._hook_runner.has_hooks("subagent_ended"):
            _hook_runner = self._hook_runner
            _entry = entry
            _outcome = outcome

            async def _fire_subagent_ended() -> None:
                try:
                    success = (_outcome or {}).get("status") not in ("error", "timeout")
                    error_msg = (_outcome or {}).get("error") if not success else None
                    duration_ms = (
                        (_entry.ended_at - _entry.started_at)
                        if _entry.ended_at and _entry.started_at
                        else None
                    )
                    await _hook_runner.run_subagent_ended(
                        {
                            "session_key": _entry.child_session_key,
                            "agent_id": None,
                            "label": _entry.label,
                            "success": bool(success),
                            "error": error_msg,
                            "duration_ms": duration_ms,
                        },
                        {
                            "session_key": _entry.child_session_key,
                            "parent_session_key": _entry.requester_session_key,
                        },
                    )
                except Exception as hook_exc:
                    logger.warning("subagent_ended hook error: %s", hook_exc)

            try:
                asyncio.get_running_loop().create_task(_fire_subagent_ended())
            except RuntimeError:
                # No running event loop — skip hook (happens in sync test contexts)
                pass
    
    def mark_cleanup_completed(self, run_id: str):
        """Mark cleanup as completed and retry any deferred sibling announces."""
        entry = self._runs.get(run_id)
        if entry:
            entry.cleanup_completed_at = int(time.time() * 1000)
            entry.cleanup_handled = True
            self._persist()
            # Unblock deferred sibling announces (mirrors TS retryDeferredCompletedAnnounces)
            self._retry_deferred_completed_announces(exclude_run_id=run_id)
    
    async def _trigger_announce_and_cleanup(self, entry: SubagentRunRecord):
        """
        Trigger announce flow and cleanup for completed run
        
        Used for restoring runs that ended during gateway restart.
        
        Args:
            entry: SubagentRunRecord that has ended
        """
        try:
            logger.info(f"Triggering announce and cleanup for run {entry.run_id}")
            
            # Import here to avoid circular dependency
            from .subagent_announce import run_subagent_announce_flow
            
            # Trigger announce flow
            await run_subagent_announce_flow(entry)
            
            # Cleanup session if requested
            if entry.cleanup == "delete":
                await self._cleanup_session(entry.child_session_key)
            
            # Mark cleanup completed
            self.mark_cleanup_completed(entry.run_id)
            
        except Exception as e:
            logger.error(f"Failed to trigger announce/cleanup for run {entry.run_id}: {e}")
    
    async def _resume_wait_for_completion(self, entry: SubagentRunRecord):
        """
        Resume waiting for subagent completion after gateway restart
        
        Args:
            entry: SubagentRunRecord that hasn't ended yet
        """
        try:
            logger.info(f"Resuming wait for run {entry.run_id}")
            
            # Calculate remaining timeout
            timeout_ms = None
            if entry.run_timeout_seconds:
                elapsed_ms = int(time.time() * 1000) - entry.created_at
                remaining_ms = (entry.run_timeout_seconds * 1000) - elapsed_ms
                if remaining_ms > 0:
                    timeout_ms = remaining_ms
                else:
                    logger.warning(f"Run {entry.run_id} already timed out")
                    self.mark_subagent_ended(
                        entry.run_id,
                        outcome={"status": "error", "error": "timeout"}
                    )
                    return
            
            # Wait for completion
            result = await self.wait_for_subagent_completion(
                entry.run_id,
                timeout_ms=timeout_ms if timeout_ms else 300000  # 5min default
            )
            
            if not result.get("success"):
                logger.warning(f"Wait failed for run {entry.run_id}: {result.get('error')}")
            
        except Exception as e:
            logger.error(f"Failed to resume wait for run {entry.run_id}: {e}")
    
    async def _cleanup_session(self, session_key: str):
        """
        Cleanup (delete) a subagent session
        
        Args:
            session_key: Session key to delete
        """
        try:
            # Import here to avoid circular dependency
            from ..gateway.rpc_client import get_gateway_rpc_client
            
            rpc = get_gateway_rpc_client()
            if rpc:
                await rpc.call("sessions.delete", {"sessionKey": session_key})
                logger.info(f"Deleted session {session_key}")
            else:
                logger.warning(f"No RPC client to delete session {session_key}")
        except Exception as e:
            logger.error(f"Failed to cleanup session {session_key}: {e}")
    
    def _persist(self):
        """Persist registry to disk"""
        try:
            save_subagent_registry_to_disk(self._runs)
        except Exception as e:
            logger.error(f"Failed to persist subagent registry: {e}")
    
    def _reconcile_orphaned_run(
        self,
        run_id: str,
        entry: SubagentRunRecord,
        reason: str,
        source: str = "restore",
    ) -> bool:
        """Mark a run as orphaned and remove it from the registry.

        Mirrors TS reconcileOrphanedRun().
        """
        now_ms = int(time.time() * 1000)
        changed = False
        if entry.ended_at is None:
            entry.ended_at = now_ms
            changed = True
        orphan_outcome: dict[str, Any] = {
            "status": "error",
            "error": f"orphaned subagent run ({reason})",
        }
        if entry.outcome != orphan_outcome:
            entry.outcome = orphan_outcome
            changed = True
        if entry.ended_reason != SUBAGENT_ENDED_REASON_ERROR:
            entry.ended_reason = SUBAGENT_ENDED_REASON_ERROR
            changed = True
        if not entry.cleanup_handled:
            entry.cleanup_handled = True
            changed = True
        if entry.cleanup_completed_at is None:
            entry.cleanup_completed_at = now_ms
            changed = True
        removed = self._runs.pop(run_id, None) is not None
        self._resumed_runs.discard(run_id)
        if removed or changed:
            logger.warning(
                "Subagent orphan run pruned source=%s run=%s child=%s reason=%s",
                source,
                run_id,
                entry.child_session_key,
                reason,
            )
            return True
        return False

    def _reconcile_orphaned_restored_runs(self) -> bool:
        """Reconcile all restored runs that no longer have a matching session.

        Mirrors TS reconcileOrphanedRestoredRuns(). Only runs that already
        ended (ended_at set) and have no live session are pruned — active
        runs are left untouched so normal lifecycle handling can proceed.
        """
        changed = False
        for run_id, entry in list(self._runs.items()):
            # Only prune runs that ended; active runs are handled by resume
            if entry.ended_at is None:
                continue
            if entry.cleanup_completed_at is not None:
                continue
            child_key = (entry.child_session_key or "").strip()
            if not child_key:
                if self._reconcile_orphaned_run(run_id, entry, "missing-session-entry", "restore"):
                    changed = True
        return changed

    def restore_once(self):
        """Restore registry from disk (once)"""
        if self._restore_attempted:
            return

        self._restore_attempted = True

        try:
            restored = load_subagent_registry_from_disk()
            if restored:
                self._runs = restored
                logger.info("Restored %d subagent runs from disk", len(restored))

                # Reconcile orphaned runs before resuming
                self._reconcile_orphaned_restored_runs()

                # Resume incomplete runs
                self._resume_incomplete_runs()
        except Exception as e:
            logger.error("Failed to restore subagent registry: %s", e)
    
    def _resume_incomplete_runs(self):
        """Resume incomplete runs after restart"""
        now_ms = int(time.time() * 1000)
        
        for run_id, entry in self._runs.items():
            if run_id in self._resumed_runs:
                continue
            
            # Skip if cleanup already done
            if entry.cleanup_completed_at:
                continue
            
            # If ended but not cleaned up, schedule cleanup
            if entry.ended_at:
                logger.info(f"Resuming cleanup for run {run_id}")
                self._resumed_runs.add(run_id)
                # Schedule announce and cleanup in background
                asyncio.create_task(self._trigger_announce_and_cleanup(entry))
                continue
            
            # If not ended, wait for completion again
            logger.info(f"Resuming wait for run {run_id}")
            self._resumed_runs.add(run_id)
            # Resume waiting in background
            asyncio.create_task(self._resume_wait_for_completion(entry))
    
    def list_runs(self, active_only: bool = False) -> list[SubagentRunRecord]:
        """
        List all runs
        
        Args:
            active_only: If True, only return runs that haven't ended
            
        Returns:
            List of SubagentRunRecord
        """
        if active_only:
            return [r for r in self._runs.values() if r.ended_at is None]
        return list(self._runs.values())
    
    def get_run(self, run_id: str) -> SubagentRunRecord | None:
        """Get run by ID"""
        return self._runs.get(run_id)
    
    def count_active_runs_for_session(self, session_key: str) -> int:
        """
        Count active runs for a requester session.
        
        Mirrors TS countActiveRunsForSession from subagent-registry.ts
        
        Args:
            session_key: Requester session key
        
        Returns:
            Number of active (not ended) runs
        """
        count = 0
        for run in self._runs.values():
            if run.requester_session_key == session_key and run.ended_at is None:
                count += 1
        return count
    
    def mark_subagent_run_terminated(
        self,
        run_id: str,
        reason: str = "killed",
    ):
        """
        Mark a subagent run as terminated.
        
        Args:
            run_id: Run ID
            reason: Termination reason ("killed" or other)
        """
        entry = self._runs.get(run_id)
        if entry:
            entry.ended_at = int(time.time() * 1000)
            entry.outcome = {"status": "terminated", "reason": reason}
            entry.suppress_announce_reason = reason
            self._persist()
            
            # Notify waiters
            if run_id in self._event_listeners:
                for event in self._event_listeners[run_id]:
                    event.set()
                del self._event_listeners[run_id]
    
    def mark_subagent_run_for_steer_restart(self, run_id: str):
        """
        Mark a subagent run for steer restart.
        
        This suppresses the announce flow.
        
        Args:
            run_id: Run ID
        """
        entry = self._runs.get(run_id)
        if entry:
            entry.suppress_announce_reason = "steer-restart"
            self._persist()
    
    def replace_subagent_run_after_steer(
        self,
        old_run_id: str,
        new_run_id: str,
        new_child_session_key: str,
    ):
        """
        Replace a subagent run after steer (restart with new message).
        
        Args:
            old_run_id: Old run ID (being replaced)
            new_run_id: New run ID
            new_child_session_key: New child session key
        """
        old_entry = self._runs.get(old_run_id)
        if not old_entry:
            return
        
        # Create new entry based on old one
        now_ms = int(time.time() * 1000)
        new_entry = SubagentRunRecord(
            run_id=new_run_id,
            child_session_key=new_child_session_key,
            requester_session_key=old_entry.requester_session_key,
            requester_origin=old_entry.requester_origin,
            requester_display_key=old_entry.requester_display_key,
            task=old_entry.task,
            cleanup=old_entry.cleanup,
            label=old_entry.label,
            model=old_entry.model,
            run_timeout_seconds=old_entry.run_timeout_seconds,
            expects_completion_message=old_entry.expects_completion_message,
            created_at=now_ms,
        )
        
        self._runs[new_run_id] = new_entry
        
        # Mark old entry as replaced
        old_entry.ended_at = now_ms
        old_entry.outcome = {"status": "replaced", "reason": "steer"}
        old_entry.cleanup_completed_at = now_ms
        old_entry.cleanup_handled = True
        
        self._persist()
    
    def list_runs_for_requester(
        self,
        requester_session_key: str,
        active_only: bool = False,
    ) -> list[SubagentRunRecord]:
        """
        List runs for a specific requester.
        
        Args:
            requester_session_key: Requester session key
            active_only: If True, only return active runs
        
        Returns:
            List of SubagentRunRecord
        """
        runs = [
            r
            for r in self._runs.values()
            if r.requester_session_key == requester_session_key
        ]
        
        if active_only:
            runs = [r for r in runs if r.ended_at is None]
        
        return runs

    # ------------------------------------------------------------------
    # Periodic sweeper — mirrors TS sweepSubagentRuns()
    # ------------------------------------------------------------------

    async def _sweep_loop(self) -> None:
        """Background task that periodically GC's timed-out registry entries.

        Mirrors TS ``sweepSubagentRuns`` — called on a 60s interval.
        Removes entries whose ``archive_at_ms`` has passed so that the
        in-memory dict doesn't grow unbounded.
        """
        SWEEP_INTERVAL_S = 60.0
        while True:
            await asyncio.sleep(SWEEP_INTERVAL_S)
            try:
                self._sweep_once()
            except Exception as exc:
                logger.warning("Subagent registry sweeper error: %s", exc)

    def _sweep_once(self) -> None:
        """Run one sweep pass — remove archived/expired entries."""
        now_ms = int(time.time() * 1000)
        to_delete: list[str] = []
        for run_id, entry in self._runs.items():
            if entry.archive_at_ms and now_ms >= entry.archive_at_ms:
                to_delete.append(run_id)
        for run_id in to_delete:
            self._runs.pop(run_id, None)
            logger.debug("Sweeper: archived subagent run %s", run_id)
        if to_delete:
            self._persist()

    def start_sweeper(self) -> asyncio.Task:
        """Start the periodic sweeper as an asyncio background task.

        Call this once after the event loop is running (e.g. from bootstrap).
        """
        task = asyncio.create_task(self._sweep_loop(), name="subagent-registry-sweeper")
        logger.debug("Subagent registry sweeper started")
        return task

    # ------------------------------------------------------------------
    # Recursive descendant tracking (BFS) — mirrors TS registry-queries
    # ------------------------------------------------------------------

    def _for_each_descendant_run(
        self,
        root_session_key: str,
        visitor: Any,
    ) -> bool:
        """BFS over all descendant runs starting from root_session_key."""
        root = root_session_key.strip()
        if not root:
            return False
        pending = [root]
        visited: set[str] = {root}
        idx = 0
        while idx < len(pending):
            requester = pending[idx]
            idx += 1
            for run_id, entry in self._runs.items():
                if entry.requester_session_key != requester:
                    continue
                visitor(run_id, entry)
                child_key = entry.child_session_key.strip()
                if child_key and child_key not in visited:
                    visited.add(child_key)
                    pending.append(child_key)
        return True

    def count_active_descendant_runs(self, root_session_key: str) -> int:
        """Count active (not ended) descendant runs recursively via BFS.

        Mirrors TS countActiveDescendantRunsFromRuns().
        """
        count = 0

        def _visit(_run_id: str, entry: SubagentRunRecord) -> None:
            nonlocal count
            if entry.ended_at is None:
                count += 1

        if not self._for_each_descendant_run(root_session_key, _visit):
            return 0
        return count

    def list_descendant_runs(self, root_session_key: str) -> list[SubagentRunRecord]:
        """List all descendant runs recursively via BFS.

        Mirrors TS listDescendantRunsForRequesterFromRuns().
        """
        descendants: list[SubagentRunRecord] = []

        def _visit(_run_id: str, entry: SubagentRunRecord) -> None:
            descendants.append(entry)

        if not self._for_each_descendant_run(root_session_key, _visit):
            return []
        return descendants

    # ------------------------------------------------------------------
    # clearSubagentRunSteerRestart — mirrors TS clearSubagentRunSteerRestart()
    # ------------------------------------------------------------------

    def clear_subagent_run_steer_restart(self, run_id: str) -> bool:
        """Clear the steer-restart suppression flag on a run.

        If the run already ended while suppressed, resumes cleanup so
        completion output is not lost.
        Mirrors TS clearSubagentRunSteerRestart().
        """
        key = run_id.strip()
        if not key:
            return False
        entry = self._runs.get(key)
        if not entry:
            return False
        if entry.suppress_announce_reason != "steer-restart":
            return True
        entry.suppress_announce_reason = None
        self._persist()
        # Resume if run already ended while suppression was active
        self._resumed_runs.discard(key)
        if entry.ended_at is not None and not entry.cleanup_completed_at:
            asyncio.create_task(self._trigger_announce_and_cleanup(entry))
        return True

    # ------------------------------------------------------------------
    # retryDeferredCompletedAnnounces — mirrors TS retryDeferredCompletedAnnounces()
    # ------------------------------------------------------------------

    _ANNOUNCE_EXPIRY_MS: int = 30 * 60 * 1000  # 30 minutes

    def _retry_deferred_completed_announces(self, exclude_run_id: str | None = None) -> None:
        """Retry announces for runs that ended but haven't been cleaned up yet.

        Called after cleanup completes for a run, to unblock any deferred
        sibling announces.  Mirrors TS retryDeferredCompletedAnnounces().
        """
        now_ms = int(time.time() * 1000)
        for run_id, entry in list(self._runs.items()):
            if exclude_run_id and run_id == exclude_run_id:
                continue
            if entry.ended_at is None:
                continue
            if entry.cleanup_completed_at or entry.cleanup_handled:
                continue
            if entry.suppress_announce_reason == "steer-restart":
                continue
            # Expire stale non-completion announces
            ended_ago = now_ms - (entry.ended_at or now_ms)
            if not entry.expects_completion_message and ended_ago > self._ANNOUNCE_EXPIRY_MS:
                logger.debug("Subagent announce expiry give-up: run=%s", run_id)
                entry.cleanup_completed_at = now_ms
                self._persist()
                continue
            self._resumed_runs.discard(run_id)
            asyncio.create_task(self._trigger_announce_and_cleanup(entry))

    # ------------------------------------------------------------------
    # releaseSubagentRun — mirrors TS releaseSubagentRun()
    # ------------------------------------------------------------------

    def release_subagent_run(self, run_id: str) -> None:
        """Remove a run from the registry and persist.

        Mirrors TS releaseSubagentRun().
        """
        if self._runs.pop(run_id, None) is not None:
            self._persist()
            logger.debug("Released subagent run %s", run_id)


# Global registry instance
_registry: SubagentRegistry | None = None


def get_global_registry() -> SubagentRegistry:
    """Get global subagent registry instance (mirrors TS pattern)"""
    global _registry
    if _registry is None:
        _registry = SubagentRegistry()
    return _registry


def get_subagent_registry() -> SubagentRegistry:
    """Get global subagent registry instance (alias for compatibility)"""
    return get_global_registry()


def init_subagent_registry() -> SubagentRegistry:
    """Initialize, restore, and start the sweeper for the global subagent registry."""
    registry = get_global_registry()
    registry.restore_once()
    try:
        registry.start_sweeper()
    except RuntimeError:
        # No running event loop — sweeper will be started later by bootstrap
        pass
    return registry
