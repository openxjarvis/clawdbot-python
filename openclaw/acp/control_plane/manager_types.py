"""ACP session manager type definitions — mirrors src/acp/control-plane/manager.types.ts"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class AcpSessionResolution:
    kind: str  # "none" | "stale" | "ready"
    session_key: str
    error: Any = None   # AcpRuntimeError | None
    meta: Any = None    # SessionAcpMeta | None


@dataclass
class AcpInitializeSessionInput:
    session_key: str
    agent: str
    mode: str  # "persistent" | "oneshot"
    cfg: Any = None
    cwd: Optional[str] = None
    backend_id: Optional[str] = None


@dataclass
class AcpRunTurnInput:
    session_key: str
    text: str
    mode: str  # "prompt" | "steer"
    request_id: str
    cfg: Any = None
    signal: Any = None  # asyncio.Event or similar
    on_event: Optional[Callable] = None


@dataclass
class AcpCloseSessionInput:
    session_key: str
    reason: str
    cfg: Any = None
    clear_meta: bool = False
    allow_backend_unavailable: bool = False
    require_acp_session: bool = True


@dataclass
class AcpCloseSessionResult:
    runtime_closed: bool
    runtime_notice: Optional[str] = None
    meta_cleared: bool = False


@dataclass
class AcpSessionStatus:
    session_key: str
    backend: str
    agent: str
    state: Any  # SessionAcpMeta state
    mode: str
    runtime_options: dict = field(default_factory=dict)
    capabilities: dict = field(default_factory=dict)
    identity: Any = None
    runtime_status: Any = None
    last_activity_at: float = 0.0
    last_error: Optional[str] = None


@dataclass
class AcpManagerObservabilitySnapshot:
    runtime_cache: dict = field(default_factory=dict)
    turns: dict = field(default_factory=dict)
    errors_by_code: dict = field(default_factory=dict)


@dataclass
class AcpStartupIdentityReconcileResult:
    checked: int = 0
    resolved: int = 0
    failed: int = 0


@dataclass
class ActiveTurnState:
    runtime: Any
    handle: dict
    cancel_event: Any = None  # asyncio.Event
    cancel_task: Any = None   # asyncio.Task


@dataclass
class TurnLatencyStats:
    completed: int = 0
    failed: int = 0
    total_ms: float = 0.0
    max_ms: float = 0.0
