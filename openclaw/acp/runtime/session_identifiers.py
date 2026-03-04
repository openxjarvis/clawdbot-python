"""ACP session identifier display helpers — mirrors src/acp/runtime/session-identifiers.ts

Formats session identity information for /status output and thread detail lines,
including agent-specific resume hints (codex resume <id>, kimi resume <id>, etc).
"""
from __future__ import annotations

from typing import Any

from .session_identity import (
    SessionAcpIdentity,
    SessionAcpMeta,
    is_session_identity_pending,
    resolve_session_identity_from_meta,
)

ACP_SESSION_IDENTITY_RENDERER_VERSION = "v1"
AcpSessionIdentifierRenderMode = str  # "status" | "thread"

_ACP_AGENT_RESUME_HINTS: dict[str, str] = {
    "codex": "codex resume {id}",
    "openai-codex": "codex resume {id}",
    "codex-cli": "codex resume {id}",
    "kimi": "kimi resume {id}",
    "moonshot-kimi": "kimi resume {id}",
}

_ACP_AGENT_RESUME_LABELS: dict[str, str] = {
    "codex": "Codex CLI",
    "openai-codex": "Codex CLI",
    "codex-cli": "Codex CLI",
    "kimi": "Kimi CLI",
    "moonshot-kimi": "Kimi CLI",
}


def _normalize_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


def _normalize_agent_hint_key(value: Any) -> str | None:
    normalized = _normalize_text(value)
    if not normalized:
        return None
    import re
    return re.sub(r"[\s_]+", "-", normalized).lower()


def _resolve_acp_agent_resume_hint_line(
    agent_id: str | None,
    agent_session_id: str | None,
) -> str | None:
    session_id = _normalize_text(agent_session_id)
    agent_key = _normalize_agent_hint_key(agent_id)
    if not session_id or not agent_key:
        return None
    cmd_template = _ACP_AGENT_RESUME_HINTS.get(agent_key)
    label = _ACP_AGENT_RESUME_LABELS.get(agent_key)
    if not cmd_template or not label:
        return None
    cmd = cmd_template.format(id=session_id)
    return f"resume in {label}: `{cmd}` (continues this conversation)."


def resolve_acp_session_identifier_lines(
    session_key: str,
    meta: SessionAcpMeta | None = None,
) -> list[str]:
    backend = _normalize_text(meta.get("backend") if meta else None) or "backend"
    identity = resolve_session_identity_from_meta(meta)
    return resolve_acp_session_identifier_lines_from_identity(
        backend=backend,
        identity=identity,
        mode="status",
    )


def resolve_acp_session_identifier_lines_from_identity(
    backend: str,
    identity: SessionAcpIdentity | None = None,
    mode: AcpSessionIdentifierRenderMode = "status",
) -> list[str]:
    bk = _normalize_text(backend) or "backend"
    agent_session_id = _normalize_text(identity.get("agentSessionId") if identity else None)
    acpx_session_id = _normalize_text(identity.get("acpxSessionId") if identity else None)
    acpx_record_id = _normalize_text(identity.get("acpxRecordId") if identity else None)
    has_identifier = bool(agent_session_id or acpx_session_id or acpx_record_id)

    if is_session_identity_pending(identity) and has_identifier:
        if mode == "status":
            return ["session ids: pending (available after the first reply)"]
        return []

    lines: list[str] = []
    if agent_session_id:
        lines.append(f"agent session id: {agent_session_id}")
    if acpx_session_id:
        lines.append(f"{bk} session id: {acpx_session_id}")
    if acpx_record_id:
        lines.append(f"{bk} record id: {acpx_record_id}")
    return lines


def resolve_acp_session_cwd(meta: SessionAcpMeta | None = None) -> str | None:
    if not meta:
        return None
    runtime_opts = meta.get("runtimeOptions") or {}
    cwd = _normalize_text(runtime_opts.get("cwd") if isinstance(runtime_opts, dict) else None)
    if cwd:
        return cwd
    return _normalize_text(meta.get("cwd"))


def resolve_acp_thread_session_detail_lines(
    session_key: str,
    meta: SessionAcpMeta | None = None,
) -> list[str]:
    identity = resolve_session_identity_from_meta(meta)
    backend = _normalize_text(meta.get("backend") if meta else None) or "backend"
    lines = resolve_acp_session_identifier_lines_from_identity(
        backend=backend,
        identity=identity,
        mode="thread",
    )
    if not lines:
        return lines
    hint = _resolve_acp_agent_resume_hint_line(
        agent_id=meta.get("agent") if meta else None,
        agent_session_id=identity.get("agentSessionId") if identity else None,
    )
    if hint:
        lines.append(hint)
    return lines
