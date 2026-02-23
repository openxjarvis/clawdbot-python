"""ACP session-mapper — mirrors src/acp/session-mapper.ts"""
from __future__ import annotations

from typing import Any

from .meta import read_bool, read_string


class AcpSessionMeta:
    def __init__(
        self,
        session_key: str | None = None,
        session_label: str | None = None,
        reset_session: bool | None = None,
        require_existing: bool | None = None,
        prefix_cwd: bool | None = None,
    ) -> None:
        self.session_key = session_key
        self.session_label = session_label
        self.reset_session = reset_session
        self.require_existing = require_existing
        self.prefix_cwd = prefix_cwd


def parse_session_meta(meta: Any) -> AcpSessionMeta:
    if not meta or not isinstance(meta, dict):
        return AcpSessionMeta()
    return AcpSessionMeta(
        session_key=read_string(meta, ["sessionKey", "session", "key"]),
        session_label=read_string(meta, ["sessionLabel", "label"]),
        reset_session=read_bool(meta, ["resetSession", "reset"]),
        require_existing=read_bool(meta, ["requireExistingSession", "requireExisting"]),
        prefix_cwd=read_bool(meta, ["prefixCwd"]),
    )


async def resolve_session_key(
    *,
    meta: AcpSessionMeta,
    fallback_key: str,
    gateway: Any,
    opts: Any,
) -> str:
    requested_label = meta.session_label or (getattr(opts, "default_session_label", None))
    requested_key = meta.session_key or (getattr(opts, "default_session_key", None))
    require_existing = meta.require_existing \
        if meta.require_existing is not None \
        else (getattr(opts, "require_existing_session", False) or False)

    if meta.session_label:
        resolved = await gateway.request("sessions.resolve", {"label": meta.session_label})
        if not (resolved and resolved.get("key")):
            raise ValueError(f"Unable to resolve session label: {meta.session_label}")
        return resolved["key"]

    if meta.session_key:
        if not require_existing:
            return meta.session_key
        resolved = await gateway.request("sessions.resolve", {"key": meta.session_key})
        if not (resolved and resolved.get("key")):
            raise ValueError(f"Session key not found: {meta.session_key}")
        return resolved["key"]

    if requested_label:
        resolved = await gateway.request("sessions.resolve", {"label": requested_label})
        if not (resolved and resolved.get("key")):
            raise ValueError(f"Unable to resolve session label: {requested_label}")
        return resolved["key"]

    if requested_key:
        if not require_existing:
            return requested_key
        resolved = await gateway.request("sessions.resolve", {"key": requested_key})
        if not (resolved and resolved.get("key")):
            raise ValueError(f"Session key not found: {requested_key}")
        return resolved["key"]

    return fallback_key


async def reset_session_if_needed(
    *,
    meta: AcpSessionMeta,
    session_key: str,
    gateway: Any,
    opts: Any,
) -> None:
    reset = meta.reset_session \
        if meta.reset_session is not None \
        else (getattr(opts, "reset_session", False) or False)
    if not reset:
        return
    await gateway.request("sessions.reset", {"key": session_key})
