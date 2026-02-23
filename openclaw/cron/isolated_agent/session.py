"""Session management for isolated cron agents.

Mirrors TypeScript: openclaw/src/cron/isolated-agent/session.ts
"""
from __future__ import annotations

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
        
        # Load existing session if it exists
        if self.session_path.exists():
            self._load_metadata()
    
    def _load_metadata(self) -> None:
        """Load session metadata"""
        # For now, just check if session exists
        # Full metadata loading would parse the JSONL file
        logger.debug(f"Loaded metadata for session: {self.session_key}")
    
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
        """
        if not self.exists():
            return True
        if reset_policy == "always":
            return True
        if reset_policy == "never":
            return False
        now_ms = int(time.time() * 1000)
        if last_run_at_ms is None:
            return True
        elapsed_ms = now_ms - last_run_at_ms
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
