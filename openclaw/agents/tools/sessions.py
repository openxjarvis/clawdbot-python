"""Session management tools"""

import logging
from typing import Any

from ..session import SessionManager
from .base import AgentTool, ToolResult

logger = logging.getLogger(__name__)


class SessionsListTool(AgentTool):
    """List all sessions with access control"""

    def __init__(
        self,
        session_manager: SessionManager,
        current_session_key: str | None = None,
        cfg: Any = None,
    ):
        super().__init__()
        self.name = "sessions_list"
        self.description = "List other sessions (incl. sub-agents) with filters/last"
        self.session_manager = session_manager
        self.current_session_key = current_session_key
        self.cfg = cfg

    def get_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}, "required": []}

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        """List sessions with visibility guard"""
        try:
            # Create visibility guard
            from openclaw.agents.tools.sessions_access import (
                create_agent_to_agent_policy,
                create_session_visibility_guard,
                resolve_session_tools_visibility,
            )
            
            a2a_policy = create_agent_to_agent_policy(self.cfg or {})
            visibility = resolve_session_tools_visibility(self.cfg or {})
            
            guard = await create_session_visibility_guard(
                action="list",
                requester_session_key=self.current_session_key or "main",
                visibility=visibility,
                a2a_policy=a2a_policy,
            )
            
            check = guard["check"]
            
            # List all sessions
            session_ids = self.session_manager.list_sessions()
            
            # Filter by access control
            accessible_sessions = []
            for session_id in session_ids:
                result = check(session_id)
                if result.allowed:
                    session = self.session_manager.get_session(session_id)
                    accessible_sessions.append({
                        "session_id": session_id,
                        "message_count": len(session.messages),
                        "last_message": (
                            session.messages[-1].timestamp if session.messages else None
                        ),
                    })
            
            # Format output
            if accessible_sessions:
                output = f"Found {len(accessible_sessions)} accessible session(s):\n\n"
                for info in accessible_sessions:
                    output += f"- **{info['session_id']}**: {info['message_count']} messages"
                    if info["last_message"]:
                        output += f" (last: {info['last_message']})"
                    output += "\n"
            else:
                output = "No accessible sessions found"

            return ToolResult(
                success=True,
                content=output,
                metadata={"sessions": accessible_sessions}
            )

        except Exception as e:
            logger.error(f"Sessions list error: {e}", exc_info=True)
            return ToolResult(success=False, content="", error=str(e))


class SessionsHistoryTool(AgentTool):
    """Get session history with access control"""

    def __init__(
        self,
        session_manager: SessionManager,
        current_session_key: str | None = None,
        cfg: Any = None,
    ):
        super().__init__()
        self.name = "sessions_history"
        self.description = "Fetch history for another session/sub-agent"
        self.session_manager = session_manager
        self.current_session_key = current_session_key
        self.cfg = cfg

    def get_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Session ID to get history from"},
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of messages to return",
                    "default": 50,
                },
            },
            "required": ["session_id"],
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        """Get session history with access control"""
        session_id = params.get("session_id", "")
        limit = params.get("limit", 50)

        if not session_id:
            return ToolResult(success=False, content="", error="session_id required")

        try:
            # Create visibility guard
            from openclaw.agents.tools.sessions_access import (
                create_agent_to_agent_policy,
                create_session_visibility_guard,
                resolve_session_tools_visibility,
            )
            
            a2a_policy = create_agent_to_agent_policy(self.cfg or {})
            visibility = resolve_session_tools_visibility(self.cfg or {})
            
            guard = await create_session_visibility_guard(
                action="history",
                requester_session_key=self.current_session_key or "main",
                visibility=visibility,
                a2a_policy=a2a_policy,
            )
            
            check = guard["check"]
            
            # Check access
            access_result = check(session_id)
            if not access_result.allowed:
                return ToolResult(
                    success=False,
                    content="",
                    error=access_result.error or "Access denied",
                )
            
            # Get session history
            session = self.session_manager.get_session(session_id)
            messages = session.get_messages(limit=limit)

            if not messages:
                return ToolResult(
                    success=True,
                    content=f"No messages in session '{session_id}'",
                    metadata={"session_id": session_id, "count": 0},
                )

            # Format messages
            output = f"Session '{session_id}' history ({len(messages)} messages):\n\n"
            for msg in messages:
                output += f"**{msg.role.upper()}** ({msg.timestamp}):\n{msg.content}\n\n"

            return ToolResult(
                success=True,
                content=output,
                metadata={"session_id": session_id, "count": len(messages)},
            )

        except Exception as e:
            logger.error(f"Sessions history error: {e}", exc_info=True)
            return ToolResult(success=False, content="", error=str(e))


