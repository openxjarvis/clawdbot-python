"""Session model overrides — matches openclaw/src/sessions/model-overrides.ts"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal, Optional


@dataclass
class ModelOverrideSelection:
    """Model selection for override."""
    provider: str
    model: str
    is_default: bool = False


def apply_model_override_to_session_entry(
    entry: object,
    selection: ModelOverrideSelection,
    profile_override: Optional[str] = None,
    profile_override_source: Literal["auto", "user"] = "user",
) -> dict:
    """
    Apply model override to a session entry (dict or object with attributes).

    - selection.is_default=True: clears providerOverride/modelOverride
    - selection.is_default=False: sets providerOverride/modelOverride
    - profile_override: sets authProfileOverride + authProfileOverrideSource;
      clears authProfileOverrideCompactionCount.
    - No profile_override: clears all authProfile* fields.

    Returns {"updated": bool}.

    Matches TS applyModelOverrideToSessionEntry().
    """
    updated = False

    def _get(key: str, default=None):
        if isinstance(entry, dict):
            return entry.get(key, default)
        return getattr(entry, key, default)

    def _set(key: str, value) -> None:
        nonlocal updated
        if isinstance(entry, dict):
            entry[key] = value  # type: ignore[index]
        else:
            setattr(entry, key, value)
        updated = True

    def _del(key: str) -> None:
        nonlocal updated
        if isinstance(entry, dict):
            if key in entry:  # type: ignore[operator]
                del entry[key]  # type: ignore[attr-defined]
                updated = True
        else:
            if hasattr(entry, key):
                try:
                    delattr(entry, key)
                    updated = True
                except AttributeError:
                    pass

    if selection.is_default:
        if _get("providerOverride") is not None:
            _del("providerOverride")
        if _get("modelOverride") is not None:
            _del("modelOverride")
    else:
        if _get("providerOverride") != selection.provider:
            _set("providerOverride", selection.provider)
        if _get("modelOverride") != selection.model:
            _set("modelOverride", selection.model)

    if profile_override:
        if _get("authProfileOverride") != profile_override:
            _set("authProfileOverride", profile_override)
        if _get("authProfileOverrideSource") != profile_override_source:
            _set("authProfileOverrideSource", profile_override_source)
        if _get("authProfileOverrideCompactionCount") is not None:
            _del("authProfileOverrideCompactionCount")
    else:
        if _get("authProfileOverride"):
            _del("authProfileOverride")
        if _get("authProfileOverrideSource"):
            _del("authProfileOverrideSource")
        if _get("authProfileOverrideCompactionCount") is not None:
            _del("authProfileOverrideCompactionCount")

    if updated:
        now_ms = int(time.time() * 1000)
        _set("updatedAt", now_ms)

    return {"updated": updated}


__all__ = [
    "ModelOverrideSelection",
    "apply_model_override_to_session_entry",
]
