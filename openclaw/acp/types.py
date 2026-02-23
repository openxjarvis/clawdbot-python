"""ACP type definitions — mirrors src/acp/types.ts"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

try:
    from openclaw.version import VERSION
except ImportError:
    VERSION = "0.0.0"


@dataclass
class AcpSession:
    session_id: str
    session_key: str
    cwd: str
    created_at: int  # epoch ms
    abort_controller: Any = None  # asyncio.Event or similar cancel token
    active_run_id: str | None = None


@dataclass
class AcpServerOptions:
    gateway_url: str | None = None
    gateway_token: str | None = None
    gateway_password: str | None = None
    default_session_key: str | None = None
    default_session_label: str | None = None
    require_existing_session: bool = False
    reset_session: bool = False
    prefix_cwd: bool = True
    verbose: bool = False


ACP_AGENT_INFO = {
    "name": "openclaw-acp",
    "title": "OpenClaw ACP Gateway",
    "version": VERSION,
}
