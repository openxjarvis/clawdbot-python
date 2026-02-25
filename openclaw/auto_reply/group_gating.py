"""Group message gating with mention patterns and activation modes.

Determines whether group messages should trigger auto-reply based on
mention patterns, activation modes, and group policy configuration.

Mirrors TypeScript openclaw/src/web/auto-reply/monitor/group-gating.ts.
"""
from __future__ import annotations

import logging
from typing import Any, TypedDict

from openclaw.auto_reply.group_activation import (
    parse_activation_command,
    resolve_group_activation_for,
)
from openclaw.auto_reply.group_history import (
    GroupHistoryEntry,
    record_pending_group_history_entry,
)
from openclaw.auto_reply.reply.mentions import (
    build_mention_regexes,
    matches_mention_with_explicit,
    ExplicitMentionSignal,
)
from openclaw.config.group_policy import resolve_channel_group_policy

logger = logging.getLogger(__name__)


class GroupGatingResult(TypedDict):
    """Result of group gating check."""
    shouldProcess: bool
    wasMentioned: bool | None


def _is_owner_sender(
    owner_list: list[str],
    sender_id: str | None,
    sender_e164: str | None,
) -> bool:
    """Check if sender is in owner list.
    
    Mirrors TS isOwnerSender().
    """
    if not owner_list:
        return False
    
    sender = sender_e164 or sender_id or ""
    if not sender:
        return False
    
    # Normalize E.164 format
    normalized = sender.strip().replace(" ", "").replace("-", "")
    if not normalized.startswith("+"):
        normalized = f"+{normalized}"
    
    return normalized in owner_list


def _has_control_command(text: str) -> bool:
    """Check if text contains a control command.
    
    Mirrors TS hasControlCommand() concept.
    Simple check for common control commands.
    """
    if not text:
        return False
    
    text_lower = text.strip().lower()
    control_commands = [
        "/new", "/reset", "/clear", "/compact",
        "/verbose", "/think", "/model", "/status",
    ]
    
    return any(text_lower.startswith(cmd) for cmd in control_commands)


def apply_group_gating(
    cfg: dict[str, Any],
    msg: dict[str, Any],
    conversation_id: str,
    group_history_key: str,
    agent_id: str,
    session_key: str,
    channel: str,
    account_id: str | None = None,
    group_id: str | None = None,
    group_histories: dict[str, list[GroupHistoryEntry]] | None = None,
    group_history_limit: int = 50,
    owner_list: list[str] | None = None,
    session_state: dict[str, Any] | None = None,
) -> GroupGatingResult:
    """Apply group gating logic to determine if message should be processed.
    
    Mirrors TS applyGroupGating() from src/web/auto-reply/monitor/group-gating.ts.
    
    Args:
        cfg: OpenClaw configuration
        msg: Inbound message dict
        conversation_id: Conversation/group ID
        group_history_key: Key for group history storage
        agent_id: Agent ID
        session_key: Session key
        channel: Channel ID (e.g., "telegram", "whatsapp")
        account_id: Optional account ID
        group_histories: Optional group history map
        group_history_limit: Maximum history entries to keep
        owner_list: List of owner identifiers
        session_state: Optional session state dict
        
    Returns:
        GroupGatingResult with shouldProcess and wasMentioned flags
    """
    # DM messages always process (mirrors TS behaviour)
    chat_type = msg.get("chatType") or msg.get("chat_type") or ""
    if chat_type.lower() == "dm":
        return GroupGatingResult(shouldProcess=True, wasMentioned=True)

    # Check group policy allowlist
    group_id = group_id or msg.get("group_id") or conversation_id
    group_policy = resolve_channel_group_policy(
        cfg=cfg,
        channel=channel,
        group_id=group_id,
        account_id=account_id,
    )
    
    if group_policy["allowlistEnabled"] and not group_policy["allowed"]:
        logger.debug(f"Skipping group message {conversation_id} (not in allowlist)")
        return GroupGatingResult(shouldProcess=False, wasMentioned=None)
    
    # Build mention regexes
    mention_regexes = build_mention_regexes(cfg, agent_id)
    
    # Parse activation command
    body = msg.get("body", msg.get("text", ""))
    activation_command = parse_activation_command(body)
    
    # Check if sender is owner
    sender_id = msg.get("sender_id", msg.get("senderId"))
    sender_e164 = msg.get("sender_e164", msg.get("senderE164"))
    owner = _is_owner_sender(owner_list or [], sender_id, sender_e164)
    
    # Check if should bypass mention (owner + control command)
    should_bypass_mention = owner and _has_control_command(body)
    
    # If owner sends /activation, allow processing
    if activation_command["hasCommand"] and owner:
        return GroupGatingResult(shouldProcess=True, wasMentioned=True)

    # If non-owner tries to use /activation, ignore and record history
    if activation_command["hasCommand"] and not owner:
        logger.debug(f"Ignoring /activation from non-owner in group {conversation_id}")
        if group_histories is not None:
            entry = GroupHistoryEntry(
                sender=msg.get("sender_name", "Unknown"),
                body=body,
                timestamp=msg.get("timestamp"),
                id=msg.get("id", msg.get("message_id")),
            )
            record_pending_group_history_entry(
                session_key=group_history_key,
                entry=entry,
                limit=group_history_limit,
                history_map=group_histories,
            )
        return GroupGatingResult(shouldProcess=False, wasMentioned=None)
    
    # Check explicit mention signal from channel
    explicit_mention: ExplicitMentionSignal | None = None
    if "was_mentioned" in msg or "wasMentioned" in msg:
        was_mentioned = msg.get("was_mentioned", msg.get("wasMentioned", False))
        explicit_mention = ExplicitMentionSignal(
            hasAnyMention=True,
            isExplicitlyMentioned=was_mentioned,
            canResolveExplicit=True,
        )
    
    # Check if mentioned
    was_mentioned = matches_mention_with_explicit(
        text=body,
        mention_regexes=mention_regexes,
        explicit=explicit_mention,
    )
    
    # Resolve activation mode
    activation = resolve_group_activation_for(
        cfg=cfg,
        agent_id=agent_id,
        session_key=session_key,
        channel=channel,
        account_id=account_id,
        group_id=group_id,
        session_state=session_state,
    )
    
    require_mention = activation != "always"
    
    # Check implicit mention (reply to bot's message)
    implicit_mention = False
    reply_to_sender = msg.get("reply_to_sender", msg.get("replyToSender"))
    self_id = msg.get("self_id", msg.get("selfE164"))
    if reply_to_sender and self_id:
        implicit_mention = reply_to_sender == self_id
    
    # Determine if should process
    effective_was_mentioned = was_mentioned or implicit_mention or should_bypass_mention
    should_skip = require_mention and not effective_was_mentioned
    
    if not should_bypass_mention and should_skip:
        logger.debug(
            f"Group message stored for context (no mention detected) in {conversation_id}: {body[:50]}..."
        )
        if group_histories is not None:
            entry = GroupHistoryEntry(
                sender=msg.get("sender_name", "Unknown"),
                body=body,
                timestamp=msg.get("timestamp"),
                id=msg.get("id", msg.get("message_id")),
            )
            record_pending_group_history_entry(
                session_key=group_history_key,
                entry=entry,
                limit=group_history_limit,
                history_map=group_histories,
            )
        return GroupGatingResult(shouldProcess=False, wasMentioned=effective_was_mentioned)
    
    return GroupGatingResult(shouldProcess=True, wasMentioned=effective_was_mentioned)


__all__ = [
    "GroupGatingResult",
    "apply_group_gating",
]
