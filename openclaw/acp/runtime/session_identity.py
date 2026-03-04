"""ACP session identity helpers — mirrors src/acp/runtime/session-identity.ts

Manages the pending→resolved state machine for ACP session identities,
which track backend-specific identifiers (acpxRecordId, acpxSessionId,
agentSessionId) across ensure/status/event lifecycle phases.
"""
from __future__ import annotations

import time
from typing import Any

# SessionAcpIdentity shape:
#   state: "pending" | "resolved"
#   acpxRecordId?: str
#   acpxSessionId?: str
#   agentSessionId?: str
#   source: "ensure" | "status" | "event"
#   lastUpdatedAt: int (ms timestamp)

SessionAcpIdentity = dict[str, Any]
SessionAcpMeta = dict[str, Any]


def _normalize_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


def _normalize_identity_state(value: Any) -> str | None:
    if value not in ("pending", "resolved"):
        return None
    return value


def _normalize_identity_source(value: Any) -> str | None:
    if value not in ("ensure", "status", "event"):
        return None
    return value


def _normalize_identity(identity: SessionAcpIdentity | None) -> SessionAcpIdentity | None:
    if not identity:
        return None
    state = _normalize_identity_state(identity.get("state"))
    source = _normalize_identity_source(identity.get("source"))
    acpx_record_id = _normalize_text(identity.get("acpxRecordId"))
    acpx_session_id = _normalize_text(identity.get("acpxSessionId"))
    agent_session_id = _normalize_text(identity.get("agentSessionId"))
    last_updated = identity.get("lastUpdatedAt")
    if not (isinstance(last_updated, (int, float)) and last_updated == last_updated):
        last_updated = None

    has_any_id = bool(acpx_record_id or acpx_session_id or agent_session_id)
    if not state and not source and not has_any_id and last_updated is None:
        return None

    resolved = bool(acpx_session_id or agent_session_id)
    normalized_state = state or ("resolved" if resolved else "pending")

    result: SessionAcpIdentity = {"state": normalized_state, "source": source or "status", "lastUpdatedAt": int(last_updated) if last_updated is not None else int(time.time() * 1000)}
    if acpx_record_id:
        result["acpxRecordId"] = acpx_record_id
    if acpx_session_id:
        result["acpxSessionId"] = acpx_session_id
    if agent_session_id:
        result["agentSessionId"] = agent_session_id
    return result


def resolve_session_identity_from_meta(
    meta: SessionAcpMeta | None,
) -> SessionAcpIdentity | None:
    if not meta:
        return None
    return _normalize_identity(meta.get("identity"))


def identity_has_stable_session_id(identity: SessionAcpIdentity | None) -> bool:
    if not identity:
        return False
    return bool(identity.get("acpxSessionId") or identity.get("agentSessionId"))


def is_session_identity_pending(identity: SessionAcpIdentity | None) -> bool:
    if not identity:
        return True
    return identity.get("state") == "pending"


def identity_equals(
    left: SessionAcpIdentity | None,
    right: SessionAcpIdentity | None,
) -> bool:
    a = _normalize_identity(left)
    b = _normalize_identity(right)
    if not a and not b:
        return True
    if not a or not b:
        return False
    return (
        a.get("state") == b.get("state")
        and a.get("acpxRecordId") == b.get("acpxRecordId")
        and a.get("acpxSessionId") == b.get("acpxSessionId")
        and a.get("agentSessionId") == b.get("agentSessionId")
        and a.get("source") == b.get("source")
    )


def merge_session_identity(
    current: SessionAcpIdentity | None,
    incoming: SessionAcpIdentity | None,
    now: int | None = None,
) -> SessionAcpIdentity | None:
    """Merge two session identities, preferring more-resolved data."""
    if now is None:
        now = int(time.time() * 1000)
    c = _normalize_identity(current)
    i = _normalize_identity(incoming)
    if not c:
        if not i:
            return None
        return {**i, "lastUpdatedAt": now}
    if not i:
        return c

    current_resolved = c.get("state") == "resolved"
    incoming_resolved = i.get("state") == "resolved"
    allow_incoming = not current_resolved or incoming_resolved

    next_record = (i.get("acpxRecordId") if allow_incoming and i.get("acpxRecordId") else None) or c.get("acpxRecordId")
    next_acpx = (i.get("acpxSessionId") if allow_incoming and i.get("acpxSessionId") else None) or c.get("acpxSessionId")
    next_agent = (i.get("agentSessionId") if allow_incoming and i.get("agentSessionId") else None) or c.get("agentSessionId")

    next_resolved = bool(next_acpx or next_agent)
    if next_resolved:
        next_state = "resolved"
    elif current_resolved:
        next_state = "resolved"
    else:
        next_state = i.get("state", "pending")

    next_source = i.get("source") if allow_incoming else c.get("source")
    result: SessionAcpIdentity = {
        "state": next_state,
        "source": next_source or "status",
        "lastUpdatedAt": now,
    }
    if next_record:
        result["acpxRecordId"] = next_record
    if next_acpx:
        result["acpxSessionId"] = next_acpx
    if next_agent:
        result["agentSessionId"] = next_agent
    return result


def create_identity_from_ensure(
    handle: dict[str, Any],
    now: int | None = None,
) -> SessionAcpIdentity | None:
    if now is None:
        now = int(time.time() * 1000)
    acpx_record_id = _normalize_text(handle.get("acpxRecordId"))
    acpx_session_id = _normalize_text(handle.get("backendSessionId"))
    agent_session_id = _normalize_text(handle.get("agentSessionId"))
    if not acpx_record_id and not acpx_session_id and not agent_session_id:
        return None
    result: SessionAcpIdentity = {"state": "pending", "source": "ensure", "lastUpdatedAt": now}
    if acpx_record_id:
        result["acpxRecordId"] = acpx_record_id
    if acpx_session_id:
        result["acpxSessionId"] = acpx_session_id
    if agent_session_id:
        result["agentSessionId"] = agent_session_id
    return result


def create_identity_from_status(
    status: dict[str, Any] | None,
    now: int | None = None,
) -> SessionAcpIdentity | None:
    if now is None:
        now = int(time.time() * 1000)
    if not status:
        return None
    details = status.get("details") or {}
    acpx_record_id = _normalize_text(status.get("acpxRecordId")) or _normalize_text(details.get("acpxRecordId"))
    acpx_session_id = (_normalize_text(status.get("backendSessionId"))
                       or _normalize_text(details.get("backendSessionId"))
                       or _normalize_text(details.get("acpxSessionId")))
    agent_session_id = _normalize_text(status.get("agentSessionId")) or _normalize_text(details.get("agentSessionId"))
    if not acpx_record_id and not acpx_session_id and not agent_session_id:
        return None
    resolved = bool(acpx_session_id or agent_session_id)
    result: SessionAcpIdentity = {
        "state": "resolved" if resolved else "pending",
        "source": "status",
        "lastUpdatedAt": now,
    }
    if acpx_record_id:
        result["acpxRecordId"] = acpx_record_id
    if acpx_session_id:
        result["acpxSessionId"] = acpx_session_id
    if agent_session_id:
        result["agentSessionId"] = agent_session_id
    return result


def resolve_runtime_handle_identifiers_from_identity(
    identity: SessionAcpIdentity | None,
) -> dict[str, str]:
    if not identity:
        return {}
    result: dict[str, str] = {}
    if identity.get("acpxSessionId"):
        result["backendSessionId"] = identity["acpxSessionId"]
    if identity.get("agentSessionId"):
        result["agentSessionId"] = identity["agentSessionId"]
    return result
