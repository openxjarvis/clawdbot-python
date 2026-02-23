"""ACP meta reading utilities — mirrors src/acp/meta.ts"""
from __future__ import annotations

from typing import Any


def read_string(meta: dict | None, keys: list[str]) -> str | None:
    if not meta:
        return None
    for key in keys:
        value = meta.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def read_bool(meta: dict | None, keys: list[str]) -> bool | None:
    if not meta:
        return None
    for key in keys:
        value = meta.get(key)
        if isinstance(value, bool):
            return value
    return None


def read_number(meta: dict | None, keys: list[str]) -> float | int | None:
    if not meta:
        return None
    for key in keys:
        value = meta.get(key)
        if isinstance(value, (int, float)) and value == value:  # NaN check
            return value
    return None
