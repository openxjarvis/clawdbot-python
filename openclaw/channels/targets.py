"""Messaging target utilities — mirrors src/channels/targets.ts"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

MessagingTargetKind = Literal["user", "channel"]


@dataclass
class MessagingTarget:
    kind: MessagingTargetKind
    id: str
    raw: str
    normalized: str


def normalize_target_id(kind: MessagingTargetKind, id_: str) -> str:
    return f"{kind}:{id_}".lower()


def build_messaging_target(kind: MessagingTargetKind, id_: str, raw: str) -> MessagingTarget:
    return MessagingTarget(
        kind=kind,
        id=id_,
        raw=raw,
        normalized=normalize_target_id(kind, id_),
    )


def ensure_target_id(*, candidate: str, pattern: re.Pattern, error_message: str) -> str:
    if not pattern.match(candidate):
        raise ValueError(error_message)
    return candidate


def parse_target_mention(
    *,
    raw: str,
    mention_pattern: re.Pattern,
    kind: MessagingTargetKind,
) -> MessagingTarget | None:
    m = mention_pattern.match(raw)
    if not m or not m.group(1):
        return None
    return build_messaging_target(kind, m.group(1), raw)


def parse_target_prefix(
    *,
    raw: str,
    prefix: str,
    kind: MessagingTargetKind,
) -> MessagingTarget | None:
    stripped = raw.strip()
    if not stripped.lower().startswith(prefix.lower()):
        return None
    id_ = stripped[len(prefix):].strip()
    if not id_:
        return None
    return build_messaging_target(kind, id_, raw)


def parse_messaging_target(
    raw: str,
    *,
    default_kind: MessagingTargetKind = "user",
    ambiguous_message: str | None = None,
) -> MessagingTarget:
    """Parse a raw target string like #channel or @user or plain id."""
    stripped = raw.strip()
    if stripped.startswith("#"):
        return build_messaging_target("channel", stripped[1:], raw)
    if stripped.startswith("@"):
        return build_messaging_target("user", stripped[1:], raw)
    return build_messaging_target(default_kind, stripped, raw)
