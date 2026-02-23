"""Allowlist resolution utilities — mirrors src/channels/allowlists/resolve-utils.ts"""
from __future__ import annotations

from typing import Any, Callable, Protocol, TypeVar


class AllowlistUserResolutionLike(Protocol):
    input: str
    resolved: bool
    id: str | None


def merge_allowlist(
    *,
    existing: list[str | int] | None = None,
    additions: list[str],
) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []

    def push(value: str) -> None:
        normalized = value.strip()
        if not normalized:
            return
        key = normalized.lower()
        if key in seen:
            return
        seen.add(key)
        merged.append(normalized)

    for entry in (existing or []):
        push(str(entry))
    for entry in additions:
        push(entry)

    return merged


T = TypeVar("T")


def build_allowlist_resolution_summary(
    resolved_users: list[Any],
    *,
    format_resolved: Callable[[Any], str] | None = None,
) -> dict:
    def _resolved_ok(entry: Any) -> bool:
        return bool(getattr(entry, "resolved", False) and getattr(entry, "id", None))

    def _default_fmt(entry: Any) -> str:
        return f"{entry.input}→{entry.id}"

    fmt = format_resolved or _default_fmt
    resolved_map = {e.input: e for e in resolved_users}
    mapping = [fmt(e) for e in resolved_users if _resolved_ok(e)]
    additions = [e.id for e in resolved_users if _resolved_ok(e) and e.id]
    unresolved = [e.input for e in resolved_users if not _resolved_ok(e)]
    return {
        "resolvedMap": resolved_map,
        "mapping": mapping,
        "unresolved": unresolved,
        "additions": additions,
    }


def resolve_allowlist_id_additions(
    *,
    existing: list[str | int],
    resolved_map: dict[str, Any],
) -> list[str]:
    additions: list[str] = []
    for entry in existing:
        trimmed = str(entry).strip()
        resolved = resolved_map.get(trimmed)
        if resolved and getattr(resolved, "resolved", False) and getattr(resolved, "id", None):
            additions.append(resolved.id)
    return additions


def patch_allowlist_users_in_config_entries(
    *,
    entries: dict[str, Any],
    resolved_map: dict[str, Any],
) -> dict[str, Any]:
    next_entries = dict(entries)
    for entry_key, entry_config in entries.items():
        if not isinstance(entry_config, dict):
            continue
        users = entry_config.get("users")
        if not isinstance(users, list) or not users:
            continue
        additions = resolve_allowlist_id_additions(existing=users, resolved_map=resolved_map)
        next_entries[entry_key] = {
            **entry_config,
            "users": merge_allowlist(existing=users, additions=additions),
        }
    return next_entries


def add_allowlist_user_entries_from_config_entry(
    target: set[str],
    entry: Any,
) -> None:
    if not isinstance(entry, dict):
        return
    users = entry.get("users")
    if not isinstance(users, list):
        return
    for value in users:
        trimmed = str(value).strip()
        if trimmed and trimmed != "*":
            target.add(trimmed)


def summarize_mapping(
    label: str,
    mapping: list[str],
    unresolved: list[str],
    log: Callable[[str], None],
) -> None:
    lines: list[str] = []
    if mapping:
        sample = mapping[:6]
        suffix = f" (+{len(mapping) - len(sample)})" if len(mapping) > len(sample) else ""
        lines.append(f"{label} resolved: {', '.join(sample)}{suffix}")
    if unresolved:
        sample = unresolved[:6]
        suffix = f" (+{len(unresolved) - len(sample)})" if len(unresolved) > len(sample) else ""
        lines.append(f"{label} unresolved: {', '.join(sample)}{suffix}")
    if lines:
        log("\n".join(lines))
