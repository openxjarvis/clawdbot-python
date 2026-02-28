"""
Gateway protocol event frames.

Mirrors TypeScript openclaw/src/gateway/protocol/events.ts — typed event
envelope used for all server→client notifications over the WebSocket.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EventFrame:
    """
    Normalized event frame sent over the WebSocket channel.

    Fields mirror TS EventFrame:
      event   — dot-separated event name  (e.g. "agent.turn.start")
      payload — arbitrary JSON-serialisable data
      seq     — monotonically-increasing sequence number (0-based)
      id      — optional correlation / request ID
    """

    event: str
    payload: Any = None
    seq: int = 0
    id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialise to wire format (matches TS toJSON())."""
        d: dict[str, Any] = {"event": self.event, "seq": self.seq}
        if self.payload is not None:
            d["payload"] = self.payload
        if self.id is not None:
            d["id"] = self.id
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EventFrame":
        """Deserialise from wire format."""
        return cls(
            event=data["event"],
            payload=data.get("payload"),
            seq=data.get("seq", 0),
            id=data.get("id"),
        )


__all__ = ["EventFrame"]
