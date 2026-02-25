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
    suppress_announce_reason: str | None = None  # NEW: "steer-restart" or "killed"
    expects_completion_message: bool = False  # NEW: Whether to announce on completion
    announce_retry_count: int = 0  # NEW: Number of announce retry attempts
    last_announce_retry_at: int | None = None  # NEW: Timestamp of last retry
    
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
    
    def __init__(self):
        self._runs: dict[str, SubagentRunRecord] = {}
        self._resumed_runs: set[str] = set()
        self._restore_attempted = False
        self._event_listeners: dict[str, list[asyncio.Event]] = {}
        self._lock = asyncio.Lock()
    
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
    ) -> SubagentRunRecord:
        """
        Register a new subagent run
        
        Args:
            child_session_key: Session key of child agent
            requester_session_key: Session key of requester
            task: Task description
            requester_origin: Origin context
            requester_display_key: Display key for requester
            cleanup: "delete" or "keep" session after completion
            label: Optional label
            
        Returns:
            Created SubagentRunRecord
        """
        run_id = str(uuid.uuid4())
        now_ms = int(time.time() * 1000)
        
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
            created_at=now_ms,
        )
        
        self._runs[run_id] = record
        self._persist()
        
        logger.info(f"Registered subagent run: {run_id} (session: {child_session_key})")
        
        return record
    
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
        outcome: dict[str, Any] | None = None
    ):
        """
        Mark subagent as ended
        
        Args:
            run_id: Run ID
            outcome: Outcome information
        """
        entry = self._runs.get(run_id)
        if not entry:
            return
        
        entry.ended_at = int(time.time() * 1000)
        entry.outcome = outcome
        self._persist()
        
        # Notify waiters
        if run_id in self._event_listeners:
            for event in self._event_listeners[run_id]:
                event.set()
            del self._event_listeners[run_id]
        
        logger.info(f"Subagent run {run_id} ended")
    
    def mark_cleanup_completed(self, run_id: str):
        """Mark cleanup as completed"""
        entry = self._runs.get(run_id)
        if entry:
            entry.cleanup_completed_at = int(time.time() * 1000)
            entry.cleanup_handled = True
            self._persist()
    
    def _persist(self):
        """Persist registry to disk"""
        try:
            save_subagent_registry_to_disk(self._runs)
        except Exception as e:
            logger.error(f"Failed to persist subagent registry: {e}")
    
    def restore_once(self):
        """Restore registry from disk (once)"""
        if self._restore_attempted:
            return
        
        self._restore_attempted = True
        
        try:
            restored = load_subagent_registry_from_disk()
            if restored:
                self._runs = restored
                logger.info(f"Restored {len(restored)} subagent runs from disk")
                
                # Resume incomplete runs
                self._resume_incomplete_runs()
        except Exception as e:
            logger.error(f"Failed to restore subagent registry: {e}")
    
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
                # TODO: Trigger announce and cleanup
                self._resumed_runs.add(run_id)
                continue
            
            # If not ended, wait for completion again
            logger.info(f"Resuming wait for run {run_id}")
            # TODO: Wait for completion again
            self._resumed_runs.add(run_id)
    
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


def init_subagent_registry():
    """Initialize and restore subagent registry"""
    registry = get_global_registry()
    registry.restore_once()