class SessionsSendTool(AgentTool):
    """Send message to another session with access control"""

    def __init__(
        self,
        session_manager: SessionManager,
        current_session_key: str | None = None,
        cfg: Any = None,
    ):
        super().__init__()
        self.name = "sessions_send"
        self.description = "Send a message to another session/sub-agent"
        self.session_manager = session_manager
        self.current_session_key = current_session_key
        self.cfg = cfg

    def get_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Target session ID"},
                "message": {"type": "string", "description": "Message content to send"},
                "from_session": {
                    "type": "string",
                    "description": "Source session ID",
                    "default": "system",
                },
            },
            "required": ["session_id", "message"],
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        """Send message to session with access control"""
        session_id = params.get("session_id", "")
        message = params.get("message", "")
        from_session = params.get("from_session", self.current_session_key or "system")

        if not session_id or not message:
            return ToolResult(success=False, content="", error="session_id and message required")

        try:
            # Create visibility guard
            from openclaw.agents.tools.sessions_access import (
                create_agent_to_agent_policy,
                create_session_visibility_guard,
                resolve_session_tools_visibility,
            )
            
            a2a_policy = create_agent_to_agent_policy(self.cfg or {})
            visibility = resolve_session_tools_visibility(self.cfg or {})
            
            guard = await create_session_visibility_guard(
                action="send",
                requester_session_key=self.current_session_key or "main",
                visibility=visibility,
                a2a_policy=a2a_policy,
            )
            
            check = guard["check"]
            
            # Check access
            access_result = check(session_id)
            if not access_result.allowed:
                return ToolResult(
                    success=False,
                    content="",
                    error=access_result.error or "Access denied",
                )
            
            # Get target session
            session = self.session_manager.get_session(session_id)

            # Add message as user message with metadata
            prefix = f"[From {from_session}] "
            session.add_user_message(prefix + message)

            return ToolResult(
                success=True,
                content=f"Message sent to session '{session_id}'",
                metadata={"session_id": session_id, "from_session": from_session},
            )

        except Exception as e:
            logger.error(f"Sessions send error: {e}", exc_info=True)
            return ToolResult(success=False, content="", error=str(e))


class SessionsSpawnTool(AgentTool):
    """Spawn a subagent session to run a task.

    Mirrors TS createSessionsSpawnTool() in sessions-spawn-tool.ts.
    Schema fields align with TS: task, label, agentId, model, thinking,
    runTimeoutSeconds, cleanup.
    """

    def __init__(self, session_manager: SessionManager | None = None, gateway: Any = None):
        super().__init__()
        self.name = "sessions_spawn"
        self.description = (
            "Spawn a subagent session to work on a task asynchronously. "
            "Returns a session key you can use to check status via sessions_status."
        )
        self.session_manager = session_manager
        self.gateway = gateway

    def get_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "The task for the subagent to work on.",
                },
                "label": {
                    "type": "string",
                    "description": "Human-readable label for the spawned session.",
                },
                "agentId": {
                    "type": "string",
                    "description": "Agent ID to use. Defaults to the current agent.",
                },
                "model": {
                    "type": "string",
                    "description": "Model override for the spawned session (e.g. 'anthropic:claude-sonnet-4').",
                },
                "thinking": {
                    "type": "string",
                    "description": "Thinking/reasoning mode override ('auto', 'none', or a number of tokens).",
                },
                "runTimeoutSeconds": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Timeout in seconds for the spawned run (default: 600).",
                },
                "cleanup": {
                    "type": "string",
                    "enum": ["delete", "keep"],
                    "description": "Whether to delete the session after the run completes. Default: 'keep'.",
                },
            },
            "required": ["task"],
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        """Spawn subagent session."""
        task = params.get("task")
        if not isinstance(task, str) or not task.strip():
            return ToolResult(success=False, content="", error="'task' is required")

        label = params.get("label") or ""
        agent_id = params.get("agentId")
        model = params.get("model")
        thinking = params.get("thinking")
        cleanup = params.get("cleanup", "keep")
        if cleanup not in ("delete", "keep"):
            cleanup = "keep"
        run_timeout_seconds = params.get("runTimeoutSeconds")
        if run_timeout_seconds is not None:
            try:
                run_timeout_seconds = max(0, float(run_timeout_seconds))
            except (TypeError, ValueError):
                run_timeout_seconds = None

        try:
            import time
            session_id = (
                label.lower().replace(" ", "-")[:32]
                if label
                else f"spawned-{int(time.time())}"
            )

            if self.gateway is not None:
                spawn_fn = getattr(self.gateway, "spawn_subagent", None)
                if callable(spawn_fn):
                    result = await spawn_fn(
                        task=task.strip(),
                        label=label or None,
                        agent_id=agent_id,
                        model=model,
                        thinking=thinking,
                        run_timeout_seconds=run_timeout_seconds,
                        cleanup=cleanup,
                    )
                    if isinstance(result, dict):
                        session_key = result.get("sessionKey") or result.get("session_key") or session_id
                        return ToolResult(
                            success=True,
                            content=f"Spawned subagent session '{session_key}'. Task: {task.strip()[:120]}",
                            metadata=result,
                        )

            if self.session_manager is not None:
                session = self.session_manager.get_session(session_id)
                session.add_user_message(task.strip())
                return ToolResult(
                    success=True,
                    content=f"Spawned session '{session_id}'",
                    metadata={
                        "sessionKey": session_id,
                        "agentId": agent_id,
                        "model": model,
                        "cleanup": cleanup,
                    },
                )

            return ToolResult(
                success=True,
                content=f"Session spawn queued: {session_id}",
                metadata={"sessionKey": session_id},
            )

        except Exception as exc:
            logger.error("sessions_spawn error: %s", exc, exc_info=True)
            return ToolResult(success=False, content="", error=str(exc))
