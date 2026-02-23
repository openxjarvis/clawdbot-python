"""
In-memory runtime config overrides — matches openclaw/src/config/runtime-overrides.ts

Allows live patching of config values without writing to disk.
Applied at the end of load_config() pipeline via apply_config_overrides().
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Union

# Global in-memory override tree (mirrors TS _overrideTree module-level var)
_override_tree: Dict[str, Any] = {}


def get_config_overrides() -> Dict[str, Any]:
    """Return a shallow copy of the current override tree."""
    return dict(_override_tree)


def reset_config_overrides() -> None:
    """Clear all runtime config overrides."""
    global _override_tree
    _override_tree = {}


def _parse_config_path(raw: str):
    """
    Parse a dot-notation config path string into a list of keys.

    Returns {"ok": True, "path": [...]} or {"ok": False, "error": str}.

    Blocks dangerous prototype pollution keys.
    """
    trimmed = raw.strip()
    if not trimmed:
        return {"ok": False, "error": "empty path"}
    keys = trimmed.split(".")
    dangerous = {"__proto__", "prototype", "constructor"}
    for key in keys:
        if not key:
            return {"ok": False, "error": f"empty segment in path: {raw!r}"}
        if key in dangerous:
            return {"ok": False, "error": f"forbidden key: {key!r}"}
    return {"ok": True, "path": keys}


def _set_at_path(root: dict, path: List[str], value: Any) -> None:
    """Set value at dot-notation path in root dict, creating intermediate dicts."""
    node = root
    for key in path[:-1]:
        if key not in node or not isinstance(node[key], dict):
            node[key] = {}
        node = node[key]
    node[path[-1]] = value


def _unset_at_path(root: dict, path: List[str]) -> bool:
    """
    Unset (delete) value at path. Cleans up empty parent dicts.

    Returns True if something was removed.
    """
    if not path:
        return False

    def _unset(node: dict, remaining: List[str]) -> bool:
        key = remaining[0]
        if key not in node:
            return False
        if len(remaining) == 1:
            del node[key]
            return True
        child = node[key]
        if not isinstance(child, dict):
            return False
        removed = _unset(child, remaining[1:])
        if removed and not child:
            del node[key]
        return removed

    return _unset(root, path)


def set_config_override(path_raw: str, value: Any) -> Dict[str, Any]:
    """
    Set a runtime config override at the given dot-notation path.

    Returns {"ok": True} or {"ok": False, "error": str}.

    Matches TS setConfigOverride().
    """
    result = _parse_config_path(path_raw)
    if not result["ok"]:
        return {"ok": False, "error": result["error"]}
    _set_at_path(_override_tree, result["path"], value)
    return {"ok": True}


def unset_config_override(path_raw: str) -> Dict[str, Any]:
    """
    Remove a runtime config override at the given dot-notation path.

    Returns {"ok": True, "removed": bool} or {"ok": False, "error": str}.

    Matches TS unsetConfigOverride().
    """
    result = _parse_config_path(path_raw)
    if not result["ok"]:
        return {"ok": False, "error": result["error"]}
    removed = _unset_at_path(_override_tree, result["path"])
    return {"ok": True, "removed": removed}


def _deep_merge_overrides(base: Any, overrides: Any) -> Any:
    """Deep merge overrides onto base. Objects merge; primitives/arrays replace."""
    if not isinstance(overrides, dict) or not isinstance(base, dict):
        return copy.deepcopy(overrides)
    result = dict(base)
    for key, val in overrides.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge_overrides(result[key], val)
        else:
            result[key] = copy.deepcopy(val)
    return result


def apply_config_overrides(cfg: Any) -> Any:
    """
    Apply all in-memory runtime overrides to the config object.

    Returns the (potentially mutated / new) config.
    If no overrides are set, returns cfg unchanged.

    Called at the end of load_config() pipeline.

    Matches TS applyConfigOverrides().
    """
    if not _override_tree:
        return cfg

    if isinstance(cfg, dict):
        return _deep_merge_overrides(cfg, _override_tree)

    # For Pydantic/dataclass models convert to dict, merge, convert back
    cfg_dict: Optional[dict] = None
    if hasattr(cfg, "model_dump"):
        cfg_dict = cfg.model_dump()
    elif hasattr(cfg, "dict"):
        cfg_dict = cfg.dict()  # type: ignore[union-attr]
    elif hasattr(cfg, "__dict__"):
        cfg_dict = dict(cfg.__dict__)

    if cfg_dict is not None:
        merged = _deep_merge_overrides(cfg_dict, _override_tree)
        # Try to reconstruct the original type
        try:
            if hasattr(cfg, "model_validate"):
                return type(cfg).model_validate(merged)  # type: ignore[union-attr]
            if hasattr(cfg, "parse_obj"):
                return type(cfg).parse_obj(merged)  # type: ignore[union-attr]
        except Exception:
            pass
        return merged

    return cfg


__all__ = [
    "get_config_overrides",
    "reset_config_overrides",
    "set_config_override",
    "unset_config_override",
    "apply_config_overrides",
]
