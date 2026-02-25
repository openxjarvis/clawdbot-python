"""Command dispatcher using message handler pattern.

Simplified version aligned with TypeScript openclaw/src/auto-reply/reply/provider-dispatcher.ts
Uses the channel's message_handler callback to integrate with agent runtime.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def dispatch_reply_with_buffered_dispatcher(
    inbound_ctx: dict[str, Any],
    runtime_ctx: dict[str, Any],
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    message_handler: Any | None,
    channel_id: str = "telegram",
) -> None:
    """Dispatch command via message handler (matches channel architecture).
    
    Converts command context to InboundMessage and dispatches via message_handler.
    
    Args:
        inbound_ctx: Finalized inbound context
        runtime_ctx: Runtime context with routing info
        update: Telegram update
        context: Telegram context
        message_handler: Message handler callback from channel manager
        channel_id: Channel ID
    """
    msg = update.message or update.edited_message
    if not msg or not msg.from_user:
        return
    
    chat = msg.chat
    chat_id = chat.id
    thread_id = runtime_ctx["thread_spec"].get("id") if runtime_ctx["thread_spec"]["scope"] == "forum" else None
    
    try:
        # Show typing indicator
        await context.bot.send_chat_action(
            chat_id=chat_id,
            action="typing",
            message_thread_id=thread_id
        )
        
        # If no message handler, cannot dispatch to agent
        if not message_handler:
            logger.warning("No message handler configured, cannot dispatch command to agent")
            await context.bot.send_message(
                chat_id=chat_id,
                text="Command processing not fully configured. Try again later.",
                message_thread_id=thread_id,
            )
            return
        
        # Convert to InboundMessage format
        from openclaw.channels.base import InboundMessage
        
        message_text = inbound_ctx.get("BodyForAgent", inbound_ctx.get("Body", ""))
        session_key = runtime_ctx["session_key"]
        
        inbound = InboundMessage(
            channel_id=channel_id,
            message_id=str(msg.message_id),
            sender_id=str(msg.from_user.id),
            sender_name=msg.from_user.first_name or msg.from_user.username or "User",
            chat_id=str(chat_id),
            chat_type="group" if chat.type in ("group", "supergroup") else "direct",
            text=message_text,
            timestamp=datetime.now(UTC).isoformat(),
            metadata={
                "event_type": "command",
                "command_body": inbound_ctx.get("CommandBody", ""),
                "command_args": inbound_ctx.get("CommandArgs"),
                "command_authorized": inbound_ctx.get("CommandAuthorized", False),
                "session_key": session_key,
                "thread_id": thread_id,
            },
        )
        
        # Dispatch via message handler
        logger.debug(f"Dispatching command via message_handler: {inbound_ctx.get('CommandBody')}")
        await message_handler(inbound)
    
    except Exception as exc:
        logger.error(f"Command dispatcher error: {exc}")
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"Error processing command: {exc}",
                message_thread_id=thread_id,
            )
        except Exception:
            pass


__all__ = [
    "dispatch_reply_with_buffered_dispatcher",
]
