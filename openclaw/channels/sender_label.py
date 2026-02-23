"""Sender label resolution — mirrors src/channels/sender-label.ts"""
from __future__ import annotations


def _normalize(value: str | None) -> str | None:
    trimmed = (value or "").strip()
    return trimmed if trimmed else None


def resolve_sender_label(
    *,
    name: str | None = None,
    username: str | None = None,
    tag: str | None = None,
    e164: str | None = None,
    id: str | None = None,
) -> str | None:
    n = _normalize(name)
    u = _normalize(username)
    t = _normalize(tag)
    e = _normalize(e164)
    i = _normalize(id)

    display = n or u or t or ""
    id_part = e or i or ""

    if display and id_part and display != id_part:
        return f"{display} ({id_part})"
    return display or id_part or None


def list_sender_label_candidates(
    *,
    name: str | None = None,
    username: str | None = None,
    tag: str | None = None,
    e164: str | None = None,
    id: str | None = None,
) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    def add(v: str | None) -> None:
        n = _normalize(v)
        if n and n not in seen:
            seen.add(n)
            candidates.append(n)

    add(name)
    add(username)
    add(tag)
    add(e164)
    add(id)

    resolved = resolve_sender_label(name=name, username=username, tag=tag, e164=e164, id=id)
    add(resolved)
    return candidates
