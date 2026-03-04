"""ACP in-memory session store — mirrors src/acp/session.ts"""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from .types import AcpSession


class AcpSessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, AcpSession] = {}
        self._run_to_session: dict[str, str] = {}

    def create_session(
        self,
        *,
        session_key: str,
        cwd: str,
        session_id: str | None = None,
    ) -> AcpSession:
        sid = session_id or str(uuid.uuid4())
        session = AcpSession(
            session_id=sid,
            session_key=session_key,
            cwd=cwd,
            created_at=int(time.time() * 1000),
        )
        self._sessions[sid] = session
        return session

    def get_session(self, session_id: str) -> AcpSession | None:
        return self._sessions.get(session_id)

    def has_session(self, session_id: str) -> bool:
        return session_id in self._sessions

    def get_session_by_run_id(self, run_id: str) -> AcpSession | None:
        sid = self._run_to_session.get(run_id)
        return self._sessions.get(sid) if sid else None

    def set_active_run(
        self,
        session_id: str,
        run_id: str,
        abort_controller: Any,
    ) -> None:
        session = self._sessions.get(session_id)
        if not session:
            return
        session.active_run_id = run_id
        session.abort_controller = abort_controller
        self._run_to_session[run_id] = session_id

    def clear_active_run(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if not session:
            return
        if session.active_run_id:
            self._run_to_session.pop(session.active_run_id, None)
        session.active_run_id = None
        session.abort_controller = None

    def cancel_active_run(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if not session or not session.abort_controller:
            return False
        ctrl = session.abort_controller
        if isinstance(ctrl, asyncio.Event):
            ctrl.set()
        elif callable(getattr(ctrl, "cancel", None)):
            ctrl.cancel()
        if session.active_run_id:
            self._run_to_session.pop(session.active_run_id, None)
        session.abort_controller = None
        session.active_run_id = None
        return True

    def clear_all_sessions_for_test(self) -> None:
        for session in self._sessions.values():
            ctrl = session.abort_controller
            if ctrl is not None:
                if isinstance(ctrl, asyncio.Event):
                    ctrl.set()
                elif callable(getattr(ctrl, "cancel", None)):
                    ctrl.cancel()
        self._sessions.clear()
        self._run_to_session.clear()


default_acp_session_store = AcpSessionStore()


def create_in_memory_session_store() -> AcpSessionStore:
    return AcpSessionStore()
