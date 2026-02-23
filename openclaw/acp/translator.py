"""ACP gateway agent translator — mirrors src/acp/translator.ts

Bridges the ACP protocol (IDE/client side) with the OpenClaw gateway (RPC calls).
"""
from __future__ import annotations

import asyncio
import logging
import sys
import uuid
from dataclasses import dataclass, field
from typing import Any

from .commands import get_available_commands
from .event_mapper import (
    extract_attachments_from_prompt,
    extract_text_from_prompt,
    format_tool_title,
    infer_tool_kind,
)
from .meta import read_bool, read_number, read_string
from .session import AcpSessionStore, create_in_memory_session_store
from .session_mapper import parse_session_meta, reset_session_if_needed, resolve_session_key
from .types import ACP_AGENT_INFO, AcpServerOptions

logger = logging.getLogger(__name__)

# ACP protocol version — keep in sync with @agentclientprotocol/sdk
PROTOCOL_VERSION = "1.0"


@dataclass
class _PendingPrompt:
    session_id: str
    session_key: str
    idempotency_key: str
    future: asyncio.Future
    sent_text_length: int = 0
    sent_text: str = ""
    tool_calls: set[str] = field(default_factory=set)


class AcpGatewayAgent:
    """
    Gateway-backed ACP agent.

    Receives ACP protocol messages from the IDE (initialize, prompt, cancel, …),
    translates them into gateway RPC calls (chat.send, sessions.*, …),
    and maps gateway events back into ACP streaming updates.
    """

    def __init__(
        self,
        connection: Any,
        gateway: Any,
        opts: AcpServerOptions | None = None,
        session_store: AcpSessionStore | None = None,
    ) -> None:
        self._connection = connection
        self._gateway = gateway
        self._opts = opts or AcpServerOptions()
        self._session_store = session_store or create_in_memory_session_store()
        self._pending: dict[str, _PendingPrompt] = {}
        self._log = (
            (lambda msg: sys.stderr.write(f"[acp] {msg}\n"))
            if self._opts.verbose
            else (lambda msg: None)
        )

    def start(self) -> None:
        self._log("ready")

    def handle_gateway_reconnect(self) -> None:
        self._log("gateway reconnected")

    def handle_gateway_disconnect(self, reason: str) -> None:
        self._log(f"gateway disconnected: {reason}")
        for pending in list(self._pending.values()):
            if not pending.future.done():
                pending.future.set_exception(
                    RuntimeError(f"Gateway disconnected: {reason}")
                )
            self._session_store.clear_active_run(pending.session_id)
        self._pending.clear()

    async def handle_gateway_event(self, evt: dict) -> None:
        event = evt.get("event")
        if event == "chat":
            await self._handle_chat_event(evt)
        elif event == "agent":
            await self._handle_agent_event(evt)

    # ------------------------------------------------------------------
    # ACP protocol handlers
    # ------------------------------------------------------------------

    async def initialize(self, params: dict) -> dict:
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "agentCapabilities": {
                "loadSession": True,
                "promptCapabilities": {
                    "image": True,
                    "audio": False,
                    "embeddedContext": True,
                },
                "mcpCapabilities": {"http": False, "sse": False},
                "sessionCapabilities": {"list": {}},
            },
            "agentInfo": ACP_AGENT_INFO,
            "authMethods": [],
        }

    async def authenticate(self, params: dict) -> dict:
        return {"ok": True}

    async def new_session(self, params: dict) -> dict:
        import os
        meta = parse_session_meta(params.get("_meta"))
        cwd = os.getcwd()
        fallback_key = f"agent:main:{uuid.uuid4().hex[:8]}"
        try:
            session_key = await resolve_session_key(
                meta=meta,
                fallback_key=fallback_key,
                gateway=self._gateway,
                opts=self._opts,
            )
        except Exception as e:
            return {"ok": False, "error": str(e)}

        await reset_session_if_needed(
            meta=meta,
            session_key=session_key,
            gateway=self._gateway,
            opts=self._opts,
        )

        session = self._session_store.create_session(session_key=session_key, cwd=cwd)
        await self._send_available_commands(session.session_id)
        return {"ok": True, "sessionId": session.session_id, "sessionKey": session_key}

    async def load_session(self, params: dict) -> dict:
        import os
        meta = parse_session_meta(params.get("_meta"))
        cwd = os.getcwd()
        session_key = params.get("sessionId") or params.get("sessionKey") or ""
        if not session_key:
            return {"ok": False, "error": "sessionId or sessionKey required"}

        session = self._session_store.create_session(
            session_key=session_key, cwd=cwd, session_id=params.get("sessionId")
        )
        await reset_session_if_needed(
            meta=meta,
            session_key=session_key,
            gateway=self._gateway,
            opts=self._opts,
        )
        await self._send_available_commands(session.session_id)
        return {"ok": True, "sessionId": session.session_id}

    async def list_sessions(self, params: dict) -> dict:
        try:
            result = await self._gateway.request("sessions.list", {})
            return {"ok": True, "sessions": result or []}
        except Exception as e:
            return {"ok": False, "error": str(e), "sessions": []}

    async def set_session_mode(self, params: dict) -> dict:
        return {"ok": True}

    async def prompt(self, params: dict) -> dict:
        session_id = params.get("sessionId", "")
        session = self._session_store.get_session(session_id)
        if not session:
            return {"stopReason": "error"}

        content = params.get("prompt") or []
        meta = params.get("_meta") or {}

        message = extract_text_from_prompt(content) if isinstance(content, list) else str(content)
        attachments = extract_attachments_from_prompt(content) if isinstance(content, list) else []

        if self._opts.prefix_cwd and session.cwd:
            message = f"[cwd: {session.cwd}]\n{message}" if message else f"[cwd: {session.cwd}]"

        run_id = str(uuid.uuid4())
        cancel_event = asyncio.Event()
        self._session_store.set_active_run(session_id, run_id, cancel_event)

        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()

        pending = _PendingPrompt(
            session_id=session_id,
            session_key=session.session_key,
            idempotency_key=run_id,
            future=future,
        )
        self._pending[session_id] = pending

        thinking = read_string(meta, ["thinking", "thinkingLevel"])
        deliver = read_bool(meta, ["deliver"])
        timeout_ms = read_number(meta, ["timeoutMs"])

        request_payload: dict = {
            "sessionKey": session.session_key,
            "message": message,
            "idempotencyKey": run_id,
        }
        if attachments:
            request_payload["attachments"] = attachments
        if thinking is not None:
            request_payload["thinking"] = thinking
        if deliver is not None:
            request_payload["deliver"] = deliver
        if timeout_ms is not None:
            request_payload["timeoutMs"] = timeout_ms

        asyncio.ensure_future(
            self._gateway.request("chat.send", request_payload, expect_final=True)
        ).add_done_callback(
            lambda t: self._on_chat_send_done(t, session_id)
        )

        try:
            return await future
        except asyncio.CancelledError:
            return {"stopReason": "cancelled"}
        except Exception:
            return {"stopReason": "error"}

    async def cancel(self, params: dict) -> None:
        session_id = params.get("sessionId", "")
        session = self._session_store.get_session(session_id)
        if not session:
            return

        self._session_store.cancel_active_run(session_id)
        try:
            await self._gateway.request("chat.abort", {"sessionKey": session.session_key})
        except Exception as e:
            self._log(f"cancel error: {e}")

        pending = self._pending.pop(session_id, None)
        if pending and not pending.future.done():
            pending.future.set_result({"stopReason": "cancelled"})

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _on_chat_send_done(self, task: asyncio.Task, session_id: str) -> None:
        if task.exception():
            pending = self._pending.pop(session_id, None)
            self._session_store.clear_active_run(session_id)
            if pending and not pending.future.done():
                pending.future.set_exception(task.exception())

    async def _handle_agent_event(self, evt: dict) -> None:
        payload = evt.get("payload") or {}
        stream = payload.get("stream")
        data = payload.get("data") or {}
        session_key = payload.get("sessionKey")

        if stream != "tool" or not data or not session_key:
            return

        phase = data.get("phase")
        name = data.get("name")
        tool_call_id = data.get("toolCallId")
        if not tool_call_id:
            return

        pending = self._find_pending_by_session_key(session_key)
        if not pending:
            return

        if phase == "start":
            if tool_call_id in pending.tool_calls:
                return
            pending.tool_calls.add(tool_call_id)
            args = data.get("args")
            await self._connection_session_update(pending.session_id, {
                "sessionUpdate": "tool_call",
                "toolCallId": tool_call_id,
                "title": format_tool_title(name, args),
                "status": "in_progress",
                "rawInput": args,
                "kind": infer_tool_kind(name),
            })
        elif phase == "result":
            is_error = bool(data.get("isError"))
            await self._connection_session_update(pending.session_id, {
                "sessionUpdate": "tool_call_update",
                "toolCallId": tool_call_id,
                "status": "failed" if is_error else "completed",
                "rawOutput": data.get("result"),
            })

    async def _handle_chat_event(self, evt: dict) -> None:
        payload = evt.get("payload") or {}
        session_key = payload.get("sessionKey")
        state = payload.get("state")
        run_id = payload.get("runId")
        message_data = payload.get("message") or {}

        if not session_key or not state:
            return

        pending = self._find_pending_by_session_key(session_key)
        if not pending:
            return

        if run_id and pending.idempotency_key != run_id:
            return

        if state == "delta" and message_data:
            await self._handle_delta_event(pending.session_id, message_data)
            return

        if state == "final":
            self._finish_prompt(pending.session_id, "end_turn")
        elif state == "aborted":
            self._finish_prompt(pending.session_id, "cancelled")
        elif state == "error":
            self._finish_prompt(pending.session_id, "refusal")

    async def _handle_delta_event(self, session_id: str, message_data: dict) -> None:
        content = message_data.get("content") or []
        full_text = ""
        for c in content:
            if isinstance(c, dict) and c.get("type") == "text":
                full_text = c.get("text", "")
                break

        pending = self._pending.get(session_id)
        if not pending:
            return

        sent_so_far = pending.sent_text_length
        if len(full_text) <= sent_so_far:
            return

        new_text = full_text[sent_so_far:]
        pending.sent_text_length = len(full_text)
        pending.sent_text = full_text

        await self._connection_session_update(session_id, {
            "sessionUpdate": "agent_message_chunk",
            "content": {"type": "text", "text": new_text},
        })

    def _finish_prompt(self, session_id: str, stop_reason: str) -> None:
        pending = self._pending.pop(session_id, None)
        self._session_store.clear_active_run(session_id)
        if pending and not pending.future.done():
            pending.future.set_result({"stopReason": stop_reason})

    def _find_pending_by_session_key(self, session_key: str) -> _PendingPrompt | None:
        for p in self._pending.values():
            if p.session_key == session_key:
                return p
        return None

    async def _send_available_commands(self, session_id: str) -> None:
        await self._connection_session_update(session_id, {
            "sessionUpdate": "available_commands_update",
            "availableCommands": get_available_commands(),
        })

    async def _connection_session_update(self, session_id: str, update: dict) -> None:
        fn = getattr(self._connection, "session_update", None) or \
             getattr(self._connection, "sessionUpdate", None)
        if callable(fn):
            await fn({"sessionId": session_id, "update": update})
