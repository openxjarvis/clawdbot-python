"""Access control policy resolution for Feishu channel.

Mirrors TypeScript: extensions/feishu/src/policy.ts
Handles: dmPolicy, groupPolicy, allowFrom, groupAllowFrom, per-group overrides.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .config import FeishuGroupConfig, ResolvedFeishuAccount

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ID normalization helpers
# ---------------------------------------------------------------------------

def _normalize_id(raw: str) -> str:
    """Strip feishu: prefix and lowercase. Mirrors TS normalizeFeishuId()."""
    s = raw.strip().lower()
    if s.startswith("feishu:"):
        s = s[len("feishu:"):]
    return s


def _normalize_list(ids: list[str]) -> list[str]:
    return [_normalize_id(e) for e in ids if e.strip()]


# ---------------------------------------------------------------------------
# Allowlist resolution
# ---------------------------------------------------------------------------

@dataclass
class AllowlistResult:
    allowed: bool
    reason: str = ""


def resolve_feishu_allowlist_match(
    *,
    allow_from: list[str],
    sender_id: str,
    sender_ids: list[str] | None = None,
    sender_name: str | None = None,
) -> AllowlistResult:
    """
    Check whether a sender is in the allowlist.

    - IDs are normalized (strips 'feishu:' prefix, lowercased).
    - '*' is wildcard.
    - Display names are NOT used for access control (only IDs).
    - Both open_id and user_id are checked.

    Mirrors TS resolveFeishuAllowlistMatch().
    """
    normalized = _normalize_list(allow_from)
    if not normalized:
        return AllowlistResult(allowed=False, reason="allowlist empty")

    if "*" in normalized:
        return AllowlistResult(allowed=True, reason="wildcard")

    all_ids = [_normalize_id(sender_id)]
    if sender_ids:
        all_ids.extend(_normalize_id(i) for i in sender_ids if i.strip())

    for sid in all_ids:
        if sid and sid in normalized:
            return AllowlistResult(allowed=True, reason=f"id:{sid}")

    return AllowlistResult(allowed=False, reason="not in allowlist")


# ---------------------------------------------------------------------------
# DM policy resolution
# ---------------------------------------------------------------------------

def resolve_feishu_dm_policy(
    account: ResolvedFeishuAccount,
    sender_id: str,
    *,
    sender_ids: list[str] | None = None,
    pairing_allow_from: list[str] | None = None,
) -> tuple[bool, str]:
    """
    Determine whether a DM sender is allowed.

    Returns (allowed, reason).

    Mirrors TS dm policy resolution in bot.ts.
    """
    policy = account.dm_policy

    if policy == "open":
        return True, "dm_policy=open"

    # Combine config allowFrom + pairing store
    allow_from = list(account.allow_from)
    if pairing_allow_from:
        allow_from.extend(pairing_allow_from)

    match = resolve_feishu_allowlist_match(
        allow_from=allow_from,
        sender_id=sender_id,
        sender_ids=sender_ids,
    )
    if match.allowed:
        return True, f"dm_policy={policy} allow:{match.reason}"

    return False, f"dm_policy={policy} blocked"


# ---------------------------------------------------------------------------
# Group policy resolution
# ---------------------------------------------------------------------------

def is_feishu_group_allowed(
    account: ResolvedFeishuAccount,
    chat_id: str,
) -> bool:
    """
    Check if a group chat is allowed.

    groupPolicy:
      "open"      → all groups allowed
      "allowlist" → only groups in groupAllowFrom
      "disabled"  → no groups

    Mirrors TS isFeishuGroupAllowed().
    """
    policy = account.group_policy
    if policy == "disabled":
        return False
    if policy == "open":
        return True
    # allowlist
    normalized = _normalize_list(account.group_allow_from)
    if "*" in normalized:
        return True
    return _normalize_id(chat_id) in normalized


def resolve_feishu_group_sender_allowed(
    account: ResolvedFeishuAccount,
    chat_id: str,
    sender_id: str,
    *,
    sender_ids: list[str] | None = None,
) -> bool:
    """
    Check if a sender is allowed in the given group (groupSenderAllowFrom + per-group allowFrom).

    Mirrors TS group sender allowlist resolution.
    """
    group_cfg = account.groups.get(chat_id) or account.groups.get(_normalize_id(chat_id))

    # Per-group allowFrom overrides global groupSenderAllowFrom
    if group_cfg and group_cfg.allow_from:
        match = resolve_feishu_allowlist_match(
            allow_from=group_cfg.allow_from,
            sender_id=sender_id,
            sender_ids=sender_ids,
        )
        return match.allowed

    if not account.group_sender_allow_from:
        return True  # No sender filter → all senders allowed

    match = resolve_feishu_allowlist_match(
        allow_from=account.group_sender_allow_from,
        sender_id=sender_id,
        sender_ids=sender_ids,
    )
    return match.allowed


# ---------------------------------------------------------------------------
# Group config resolution (with per-group overrides)
# ---------------------------------------------------------------------------

def resolve_feishu_group_config(
    account: ResolvedFeishuAccount,
    chat_id: str,
) -> dict[str, Any]:
    """
    Return the effective group config for chat_id, merging top-level + per-group overrides.

    Mirrors TS resolveFeishuGroupConfig().
    """
    group_cfg = account.groups.get(chat_id) or account.groups.get(_normalize_id(chat_id))

    effective: dict[str, Any] = {
        "require_mention": account.require_mention,
        "group_session_scope": account.group_session_scope,
        "topic_session_mode": account.topic_session_mode,
        "reply_in_thread": account.reply_in_thread,
        "enabled": True,
        "system_prompt": None,
        "tools": None,
        "skills": [],
    }

    if group_cfg:
        if group_cfg.require_mention is not None:
            effective["require_mention"] = group_cfg.require_mention
        if group_cfg.group_session_scope is not None:
            effective["group_session_scope"] = group_cfg.group_session_scope
        if group_cfg.topic_session_mode is not None:
            effective["topic_session_mode"] = group_cfg.topic_session_mode
        if group_cfg.reply_in_thread is not None:
            effective["reply_in_thread"] = group_cfg.reply_in_thread
        if group_cfg.enabled is not None:
            effective["enabled"] = group_cfg.enabled
        if group_cfg.system_prompt is not None:
            effective["system_prompt"] = group_cfg.system_prompt
        if group_cfg.tools is not None:
            effective["tools"] = group_cfg.tools
        if group_cfg.skills:
            effective["skills"] = group_cfg.skills

    return effective


# ---------------------------------------------------------------------------
# Reply policy
# ---------------------------------------------------------------------------

def resolve_feishu_reply_policy(
    account: ResolvedFeishuAccount,
    chat_id: str,
    message_id: str,
    *,
    is_group: bool,
    in_thread: bool = False,
) -> dict[str, Any]:
    """
    Resolve how the bot should reply (inline vs thread).

    Mirrors TS resolveFeishuReplyPolicy().
    """
    cfg = resolve_feishu_group_config(account, chat_id) if is_group else {}
    reply_in_thread = cfg.get("reply_in_thread", account.reply_in_thread) == "enabled"

    return {
        "reply_to_message_id": message_id,
        "reply_in_thread": reply_in_thread,
    }
