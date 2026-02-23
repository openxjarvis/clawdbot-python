"""Allowlist matching utilities — mirrors src/channels/allowlist-match.ts"""
from __future__ import annotations

from typing import Literal, TypeVar

AllowlistMatchSource = Literal[
    "wildcard", "id", "name", "tag", "username",
    "prefixed-id", "prefixed-user", "prefixed-name", "slug", "localpart",
]


class AllowlistMatch:
    def __init__(
        self,
        allowed: bool,
        match_key: str | None = None,
        match_source: str | None = None,
    ) -> None:
        self.allowed = allowed
        self.match_key = match_key
        self.match_source = match_source

    def to_dict(self) -> dict:
        d: dict = {"allowed": self.allowed}
        if self.match_key is not None:
            d["matchKey"] = self.match_key
        if self.match_source is not None:
            d["matchSource"] = self.match_source
        return d


def format_allowlist_match_meta(match: AllowlistMatch | dict | None) -> str:
    if match is None:
        return "matchKey=none matchSource=none"
    if isinstance(match, dict):
        key = match.get("matchKey") or match.get("match_key") or "none"
        source = match.get("matchSource") or match.get("match_source") or "none"
    else:
        key = match.match_key or "none"
        source = match.match_source or "none"
    return f"matchKey={key} matchSource={source}"


def resolve_allowlist_match_simple(
    *,
    allow_from: list[str | int],
    sender_id: str,
    sender_name: str | None = None,
) -> AllowlistMatch:
    normalized = [str(e).strip().lower() for e in allow_from if str(e).strip()]

    if not normalized:
        return AllowlistMatch(allowed=False)

    if "*" in normalized:
        return AllowlistMatch(allowed=True, match_key="*", match_source="wildcard")

    sid = sender_id.lower()
    if sid in normalized:
        return AllowlistMatch(allowed=True, match_key=sid, match_source="id")

    sname = (sender_name or "").lower()
    if sname and sname in normalized:
        return AllowlistMatch(allowed=True, match_key=sname, match_source="name")

    return AllowlistMatch(allowed=False)
