"""
Config dot-notation path manipulation — matches openclaw/src/config/config-paths.ts
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

_FORBIDDEN_KEYS = frozenset({"__proto__", "prototype", "constructor"})

PathNode = Dict[str, Any]


def parse_config_path(raw: str) -> Dict[str, Any]:
    """
    Parse a dot-notation config path string.

    Returns:
        {"ok": True, "path": List[str]} on success
        {"ok": False, "error": str} on failure

    Matches TS parseConfigPath().
    """
    trimmed = (raw or "").strip()
    if not trimmed:
        return {"ok": False, "error": "empty path"}
    keys = trimmed.split(".")
    for key in keys:
        if not key:
            return {"ok": False, "error": f"empty segment in path: {raw!r}"}
        if key in _FORBIDDEN_KEYS:
            return {"ok": False, "error": f"forbidden key: {key!r}"}
    return {"ok": True, "path": keys}


def set_config_value_at_path(root: PathNode, path: List[str], value: Any) -> None:
    """
    Set a value at the given path inside root, creating intermediate dicts as needed.

    Matches TS setConfigValueAtPath().
    """
    if not path:
        return
    node = root
    for key in path[:-1]:
        if key not in node or not isinstance(node[key], dict):
            node[key] = {}
        node = node[key]
    node[path[-1]] = value


def unset_config_value_at_path(root: PathNode, path: List[str]) -> bool:
    """
    Remove the value at the given path from root.

    Cleans up empty parent dicts after deletion.

    Returns True if a value was removed.

    Matches TS unsetConfigValueAtPath().
    """
    if not path:
        return False

    def _remove(node: dict, remaining: List[str]) -> bool:
        key = remaining[0]
        if key not in node:
            return False
        if len(remaining) == 1:
            del node[key]
            return True
        child = node[key]
        if not isinstance(child, dict):
            return False
        removed = _remove(child, remaining[1:])
        # Clean up empty intermediate dicts
        if removed and not child:
            del node[key]
        return removed

    return _remove(root, path)


def get_config_value_at_path(root: Any, path: List[str]) -> Any:
    """
    Get the value at the given path inside root.

    Returns None if the path doesn't exist.

    Matches TS getConfigValueAtPath().
    """
    current = root
    for key in path:
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(key)
        else:
            current = getattr(current, key, None)
    return current


__all__ = [
    "PathNode",
    "parse_config_path",
    "set_config_value_at_path",
    "unset_config_value_at_path",
    "get_config_value_at_path",
]
