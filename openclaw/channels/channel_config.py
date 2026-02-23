"""Channel config matching utilities — mirrors src/channels/channel-config.ts"""
from __future__ import annotations

import re
from typing import Any, Callable, Literal, TypeVar

T = TypeVar("T")

ChannelMatchSource = Literal["direct", "parent", "wildcard"]


class ChannelEntryMatch:
    def __init__(
        self,
        entry: Any = None,
        key: str | None = None,
        wildcard_entry: Any = None,
        wildcard_key: str | None = None,
        parent_entry: Any = None,
        parent_key: str | None = None,
        match_key: str | None = None,
        match_source: ChannelMatchSource | None = None,
    ) -> None:
        self.entry = entry
        self.key = key
        self.wildcard_entry = wildcard_entry
        self.wildcard_key = wildcard_key
        self.parent_entry = parent_entry
        self.parent_key = parent_key
        self.match_key = match_key
        self.match_source = match_source


def apply_channel_match_meta(result: dict, match: ChannelEntryMatch) -> dict:
    if match.match_key and match.match_source:
        result["matchKey"] = match.match_key
        result["matchSource"] = match.match_source
    return result


def normalize_channel_slug(value: str) -> str:
    s = value.strip().lower()
    s = s.lstrip("#")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s


def build_channel_key_candidates(*keys: str | None) -> list[str]:
    seen: set[str] = set()
    candidates: list[str] = []
    for key in keys:
        if not isinstance(key, str):
            continue
        trimmed = key.strip()
        if not trimmed or trimmed in seen:
            continue
        seen.add(trimmed)
        candidates.append(trimmed)
    return candidates


def resolve_channel_entry_match(
    *,
    entries: dict[str, T] | None = None,
    keys: list[str],
    wildcard_key: str | None = None,
) -> ChannelEntryMatch:
    d = entries or {}
    match = ChannelEntryMatch()

    for k in keys:
        if k in d:
            match.entry = d[k]
            match.key = k
            break

    if wildcard_key and wildcard_key in d:
        match.wildcard_entry = d[wildcard_key]
        match.wildcard_key = wildcard_key

    return match


def resolve_channel_entry_match_with_fallback(
    *,
    entries: dict[str, T] | None = None,
    keys: list[str],
    parent_keys: list[str] | None = None,
    wildcard_key: str | None = None,
    normalize_key: Callable[[str], str] | None = None,
) -> ChannelEntryMatch:
    direct = resolve_channel_entry_match(
        entries=entries,
        keys=keys,
        wildcard_key=wildcard_key,
    )
    if direct.entry is not None and direct.key is not None:
        direct.match_key = direct.key
        direct.match_source = "direct"
        return direct

    if normalize_key and entries:
        normalized_keys = [normalize_key(k) for k in keys]
        for nk in normalized_keys:
            if nk in entries:
                direct.entry = entries[nk]
                direct.key = nk
                direct.match_key = nk
                direct.match_source = "direct"
                return direct

    if parent_keys and entries:
        for pk in parent_keys:
            if pk in entries:
                direct.parent_entry = entries[pk]
                direct.parent_key = pk
                direct.match_key = pk
                direct.match_source = "parent"
                break

    if wildcard_key and entries and wildcard_key in entries:
        direct.wildcard_entry = entries[wildcard_key]
        direct.wildcard_key = wildcard_key
        if direct.entry is None:
            direct.match_key = wildcard_key
            direct.match_source = "wildcard"

    return direct
