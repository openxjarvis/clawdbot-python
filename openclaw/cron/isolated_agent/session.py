"""Session management for isolated cron agents.

Mirrors TypeScript: openclaw/src/cron/isolated-agent/session.ts
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)

# Session reset policy — matches TS CronSessionReset
CronSessionReset = Literal["never", "always", "daily", "weekly"]


class IsolatedAgentSession:
    """
    Session manager for isolated cron agents
    
    Each cron job gets its own isolated session with key: cron:{jobId}
    """
    
    def __init__(self, sessions_dir: Path, job_id: str, agent_id: str | None = None):
        """
        Initialize isolated session
        
        Args:
            sessions_dir: Base sessions directory
            job_id: Cron job ID
            agent_id: Optional agent ID (scoped to agent)
        """
        self.job_id = job_id
        self.agent_id = agent_id
        
        # Session key format: cron:{jobId} or {agentId}:cron:{jobId}
        if agent_id:
            self.session_key = f"{agent_id}:cron:{job_id}"
        else:
            self.session_key = f"cron:{job_id}"
        
        # Session path
        self.session_path = sessions_dir / f"{self.session_key}.jsonl"
        
        # Ensure directory exists
        self.session_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Session state
        self.model: str | None = None
        self.token_count: int = 0
        self.skills: list[str] = []
        self.metadata: dict[str, Any] = {}

        # Persisted metadata parsed from JSONL
        self.last_run_at_ms: int | None = None
        self.last_active_at_ms: int | None = None
        self.compaction_count: int = 0

        # Load existing session if it exists
        if self.session_path.exists():
            self._load_metadata()

    def _load_metadata(self) -> None:
        """Parse session metadata from the JSONL file.

        Mirrors TS ``loadCronSessionMetadata`` in isolated-agent/session.ts:
        reads the last ``metadata`` entry from the JSONL to recover
        ``last_active_at``, ``compaction_count``, etc.  These values are used
        by ``is_fresh()`` to decide whether the session should be reset.

        The JSONL format is one JSON object per line. Metadata lines are those
        with ``"type": "metadata"`` (or the last line in the session file that
        has a recognisable shape).  We also accept bare timestamp fields at
        the top level so the reader works with both compacted and legacy files.
        """
        try:
            last_ms: int | None = None
            compaction_count = 0

            with self.session_path.open("r", encoding="utf-8") as fh:
                for raw_line in fh:
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(obj, dict):
                        continue

                    # Accept "metadata" typed entries (canonical format)
                    entry_type = obj.get("type") or obj.get("role") or ""
                    if entry_type == "metadata":
                        ts = obj.get("last_active_at") or obj.get("lastActiveAt")
                        if isinstance(ts, (int, float)):
                            last_ms = int(ts)
                        cc = obj.get("compaction_count") or obj.get("compactionCount")
                        if isinstance(cc, int):
                            compaction_count = cc
                        continue

                    # Also check for timestamp fields on any line (fallback)
                    for ts_key in ("timestamp", "ts", "created_at", "last_active_at", "lastActiveAt"):
                        ts_val = obj.get(ts_key)
                        if isinstance(ts_val, (int, float)) and ts_val > 0:
                            last_ms = int(ts_val)
                            break

            if last_ms is not None:
                self.last_active_at_ms = last_ms
                self.last_run_at_ms = last_ms
            self.compaction_count = compaction_count
            logger.debug(
                "Loaded metadata for session %s: last_active_at=%s, compaction_count=%d",
                self.session_key,
                last_ms,
                compaction_count,
            )
        except OSError as exc:
            logger.debug("Could not read session file %s: %s", self.session_path, exc)
    
    def exists(self) -> bool:
        """Check if session exists"""
        return self.session_path.exists()

    def is_fresh(self, reset_policy: CronSessionReset = "never", last_run_at_ms: int | None = None) -> bool:
        """Check if this session should be treated as fresh (i.e., needs reset).

        Mirrors TS resolveCronSession freshness logic:
        - "always"  → always fresh (start new session each run)
        - "daily"   → fresh if last_run_at_ms was > 24 h ago (or missing)
        - "weekly"  → fresh if last_run_at_ms was > 7 days ago (or missing)
        - "never"   → never fresh (reuse session forever) — default

        ``last_run_at_ms`` may be supplied by the caller (from job state).
        If not supplied, falls back to ``self.last_run_at_ms`` loaded from the
        JSONL session file by ``_load_metadata()``.
        """
        if not self.exists():
            return True
        if reset_policy == "always":
            return True
        if reset_policy == "never":
            return False
        now_ms = int(time.time() * 1000)
        # Prefer caller-supplied value; fall back to value parsed from JSONL
        effective_last_run = last_run_at_ms if last_run_at_ms is not None else self.last_run_at_ms
        if effective_last_run is None:
            return True
        elapsed_ms = now_ms - effective_last_run
        if reset_policy == "daily":
            return elapsed_ms > 24 * 60 * 60 * 1000
        if reset_policy == "weekly":
            return elapsed_ms > 7 * 24 * 60 * 60 * 1000
        return False

    def get_session_key(self) -> str:
        """Get session key"""
        return self.session_key

    def get_session_path(self) -> Path:
        """Get session file path"""
        return self.session_path
    
    def update_metadata(
        self,
        model: str | None = None,
        token_count: int | None = None,
        skills: list[str] | None = None,
        **kwargs,
    ) -> None:
        """
        Update session metadata
        
        Args:
            model: Model being used
            token_count: Current token count
            skills: Active skills
            **kwargs: Additional metadata
        """
        if model is not None:
            self.model = model
        if token_count is not None:
            self.token_count = token_count
        if skills is not None:
            self.skills = skills
        
        self.metadata.update(kwargs)
        
        logger.debug(f"Updated metadata for session: {self.session_key}")


def resolve_isolated_session(
    sessions_dir: Path,
    job_id: str,
    agent_id: str | None = None,
) -> IsolatedAgentSession:
    """
    Resolve or create isolated session for cron job
    
    Args:
        sessions_dir: Sessions directory
        job_id: Cron job ID
        agent_id: Optional agent ID
        
    Returns:
        Isolated agent session
    """
    session = IsolatedAgentSession(sessions_dir, job_id, agent_id)
    
    if session.exists():
        logger.info(f"Using existing isolated session: {session.session_key}")
    else:
        logger.info(f"Creating new isolated session: {session.session_key}")
    
    return session
