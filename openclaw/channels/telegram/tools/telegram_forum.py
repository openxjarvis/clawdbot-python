"""Telegram forum/supergroup topic agent tools.

Mirrors TS createForumTopic tool in openclaw/extensions/telegram/tools/.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def create_forum_topic(
    channel,
    chat_id: str,
    name: str,
    icon_color: int | None = None,
    icon_custom_emoji_id: str | None = None,
) -> dict[str, Any]:
    """Create a topic in a forum supergroup.

    Args:
        channel: TelegramChannel instance
        chat_id: Supergroup chat ID (must be a forum supergroup)
        name: Topic name (1-128 chars)
        icon_color: Optional RGB color integer for the topic icon
        icon_custom_emoji_id: Optional custom emoji ID for the topic icon

    Returns:
        dict with thread_id and name
    """
    if not hasattr(channel, "_app") or channel._app is None:
        raise RuntimeError("Telegram channel not started")

    kwargs: dict[str, Any] = {}
    if icon_color is not None:
        kwargs["icon_color"] = icon_color
    if icon_custom_emoji_id:
        kwargs["icon_custom_emoji_id"] = icon_custom_emoji_id

    forum_topic = await channel._app.bot.create_forum_topic(
        chat_id=int(chat_id) if str(chat_id).lstrip("-").isdigit() else chat_id,
        name=name,
        **kwargs,
    )
    return {
        "thread_id": forum_topic.message_thread_id,
        "name": forum_topic.name,
    }


async def close_forum_topic(channel, chat_id: str, message_thread_id: int) -> bool:
    """Close a forum topic (no new messages can be sent)."""
    if not hasattr(channel, "_app") or channel._app is None:
        raise RuntimeError("Telegram channel not started")
    await channel._app.bot.close_forum_topic(
        chat_id=int(chat_id) if str(chat_id).lstrip("-").isdigit() else chat_id,
        message_thread_id=message_thread_id,
    )
    return True


async def reopen_forum_topic(channel, chat_id: str, message_thread_id: int) -> bool:
    """Reopen a closed forum topic."""
    if not hasattr(channel, "_app") or channel._app is None:
        raise RuntimeError("Telegram channel not started")
    await channel._app.bot.reopen_forum_topic(
        chat_id=int(chat_id) if str(chat_id).lstrip("-").isdigit() else chat_id,
        message_thread_id=message_thread_id,
    )
    return True


async def delete_forum_topic(channel, chat_id: str, message_thread_id: int) -> bool:
    """Delete a forum topic and all its messages."""
    if not hasattr(channel, "_app") or channel._app is None:
        raise RuntimeError("Telegram channel not started")
    await channel._app.bot.delete_forum_topic(
        chat_id=int(chat_id) if str(chat_id).lstrip("-").isdigit() else chat_id,
        message_thread_id=message_thread_id,
    )
    return True


def register(api) -> None:
    """Register Telegram forum tools with the agent API."""
    try:
        api.register_tool(
            name="telegram_create_forum_topic",
            description="Create a new topic in a Telegram forum supergroup",
            handler=create_forum_topic,
            schema={
                "type": "object",
                "properties": {
                    "chat_id": {"type": "string", "description": "Forum supergroup chat ID"},
                    "name": {"type": "string", "description": "Topic name (1-128 chars)"},
                    "icon_color": {"type": "integer", "description": "Optional icon color (RGB int)"},
                    "icon_custom_emoji_id": {"type": "string", "description": "Optional custom emoji ID for topic icon"},
                },
                "required": ["chat_id", "name"],
            },
        )
        api.register_tool(
            name="telegram_close_forum_topic",
            description="Close a Telegram forum topic",
            handler=close_forum_topic,
            schema={
                "type": "object",
                "properties": {
                    "chat_id": {"type": "string"},
                    "message_thread_id": {"type": "integer"},
                },
                "required": ["chat_id", "message_thread_id"],
            },
        )
        api.register_tool(
            name="telegram_reopen_forum_topic",
            description="Reopen a closed Telegram forum topic",
            handler=reopen_forum_topic,
            schema={
                "type": "object",
                "properties": {
                    "chat_id": {"type": "string"},
                    "message_thread_id": {"type": "integer"},
                },
                "required": ["chat_id", "message_thread_id"],
            },
        )
        api.register_tool(
            name="telegram_delete_forum_topic",
            description="Delete a Telegram forum topic and all its messages",
            handler=delete_forum_topic,
            schema={
                "type": "object",
                "properties": {
                    "chat_id": {"type": "string"},
                    "message_thread_id": {"type": "integer"},
                },
                "required": ["chat_id", "message_thread_id"],
            },
        )
    except Exception as e:
        logger.debug("Could not register Telegram forum tools via api.register_tool: %s", e)
