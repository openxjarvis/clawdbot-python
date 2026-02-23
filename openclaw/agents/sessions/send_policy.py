"""Session send policy — matches openclaw/src/sessions/send-policy.ts"""
from __future__ import annotations

from typing import Literal, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    pass

SessionSendPolicyDecision = Literal["allow", "deny"]


def normalize_send_policy(raw: Optional[str]) -> Optional[SessionSendPolicyDecision]:
    """Normalize send policy string to 'allow' | 'deny' | None."""
    value = (raw or "").strip().lower()
    if value == "allow":
        return "allow"
    if value == "deny":
        return "deny"
    return None


def _normalize_match_value(raw: Optional[str]) -> Optional[str]:
    value = (raw or "").strip().lower()
    return value if value else None


def _strip_agent_session_key_prefix(key: Optional[str]) -> Optional[str]:
    if not key:
        return None
    parts = [p for p in key.split(":") if p]
    if len(parts) >= 3 and parts[0] == "agent":
        return ":".join(parts[2:])
    return key


def _derive_channel_from_key(key: Optional[str]) -> Optional[str]:
    normalized_key = _strip_agent_session_key_prefix(key)
    if not normalized_key:
        return None
    parts = [p for p in normalized_key.split(":") if p]
    if len(parts) >= 3 and (parts[1] == "group" or parts[1] == "channel"):
        return _normalize_match_value(parts[0])
    return None


def _derive_chat_type_from_key(key: Optional[str]) -> Optional[str]:
    normalized_key = _strip_agent_session_key_prefix(key)
    if not normalized_key:
        return None
    if ":group:" in normalized_key:
        return "group"
    if ":channel:" in normalized_key:
        return "channel"
    return None


def _normalize_chat_type(value: Optional[str]) -> Optional[str]:
    """Normalize chat type to 'direct' | 'group' | 'channel' | None."""
    v = (value or "").strip().lower()
    if v in ("direct", "dm"):
        return "direct"
    if v == "group":
        return "group"
    if v == "channel":
        return "channel"
    return None


def resolve_send_policy(
    cfg: object,
    entry: Optional[object] = None,
    session_key: Optional[str] = None,
    channel: Optional[str] = None,
    chat_type: Optional[str] = None,
) -> SessionSendPolicyDecision:
    """
    Resolve send policy decision for a session.

    Priority:
    1. Entry-level sendPolicy override
    2. Config-level rules (channel / chatType / keyPrefix / rawKeyPrefix)
    3. Config default
    4. Fallback: "allow"

    Matches TS resolveSendPolicy().
    """
    # 1. Entry override
    entry_send_policy = getattr(entry, "sendPolicy", None) if entry else None
    override = normalize_send_policy(entry_send_policy)
    if override:
        return override

    # 2. Resolve config policy section
    policy = None
    if hasattr(cfg, "session") and cfg.session:  # type: ignore[union-attr]
        policy = getattr(cfg.session, "sendPolicy", None)  # type: ignore[union-attr]
    elif isinstance(cfg, dict):
        session = cfg.get("session", {}) or {}
        policy = session.get("sendPolicy") if isinstance(session, dict) else None

    if not policy:
        return "allow"

    # Build context values
    entry_channel = getattr(entry, "channel", None) if entry else None
    entry_last_channel = getattr(entry, "lastChannel", None) if entry else None
    entry_chat_type = getattr(entry, "chatType", None) if entry else None

    resolved_channel = (
        _normalize_match_value(channel)
        or _normalize_match_value(entry_channel)
        or _normalize_match_value(entry_last_channel)
        or _derive_channel_from_key(session_key)
    )
    resolved_chat_type = (
        _normalize_chat_type(chat_type or entry_chat_type)
        or _normalize_chat_type(_derive_chat_type_from_key(session_key))
    )

    raw_session_key = session_key or ""
    stripped_session_key = _strip_agent_session_key_prefix(raw_session_key) or ""
    raw_session_key_norm = raw_session_key.lower()
    stripped_session_key_norm = stripped_session_key.lower()

    # Resolve rules list
    rules = getattr(policy, "rules", None) if not isinstance(policy, dict) else policy.get("rules")
    policy_default = getattr(policy, "default", None) if not isinstance(policy, dict) else policy.get("default")

    allowed_match = False
    for rule in (rules or []):
        if not rule:
            continue
        action_raw = getattr(rule, "action", None) if not isinstance(rule, dict) else rule.get("action")
        action = normalize_send_policy(action_raw) or "allow"

        match = getattr(rule, "match", None) if not isinstance(rule, dict) else rule.get("match")
        if match is None:
            match = {}

        match_channel = _normalize_match_value(getattr(match, "channel", None) if not isinstance(match, dict) else match.get("channel"))
        match_chat_type = _normalize_chat_type(getattr(match, "chatType", None) if not isinstance(match, dict) else match.get("chatType"))
        match_prefix = _normalize_match_value(getattr(match, "keyPrefix", None) if not isinstance(match, dict) else match.get("keyPrefix"))
        match_raw_prefix = _normalize_match_value(getattr(match, "rawKeyPrefix", None) if not isinstance(match, dict) else match.get("rawKeyPrefix"))

        if match_channel and match_channel != resolved_channel:
            continue
        if match_chat_type and match_chat_type != resolved_chat_type:
            continue
        if match_raw_prefix and not raw_session_key_norm.startswith(match_raw_prefix):
            continue
        if match_prefix and not raw_session_key_norm.startswith(match_prefix) and not stripped_session_key_norm.startswith(match_prefix):
            continue

        if action == "deny":
            return "deny"
        allowed_match = True

    if allowed_match:
        return "allow"

    fallback = normalize_send_policy(policy_default)
    return fallback or "allow"


__all__ = [
    "SessionSendPolicyDecision",
    "normalize_send_policy",
    "resolve_send_policy",
]
