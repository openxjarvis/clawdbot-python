"""System Presence — tracks connected instances and nodes.

Aligned with TS openclaw/src/infra/system-presence.ts.

Key alignment details:
- TTL_MS = 5 minutes (entries expire after 5 min without update)
- MAX_ENTRIES = 200 (LRU pruning by `ts` when exceeded)
- normalize_presence_key() — lowercased, stripped key normalization
- list_system_presence() — prunes expired entries and enforces max size
- update_system_presence() — merge + track changed fields, returns diff
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

# Mirrors TS constants
TTL_MS: int = 5 * 60 * 1000      # 5 minutes
MAX_ENTRIES: int = 200

# Global presence registry: key → SystemPresence
_presence_registry: dict[str, "SystemPresence"] = {}


@dataclass
class SystemPresence:
    """System presence beacon. Mirrors TS SystemPresence interface."""

    id: str
    type: Literal["gateway", "client", "node"] = "client"
    version: str = ""
    host: str = ""
    ip: str | None = None
    mode: str | None = None
    platform: str | None = None
    device_family: str | None = None
    model_identifier: str | None = None
    instance_id: str | None = None
    device_id: str | None = None
    reason: str | None = None
    roles: list[str] = field(default_factory=list)
    scopes: list[str] = field(default_factory=list)
    last_input_seconds: float | None = None
    text: str = ""
    since: str = ""          # ISO timestamp of first seen
    last_seen: str = ""      # ISO timestamp of last update
    ts: int = 0              # milliseconds since epoch (for LRU, matches TS)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dict for API response (camelCase to match TS output)."""
        return {
            "id": self.id,
            "type": self.type,
            "version": self.version,
            "host": self.host,
            "ip": self.ip,
            "mode": self.mode,
            "platform": self.platform,
            "deviceFamily": self.device_family,
            "modelIdentifier": self.model_identifier,
            "instanceId": self.instance_id,
            "deviceId": self.device_id,
            "reason": self.reason,
            "roles": self.roles,
            "scopes": self.scopes,
            "lastInputSeconds": self.last_input_seconds,
            "text": self.text,
            "since": self.since,
            "lastSeen": self.last_seen,
            "ts": self.ts,
            "metadata": self.metadata,
        }


@dataclass
class SystemPresenceUpdate:
    """Result of update_system_presence(). Mirrors TS SystemPresenceUpdate."""

    key: str
    previous: SystemPresence | None
    next: SystemPresence
    changes: dict[str, Any]
    changed_keys: list[str]


def normalize_presence_key(key: str | None) -> str | None:
    """Normalize a presence key to lowercase stripped form.

    Mirrors TS normalizePresenceKey().
    """
    if not key:
        return None
    trimmed = key.strip()
    return trimmed.lower() if trimmed else None


def _now_ms() -> int:
    return int(time.time() * 1000)


def _prune_registry() -> None:
    """Remove expired entries and enforce MAX_ENTRIES (LRU by ts).

    Mirrors TS listSystemPresence() pruning logic.
    """
    now = _now_ms()
    # Prune TTL-expired entries
    expired = [k for k, v in _presence_registry.items() if now - v.ts > TTL_MS]
    for k in expired:
        del _presence_registry[k]
    # Enforce max size (LRU: drop entries with smallest ts)
    if len(_presence_registry) > MAX_ENTRIES:
        sorted_keys = sorted(_presence_registry.keys(), key=lambda k: _presence_registry[k].ts)
        to_drop = len(_presence_registry) - MAX_ENTRIES
        for k in sorted_keys[:to_drop]:
            del _presence_registry[k]


def update_system_presence(
    key: str,
    payload: dict[str, Any],
) -> SystemPresenceUpdate:
    """Update or create a system presence entry.

    Mirrors TS updateSystemPresence() / upsertPresence().

    Args:
        key: Presence key (will be normalized).
        payload: Partial SystemPresence fields to merge.

    Returns:
        SystemPresenceUpdate with diff info.
    """
    normalized_key = normalize_presence_key(key) or key.lower()
    now_ms = _now_ms()
    now_iso = datetime.now(UTC).isoformat()

    existing = _presence_registry.get(normalized_key)
    had_existing = existing is not None
    if existing is None:
        existing = SystemPresence(
            id=normalized_key,
            since=now_iso,
            last_seen=now_iso,
            ts=now_ms,
        )

    track_fields = ["host", "ip", "version", "mode", "reason"]
    prev_values = {f: getattr(existing, f, None) for f in track_fields}

    # Merge fields
    for f_py, f_payload in [
        ("host", "host"), ("ip", "ip"), ("version", "version"),
        ("mode", "mode"), ("platform", "platform"),
        ("device_family", "deviceFamily"), ("model_identifier", "modelIdentifier"),
        ("instance_id", "instanceId"), ("device_id", "deviceId"),
        ("reason", "reason"), ("text", "text"),
        ("last_input_seconds", "lastInputSeconds"),
        ("type", "type"),
    ]:
        if f_payload in payload and payload[f_payload] is not None:
            setattr(existing, f_py, payload[f_payload])
    if "roles" in payload:
        existing.roles = list({*existing.roles, *payload["roles"]})
    if "scopes" in payload:
        existing.scopes = list({*existing.scopes, *payload["scopes"]})
    if "metadata" in payload:
        existing.metadata.update(payload["metadata"])

    existing.ts = now_ms
    existing.last_seen = now_iso
    _presence_registry[normalized_key] = existing

    changes: dict[str, Any] = {}
    changed_keys: list[str] = []
    for f in track_fields:
        prev = prev_values[f]
        curr = getattr(existing, f, None)
        if prev != curr:
            changes[f] = curr
            changed_keys.append(f)

    return SystemPresenceUpdate(
        key=normalized_key,
        previous=existing if had_existing else None,
        next=existing,
        changes=changes,
        changed_keys=changed_keys,
    )


def register_presence(presence: SystemPresence) -> None:
    """Register or update system presence (legacy API)."""
    presence.ts = _now_ms()
    presence.last_seen = datetime.now(UTC).isoformat()
    _presence_registry[presence.id] = presence


def update_presence(presence_id: str) -> None:
    """Update last_seen timestamp for a presence."""
    if presence_id in _presence_registry:
        now = datetime.now(UTC)
        _presence_registry[presence_id].last_seen = now.isoformat()
        _presence_registry[presence_id].ts = int(now.timestamp() * 1000)


def unregister_presence(presence_id: str) -> bool:
    """Unregister system presence."""
    if presence_id in _presence_registry:
        del _presence_registry[presence_id]
        return True
    return False


def list_system_presence() -> list[dict]:
    """List all system presences, pruning expired entries and enforcing max size.

    Mirrors TS listSystemPresence().
    """
    _prune_registry()
    sorted_entries = sorted(
        _presence_registry.values(), key=lambda p: p.ts, reverse=True
    )
    return [p.to_dict() for p in sorted_entries]


def get_presence(presence_id: str) -> SystemPresence | None:
    """Get specific presence by ID."""
    return _presence_registry.get(presence_id)


def get_raw_presence_entries() -> dict[str, SystemPresence]:
    """Return raw registry (for testing). Mirrors TS _entriesForTests()."""
    return _presence_registry


__all__ = [
    "TTL_MS",
    "MAX_ENTRIES",
    "SystemPresence",
    "SystemPresenceUpdate",
    "normalize_presence_key",
    "update_system_presence",
    "register_presence",
    "update_presence",
    "unregister_presence",
    "list_system_presence",
    "get_presence",
    "get_raw_presence_entries",
]
