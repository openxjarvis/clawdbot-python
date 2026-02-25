"""Telegram forum topics support with config inheritance

Handles forum topic threading, session routing, and config inheritance for Telegram supergroups.
"""
from __future__ import annotations

import logging
from typing import Any, TypedDict

logger = logging.getLogger(__name__)

TELEGRAM_GENERAL_TOPIC_ID = 1


class TelegramThreadSpec(TypedDict, total=False):
    """Thread specification for Telegram forums/DMs"""
    id: int | None
    scope: str  # "dm" | "forum" | "none"


def resolve_telegram_forum_thread_id(
    is_forum: bool | None,
    message_thread_id: int | None,
) -> int | None:
    """
    Resolve the thread ID for Telegram forum topics.
    
    For non-forum groups, returns None even if message_thread_id is present
    (reply threads in regular groups should not create separate sessions).
    
    For forum groups, returns the topic ID (or General topic ID=1 if unspecified).
    
    Args:
        is_forum: Whether the chat is a forum
        message_thread_id: Thread ID from message
    
    Returns:
        Resolved thread ID or None
    """
    if not is_forum:
        return None
    
    if message_thread_id is None:
        return TELEGRAM_GENERAL_TOPIC_ID
    
    return message_thread_id


def resolve_telegram_thread_spec(
    is_group: bool,
    is_forum: bool | None,
    message_thread_id: int | None,
) -> TelegramThreadSpec:
    """
    Resolve thread specification from message context.
    
    Args:
        is_group: Whether chat is a group
        is_forum: Whether chat is a forum
        message_thread_id: Thread ID from message
    
    Returns:
        Thread specification with ID and scope
    """
    if is_group:
        thread_id = resolve_telegram_forum_thread_id(is_forum, message_thread_id)
        return {
            "id": thread_id,
            "scope": "forum" if is_forum else "none",
        }
    
    # DM
    if message_thread_id is None:
        return {"id": None, "scope": "dm"}
    
    return {
        "id": message_thread_id,
        "scope": "dm",
    }


def build_telegram_thread_params(thread: TelegramThreadSpec | None) -> dict[str, int]:
    """
    Build thread params for Telegram API calls (messages, media).
    
    IMPORTANT: Thread IDs behave differently based on chat type:
    - DMs (private chats): Include message_thread_id when present (DM topics)
    - Forum topics: Skip thread_id=1 (General topic), include others
    - Regular groups: Thread IDs are ignored by Telegram
    
    General forum topic (id=1) must be treated like a regular supergroup send:
    Telegram rejects sendMessage/sendMedia with message_thread_id=1 ("thread not found").
    
    Args:
        thread: Thread specification with ID and scope
    
    Returns:
        API params object (empty dict if thread_id should be omitted)
    """
    if not thread or thread.get("id") is None:
        return {}
    
    thread_id = thread["id"]
    if not isinstance(thread_id, int):
        return {}
    
    scope = thread.get("scope", "none")
    
    if scope == "dm":
        return {"message_thread_id": thread_id} if thread_id > 0 else {}
    
    # Telegram rejects message_thread_id=1 for General forum topic
    if thread_id == TELEGRAM_GENERAL_TOPIC_ID:
        return {}
    
    return {"message_thread_id": thread_id}


def build_typing_thread_params(message_thread_id: int | None) -> dict[str, int]:
    """
    Build thread params for typing indicators (send_chat_action).
    
    Empirically, General topic (id=1) needs message_thread_id for typing to appear.
    
    Args:
        message_thread_id: Thread ID for typing
    
    Returns:
        API params with message_thread_id if needed
    """
    if message_thread_id is None:
        return {}
    
    return {"message_thread_id": message_thread_id}


def build_telegram_group_peer_id(
    chat_id: int | str,
    message_thread_id: int | None,
) -> str:
    """
    Build peer ID for group sessions with optional topic suffix.
    
    Args:
        chat_id: Group chat ID
        message_thread_id: Optional topic ID
    
    Returns:
        Peer ID string (e.g., "-1001234567890:topic:99")
    """
    if message_thread_id is not None:
        return f"{chat_id}:topic:{message_thread_id}"
    return str(chat_id)


def build_telegram_group_from(
    chat_id: int | str,
    message_thread_id: int | None,
) -> str:
    """
    Build 'from' identifier for group sessions.
    
    Args:
        chat_id: Group chat ID
        message_thread_id: Optional topic ID
    
    Returns:
        From identifier (e.g., "telegram:group:-1001234567890:topic:99")
    """
    peer_id = build_telegram_group_peer_id(chat_id, message_thread_id)
    return f"telegram:group:{peer_id}"


def build_telegram_parent_peer(
    is_group: bool,
    resolved_thread_id: int | None,
    chat_id: int | str,
) -> dict[str, str] | None:
    """
    Build parentPeer for forum topic binding inheritance.
    
    When a message comes from a forum topic, the peer ID includes the topic suffix
    (e.g., "-1001234567890:topic:99"). To allow bindings configured for the base
    group ID to match, we provide the parent group as parentPeer so the routing
    layer can fall back to it when the exact peer doesn't match.
    
    Args:
        is_group: Whether chat is a group
        resolved_thread_id: Resolved thread ID
        chat_id: Group chat ID
    
    Returns:
        Parent peer dict or None
    """
    if not is_group or resolved_thread_id is None:
        return None
    
    return {"kind": "group", "id": str(chat_id)}


def resolve_telegram_group_config(
    config: dict[str, Any],
    chat_id: int | str,
    message_thread_id: int | None = None,
) -> dict[str, Any]:
    """
    Resolve group and topic config with inheritance.
    
    Topic config inherits from group config.
    
    Args:
        config: Full Telegram config
        chat_id: Group chat ID
        message_thread_id: Optional topic ID
    
    Returns:
        Dict with groupConfig and topicConfig
    """
    groups_config = config.get("groups", {})
    
    # Get group config
    group_config = groups_config.get(str(chat_id), {})
    
    # Get topic config (if in a forum topic)
    topic_config = None
    if message_thread_id is not None:
        topics = group_config.get("topics", {})
        topic_config = topics.get(str(message_thread_id), {})
    
    return {
        "group_config": group_config,
        "topic_config": topic_config,
    }


def merge_topic_config(
    group_config: dict[str, Any],
    topic_config: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Merge topic config with group config (topic overrides group).
    
    Args:
        group_config: Base group configuration
        topic_config: Topic-specific overrides
    
    Returns:
        Merged configuration
    """
    if not topic_config:
        return group_config.copy()
    
    merged = group_config.copy()
    merged.update(topic_config)
    
    return merged
