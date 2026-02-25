"""Pairing type definitions"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable


@dataclass
class PairingRequest:
    """Pending pairing request.

    JSON serialization uses camelCase keys (matching TypeScript pairing-store.ts)
    to ensure on-disk compatibility between TS and Python gateway instances.
    """

    id: str
    code: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_seen_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    meta: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict using camelCase keys (mirrors TS)."""
        d: dict[str, Any] = {
            "id": self.id,
            "code": self.code,
            "createdAt": self.created_at,
            "lastSeenAt": self.last_seen_at,
        }
        if self.meta:
            d["meta"] = self.meta
        return d

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PairingRequest":
        """Deserialize from dict — accepts both camelCase (TS) and snake_case (legacy Python)."""
        now = datetime.now(timezone.utc).isoformat()
        created = (
            data.get("createdAt")
            or data.get("created_at")
            or now
        )
        last_seen = (
            data.get("lastSeenAt")
            or data.get("last_seen_at")
            or created
        )
        return cls(
            id=data["id"],
            code=data["code"],
            created_at=created,
            last_seen_at=last_seen,
            meta=data.get("meta") or {},
        )


@dataclass
class ChannelPairingAdapter:
    """Channel-specific pairing adapter"""
    
    id_label: str  # e.g., "userId", "phone number"
    normalize_allow_entry: Callable[[str], str] | None = None
    notify_approval: Callable[[str, str, dict[str, Any]], Any] | None = None
    
    def normalize_entry(self, entry: str) -> str:
        """Normalize allowlist entry"""
        if self.normalize_allow_entry:
            return self.normalize_allow_entry(entry)
        return entry
    
    async def send_approval_notification(
        self,
        channel_id: str,
        user_id: str,
        meta: dict[str, Any]
    ) -> None:
        """Send approval notification"""
        if self.notify_approval:
            await self.notify_approval(channel_id, user_id, meta)
