"""Input provenance tracking — matches openclaw/src/sessions/input-provenance.ts"""
from __future__ import annotations

from typing import Dict, Literal, Optional, Union

INPUT_PROVENANCE_KIND_VALUES = ("external_user", "inter_session", "internal_system")

InputProvenanceKind = Literal["external_user", "inter_session", "internal_system"]


class InputProvenance:
    """Tracks the origin of a user message."""

    __slots__ = ("kind", "source_session_key", "source_channel", "source_tool")

    def __init__(
        self,
        kind: InputProvenanceKind,
        source_session_key: Optional[str] = None,
        source_channel: Optional[str] = None,
        source_tool: Optional[str] = None,
    ) -> None:
        self.kind = kind
        self.source_session_key = source_session_key
        self.source_channel = source_channel
        self.source_tool = source_tool

    def to_dict(self) -> Dict[str, object]:
        d: Dict[str, object] = {"kind": self.kind}
        if self.source_session_key is not None:
            d["sourceSessionKey"] = self.source_session_key
        if self.source_channel is not None:
            d["sourceChannel"] = self.source_channel
        if self.source_tool is not None:
            d["sourceTool"] = self.source_tool
        return d


def _normalize_optional_string(value: object) -> Optional[str]:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed if trimmed else None


def _is_input_provenance_kind(value: object) -> bool:
    return isinstance(value, str) and value in INPUT_PROVENANCE_KIND_VALUES


def normalize_input_provenance(value: object) -> Optional[InputProvenance]:
    """
    Normalize and validate an input provenance value.

    Returns InputProvenance on success, None if invalid.

    Matches TS normalizeInputProvenance().
    """
    if not value or not isinstance(value, dict):
        return None
    kind = value.get("kind")
    if not _is_input_provenance_kind(kind):
        return None
    return InputProvenance(
        kind=kind,  # type: ignore[arg-type]
        source_session_key=_normalize_optional_string(value.get("sourceSessionKey")),
        source_channel=_normalize_optional_string(value.get("sourceChannel")),
        source_tool=_normalize_optional_string(value.get("sourceTool")),
    )


def apply_input_provenance_to_user_message(
    message: dict,
    input_provenance: Optional[InputProvenance],
) -> dict:
    """
    Apply input provenance to a user message dict.

    - No-op if provenance is None.
    - No-op if message role is not "user".
    - No-op if message already has provenance.

    Returns (possibly modified) message dict.

    Matches TS applyInputProvenanceToUserMessage().
    """
    if input_provenance is None:
        return message
    if message.get("role") != "user":
        return message
    existing = normalize_input_provenance(message.get("provenance"))
    if existing is not None:
        return message
    return {**message, "provenance": input_provenance.to_dict()}


def is_inter_session_input_provenance(value: object) -> bool:
    """Check if value represents an inter-session provenance. Matches TS."""
    prov = normalize_input_provenance(value if isinstance(value, dict) else None)
    return prov is not None and prov.kind == "inter_session"


def has_inter_session_user_provenance(message: Optional[dict]) -> bool:
    """
    Check if a message has inter-session provenance.

    Matches TS hasInterSessionUserProvenance().
    """
    if not message or message.get("role") != "user":
        return False
    return is_inter_session_input_provenance(message.get("provenance"))


__all__ = [
    "INPUT_PROVENANCE_KIND_VALUES",
    "InputProvenanceKind",
    "InputProvenance",
    "normalize_input_provenance",
    "apply_input_provenance_to_user_message",
    "is_inter_session_input_provenance",
    "has_inter_session_user_provenance",
]
