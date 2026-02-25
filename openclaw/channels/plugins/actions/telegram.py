"""Telegram Channel Actions

Implements Telegram-specific actions: send, react, delete, edit, sticker, etc.
Matches TypeScript implementation in src/channels/plugins/actions/telegram.ts
"""

from __future__ import annotations

import logging
from typing import Any, Literal

logger = logging.getLogger(__name__)


class TelegramActions:
    """
    Telegram channel action adapter.
    
    Supports actions:
    - send: Send message
    - react: Add reaction to message
    - delete: Delete message
    - edit: Edit message
    - sticker: Send sticker
    - sticker-search: Search for stickers
    """
    
    provider_id: str = "telegram"
    
    @staticmethod
    def list_actions(config: dict[str, Any]) -> list[str]:
        """
        List available actions for Telegram.
        
        Args:
            config: Channel configuration
            
        Returns:
            List of action names
        """
        # Check if Telegram is enabled
        telegram_config = config.get("channels", {}).get("telegram", {})
        if not telegram_config.get("enabled", False):
            return []
        
        actions = ["send"]
        
        # Check for optional actions
        action_config = telegram_config.get("actions", {})
        if action_config.get("reactions", True):
            actions.append("react")
        if action_config.get("deleteMessage", True):
            actions.append("delete")
        if action_config.get("editMessage", True):
            actions.append("edit")
        if action_config.get("sticker", False):
            actions.extend(["sticker", "sticker-search"])
        
        return actions
    
    @staticmethod
    def supports_buttons(config: dict[str, Any]) -> bool:
        """Check if Telegram supports inline buttons"""
        telegram_config = config.get("channels", {}).get("telegram", {})
        return telegram_config.get("inline_buttons", True)
    
    @staticmethod
    def extract_tool_send(args: dict[str, Any]) -> dict[str, Any] | None:
        """
        Extract send parameters from tool args.
        
        Args:
            args: Tool arguments
            
        Returns:
            Extracted parameters or None
        """
        action = args.get("action", "").strip()
        if action != "sendMessage":
            return None
        
        to = args.get("to")
        if not to:
            return None
        
        account_id = args.get("accountId", "").strip() or None
        
        return {
            "to": to,
            "account_id": account_id
        }
    
    @staticmethod
    async def handle_action(
        action: str,
        params: dict[str, Any],
        config: dict[str, Any],
        account_id: str | None = None
    ) -> dict[str, Any]:
        """
        Handle Telegram action.
        
        Args:
            action: Action name
            params: Action parameters
            config: Channel configuration
            account_id: Optional account ID
            
        Returns:
            Action result
            
        Raises:
            ValueError: If action not supported
        """
        if action == "send":
            return await TelegramActions._handle_send(params, config, account_id)
        elif action == "react":
            return await TelegramActions._handle_react(params, config, account_id)
        elif action == "delete":
            return await TelegramActions._handle_delete(params, config, account_id)
        elif action == "edit":
            return await TelegramActions._handle_edit(params, config, account_id)
        elif action == "sticker":
            return await TelegramActions._handle_sticker(params, config, account_id)
        elif action == "sticker-search":
            return await TelegramActions._handle_sticker_search(params, config, account_id)
        else:
            raise ValueError(f"Action {action} not supported for Telegram")
    
    @staticmethod
    async def _handle_send(
        params: dict[str, Any],
        config: dict[str, Any],
        account_id: str | None
    ) -> dict[str, Any]:
        """Handle send message action"""
        from openclaw.telegram.send import send_message_telegram
        
        to = params.get("to")
        if not to:
            raise ValueError("Missing required parameter: to")
        
        message = params.get("message", "")
        media_url = params.get("media")
        caption = params.get("caption", "")
        content = message or caption or ""
        
        reply_to = params.get("replyTo")
        thread_id = params.get("threadId")
        buttons = params.get("buttons")
        as_voice = params.get("asVoice", False)
        silent = params.get("silent", False)
        quote_text = params.get("quoteText")
        
        result = await send_message_telegram(
            to,
            content,
            media_url=media_url,
            reply_to_message_id=reply_to,
            message_thread_id=thread_id,
            buttons=buttons,
            as_voice=as_voice,
            silent=silent,
            quote_text=quote_text,
            account_id=account_id,
        )
        
        return result
    
    @staticmethod
    async def _handle_react(
        params: dict[str, Any],
        config: dict[str, Any],
        account_id: str | None
    ) -> dict[str, Any]:
        """Handle react action"""
        from telegram import Bot
        
        # Extract parameters
        chat_id = params.get("chatId") or params.get("channelId") or params.get("to")
        if not chat_id:
            raise ValueError("Missing required parameter: chatId/channelId/to")
        
        message_id = params.get("messageId")
        if not message_id:
            raise ValueError("Missing required parameter: messageId")
        
        emoji = params.get("emoji", "").strip()
        remove = params.get("remove", False)
        
        # Get bot token
        telegram_config = config.get("channels", {}).get("telegram", {})
        bot_token = telegram_config.get("botToken") or telegram_config.get("bot_token")
        if not bot_token:
            raise ValueError("Telegram bot token not configured")
        
        # Normalize chat_id and message_id
        try:
            chat_id_int = int(chat_id) if str(chat_id).lstrip("-").isdigit() else chat_id
            message_id_int = int(message_id)
        except ValueError:
            raise ValueError("Invalid chat_id or message_id format")
        
        # Build reaction array
        reactions = []
        if not remove and emoji:
            reactions = [{"type": "emoji", "emoji": emoji}]
        
        # Send reaction
        bot = Bot(token=bot_token)
        try:
            await bot.set_message_reaction(
                chat_id=chat_id_int,
                message_id=message_id_int,
                reaction=reactions,
            )
            
            if not remove and emoji:
                return {"ok": True, "added": emoji}
            else:
                return {"ok": True, "removed": True}
        
        except Exception as exc:
            error_msg = str(exc)
            if "REACTION_INVALID" in error_msg.upper():
                return {"ok": False, "warning": f"Reaction unavailable: {emoji}"}
            raise
    
    @staticmethod
    async def _handle_delete(
        params: dict[str, Any],
        config: dict[str, Any],
        account_id: str | None
    ) -> dict[str, Any]:
        """Handle delete message action"""
        from telegram import Bot
        
        # Extract parameters
        chat_id = params.get("chatId") or params.get("channelId") or params.get("to")
        if not chat_id:
            raise ValueError("Missing required parameter: chatId/channelId/to")
        
        message_id = params.get("messageId")
        if not message_id:
            raise ValueError("Missing required parameter: messageId")
        
        # Get bot token
        telegram_config = config.get("channels", {}).get("telegram", {})
        bot_token = telegram_config.get("botToken") or telegram_config.get("bot_token")
        if not bot_token:
            raise ValueError("Telegram bot token not configured")
        
        # Normalize chat_id and message_id
        try:
            chat_id_int = int(chat_id) if str(chat_id).lstrip("-").isdigit() else chat_id
            message_id_int = int(message_id)
        except ValueError:
            raise ValueError("Invalid chat_id or message_id format")
        
        # Delete message
        bot = Bot(token=bot_token)
        await bot.delete_message(
            chat_id=chat_id_int,
            message_id=message_id_int,
        )
        
        logger.info("Deleted message %d from chat %s", message_id_int, chat_id)
        return {"ok": True, "deleted": True}
    
    @staticmethod
    async def _handle_edit(
        params: dict[str, Any],
        config: dict[str, Any],
        account_id: str | None
    ) -> dict[str, Any]:
        """Handle edit message action"""
        from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton
        
        # Extract parameters
        chat_id = params.get("chatId") or params.get("channelId") or params.get("to")
        if not chat_id:
            raise ValueError("Missing required parameter: chatId/channelId/to")
        
        message_id = params.get("messageId")
        if not message_id:
            raise ValueError("Missing required parameter: messageId")
        
        content = params.get("message") or params.get("content", "")
        if not content:
            raise ValueError("Missing required parameter: message/content")
        
        buttons = params.get("buttons")
        
        # Get bot token
        telegram_config = config.get("channels", {}).get("telegram", {})
        bot_token = telegram_config.get("botToken") or telegram_config.get("bot_token")
        if not bot_token:
            raise ValueError("Telegram bot token not configured")
        
        # Normalize chat_id and message_id
        try:
            chat_id_int = int(chat_id) if str(chat_id).lstrip("-").isdigit() else chat_id
            message_id_int = int(message_id)
        except ValueError:
            raise ValueError("Invalid chat_id or message_id format")
        
        # Build inline keyboard if buttons provided
        reply_markup = None
        if buttons is not None:
            if buttons:
                keyboard = []
                for row in buttons:
                    button_row = []
                    for btn in row:
                        button_row.append(
                            InlineKeyboardButton(
                                text=btn.get("text", ""),
                                callback_data=btn.get("callback_data", ""),
                            )
                        )
                    keyboard.append(button_row)
                reply_markup = InlineKeyboardMarkup(keyboard)
            else:
                # Empty buttons array means remove buttons
                reply_markup = InlineKeyboardMarkup([])
        
        # Edit message
        bot = Bot(token=bot_token)
        try:
            await bot.edit_message_text(
                chat_id=chat_id_int,
                message_id=message_id_int,
                text=content,
                parse_mode="Markdown",
                reply_markup=reply_markup,
            )
        except Exception as exc:
            # Ignore "message is not modified" errors
            if "message is not modified" in str(exc).lower():
                pass
            else:
                raise
        
        logger.info("Edited message %d in chat %s", message_id_int, chat_id)
        return {"ok": True, "messageId": str(message_id_int), "chatId": str(chat_id)}
    
    @staticmethod
    async def _handle_sticker(
        params: dict[str, Any],
        config: dict[str, Any],
        account_id: str | None
    ) -> dict[str, Any]:
        """Handle send sticker action"""
        from telegram import Bot
        
        # Extract parameters
        to = params.get("to") or params.get("target")
        if not to:
            raise ValueError("Missing required parameter: to/target")
        
        # Accept stickerId array (shared schema) and use first element as fileId
        sticker_ids = params.get("stickerId", [])
        file_id = sticker_ids[0] if sticker_ids else params.get("fileId")
        if not file_id:
            raise ValueError("Missing required parameter: stickerId or fileId")
        
        reply_to = params.get("replyTo")
        thread_id = params.get("threadId")
        
        # Get bot token
        telegram_config = config.get("channels", {}).get("telegram", {})
        bot_token = telegram_config.get("botToken") or telegram_config.get("bot_token")
        if not bot_token:
            raise ValueError("Telegram bot token not configured")
        
        # Normalize chat_id
        chat_id = int(to) if str(to).lstrip("-").isdigit() else to
        
        # Build send parameters
        send_params = {}
        if reply_to:
            send_params["reply_to_message_id"] = int(reply_to)
        if thread_id:
            send_params["message_thread_id"] = int(thread_id)
        
        # Send sticker
        bot = Bot(token=bot_token)
        message = await bot.send_sticker(
            chat_id=chat_id,
            sticker=file_id.strip(),
            **send_params,
        )
        
        # Record sent message
        from openclaw.channels.telegram.sent_message_cache import record_sent_message
        record_sent_message(chat_id, message.message_id)
        
        return {
            "ok": True,
            "messageId": str(message.message_id),
            "chatId": str(message.chat.id),
        }
    
    @staticmethod
    async def _handle_sticker_search(
        params: dict[str, Any],
        config: dict[str, Any],
        account_id: str | None
    ) -> dict[str, Any]:
        """Handle sticker search action"""
        from openclaw.channels.telegram.sticker_cache import search_stickers
        
        query = params.get("query", "").strip()
        if not query:
            raise ValueError("Missing required parameter: query")
        
        limit = params.get("limit", 5)
        if not isinstance(limit, int) or limit < 1:
            limit = 5
        
        # Search stickers
        results = search_stickers(query, limit)
        
        return {
            "ok": True,
            "count": len(results),
            "stickers": [
                {
                    "fileId": s.file_id,
                    "emoji": s.emoji,
                    "description": s.description,
                    "setName": s.set_name,
                }
                for s in results
            ],
        }
