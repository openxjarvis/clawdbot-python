"""Session verbose-level overrides — matches openclaw/src/sessions/level-overrides.ts"""
from __future__ import annotations

from typing import Literal, Optional, Union

VerboseLevel = Literal["on", "off"]


def normalize_verbose_level(raw: object) -> Optional[VerboseLevel]:
    """Normalize verbose level string to 'on' | 'off' | None."""
    if not isinstance(raw, str):
        return None
    v = raw.strip().lower()
    if v == "on":
        return "on"
    if v == "off":
        return "off"
    return None


def parse_verbose_override(
    raw: object,
) -> Union[
    dict,  # {"ok": True, "value": VerboseLevel | None | None_type}
    dict,  # {"ok": False, "error": str}
]:
    """
    Parse verbose override value.

    Returns:
        {"ok": True, "value": "on" | "off" | None} on success
        {"ok": False, "error": str} on invalid input

    Matches TS parseVerboseOverride().
    """
    if raw is None:
        return {"ok": True, "value": None}
    if raw is ...:  # undefined sentinel
        return {"ok": True, "value": None}
    if not isinstance(raw, str):
        return {"ok": False, "error": 'invalid verboseLevel (use "on"|"off")'}
    normalized = normalize_verbose_level(raw)
    if not normalized:
        return {"ok": False, "error": 'invalid verboseLevel (use "on"|"off")'}
    return {"ok": True, "value": normalized}


def apply_verbose_override(entry: object, level: Optional[VerboseLevel]) -> None:
    """
    Apply verbose level override to a session entry dict or object.

    - level=None (undefined): no-op
    - level=None (null sentinel via explicit None + special call): delete verboseLevel
    - level="on"/"off": set verboseLevel

    Matches TS applyVerboseOverride(entry, level).

    Note: In Python we use a sentinel to distinguish "no-op (undefined)" from
    "clear (null)". Pass VERBOSE_LEVEL_CLEAR to delete the field.
    """
    if level is _UNDEFINED:
        return
    if level is None:
        # Clear the field
        if isinstance(entry, dict):
            entry.pop("verboseLevel", None)
        else:
            try:
                delattr(entry, "verboseLevel")
            except AttributeError:
                pass
        return
    if isinstance(entry, dict):
        entry["verboseLevel"] = level
    else:
        entry.verboseLevel = level  # type: ignore[union-attr]


# Sentinel to represent TypeScript undefined (distinct from Python None which maps to null)
_UNDEFINED = object()
VERBOSE_LEVEL_CLEAR = None  # pass as level to clear verboseLevel from entry


__all__ = [
    "VerboseLevel",
    "normalize_verbose_level",
    "parse_verbose_override",
    "apply_verbose_override",
    "VERBOSE_LEVEL_CLEAR",
]
