"""Telegram command authentication.

Fully aligned with TypeScript openclaw/src/telegram/bot-native-commands.ts resolveTelegramCommandAuth
"""
from __future__ import annotations

import logging
from typing import Any, TypedDict

from telegram import Bot, Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


class TelegramCommandAuthResult(TypedDict):
    """Result of command authentication check."""
    chat_id: int
    is_group: bool
    is_forum: bool
    resolved_thread_id: int | None
    sender_id: str
    sender_username: str
    group_config: dict[str, Any] | None
    topic_config: dict[str, Any] | None
    command_authorized: bool


async def resolve_telegram_command_auth(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    bot: Bot,
    cfg: dict[str, Any],
    account_id: str,
    require_auth: bool = True,
) -> TelegramCommandAuthResult | None:
    """Resolve command authentication (mirrors TS resolveTelegramCommandAuth).
    
    Args:
        update: Telegram update
        context: Telegram context
        bot: Bot instance
        cfg: OpenClaw configuration
        account_id: Telegram account ID
        require_auth: Whether to enforce authorization
        
    Returns:
        Auth result or None if not authorized
    """
    msg = update.message or update.edited_message
    if not msg or not msg.from_user:
        return None
    
    chat = msg.chat
    chat_id = chat.id
    is_group = chat.type in ("group", "supergroup")
    is_forum = getattr(chat, "is_forum", False) is True
    message_thread_id = getattr(msg, "message_thread_id", None)
    sender_id = str(msg.from_user.id)
    sender_username = msg.from_user.username or ""
    
    # Get Telegram config
    telegram_cfg = cfg.get("channels", {}).get("telegram", {})
    account_cfg = telegram_cfg.get("accounts", {}).get(account_id, {})
    
    # For now, simplified auth logic (can be expanded later to match TS fully)
    # Check DM policy for direct messages
    if not is_group:
        dm_policy = telegram_cfg.get("dm_policy", "open")
        if dm_policy == "disabled":
            await context.bot.send_message(
                chat_id=chat_id,
                text="Direct messages are disabled."
            )
            return None
        elif dm_policy == "pairing":
            # Check if sender is in allowFrom store
            from openclaw.store.allow_from import AllowFromStore
            store = AllowFromStore(cfg.get("gateway", {}).get("workspace_dir", ""))
            
            entries = store.list_entries(scope="telegram", peer_id=account_id)
            allowed = any(
                e.get("user_id") == sender_id or e.get("username") == sender_username
                for e in entries
            )
            
            if not allowed and require_auth:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="You are not authorized to use this command."
                )
                return None
    
    # Check group access
    group_config = None
    topic_config = None
    resolved_thread_id = None
    
    if is_group:
        # Get group configuration
        groups_cfg = account_cfg.get("groups", {})
        group_config = groups_cfg.get(str(chat_id))
        
        if group_config:
            # Check if group is enabled
            if group_config.get("enabled") is False:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="This group is disabled."
                )
                return None
            
            # Check forum topics
            if is_forum and message_thread_id:
                resolved_thread_id = message_thread_id
                topics = group_config.get("topics", {})
                topic_config = topics.get(str(message_thread_id))
                
                if topic_config and topic_config.get("enabled") is False:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text="This topic is disabled.",
                        message_thread_id=message_thread_id
                    )
                    return None
    
    # Command is authorized
    command_authorized = True
    
    return TelegramCommandAuthResult(
        chat_id=chat_id,
        is_group=is_group,
        is_forum=is_forum,
        resolved_thread_id=resolved_thread_id,
        sender_id=sender_id,
        sender_username=sender_username,
        group_config=group_config,
        topic_config=topic_config,
        command_authorized=command_authorized,
    )


__all__ = [
    "TelegramCommandAuthResult",
    "resolve_telegram_command_auth",
]
