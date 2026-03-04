"""ACP runtime type definitions — mirrors src/acp/runtime/types.ts"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Callable, Literal, TypedDict


AcpRuntimePromptMode = Literal["prompt", "steer"]
AcpRuntimeSessionMode = Literal["persistent", "oneshot"]
AcpRuntimeControl = Literal[
    "session/set_mode",
    "session/set_config_option",
    "session/status",
]

AcpSessionUpdateTag = str


class AcpRuntimeHandle(TypedDict, total=False):
    sessionKey: str
    backend: str
    runtimeSessionName: str
    cwd: str
    acpxRecordId: str
    backendSessionId: str
    agentSessionId: str


class AcpRuntimeEnsureInput(TypedDict, total=False):
    sessionKey: str
    agent: str
    mode: AcpRuntimeSessionMode
    cwd: str
    env: dict[str, str]


class AcpRuntimeTurnInput(TypedDict, total=False):
    handle: AcpRuntimeHandle
    text: str
    mode: AcpRuntimePromptMode
    requestId: str
    signal: Any  # asyncio.Event or similar


class AcpRuntimeCapabilities(TypedDict, total=False):
    controls: list[AcpRuntimeControl]
    configOptionKeys: list[str]


class AcpRuntimeStatus(TypedDict, total=False):
    summary: str
    acpxRecordId: str
    backendSessionId: str
    agentSessionId: str
    details: dict[str, Any]


class AcpRuntimeDoctorReport(TypedDict, total=False):
    ok: bool
    code: str
    message: str
    installCommand: str
    details: list[str]


# AcpRuntimeEvent — discriminated union by "type" field
AcpRuntimeEvent = dict[str, Any]
"""
Possible shapes:
  {"type": "text_delta",  "text": str, "stream"?: "output"|"thought", "tag"?: str}
  {"type": "status",      "text": str, "tag"?: str, "used"?: int, "size"?: int}
  {"type": "tool_call",   "text": str, "toolCallId"?: str, "status"?: str, "title"?: str}
  {"type": "done",        "stopReason"?: str}
  {"type": "error",       "message": str, "code"?: str, "retryable"?: bool}
"""


class AcpRuntime(ABC):
    """
    Abstract ACP runtime backend interface.

    Backends (e.g. acpx plugin) implement this interface and register
    themselves via register_acp_runtime_backend().
    """

    @abstractmethod
    async def ensure_session(self, input: AcpRuntimeEnsureInput) -> AcpRuntimeHandle:
        """Create or retrieve a backend session for the given session key."""

    @abstractmethod
    async def run_turn(self, input: AcpRuntimeTurnInput) -> AsyncIterator[AcpRuntimeEvent]:
        """Stream events for a single prompt turn."""

    async def get_capabilities(
        self, input: dict[str, Any]
    ) -> AcpRuntimeCapabilities:
        return {"controls": []}

    async def get_status(self, input: dict[str, Any]) -> AcpRuntimeStatus:
        return {}

    async def set_mode(self, input: dict[str, Any]) -> None:
        pass

    async def set_config_option(self, input: dict[str, Any]) -> None:
        pass

    async def doctor(self) -> AcpRuntimeDoctorReport:
        return {"ok": True, "message": "No doctor check implemented."}

    @abstractmethod
    async def cancel(self, input: dict[str, Any]) -> None:
        """Cancel an in-flight turn."""

    @abstractmethod
    async def close(self, input: dict[str, Any]) -> None:
        """Close/release a backend session."""
