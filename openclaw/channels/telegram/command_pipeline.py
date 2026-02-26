"""Unified command pipeline orchestration.

Fully aligned with TypeScript openclaw/src/telegram/bot-native-commands.ts command handler flow
"""
from __future__ import annotations

import logging
from typing import Any

from telegram import Bot, Update
from telegram.ext import ContextTypes

from .command_auth import resolve_telegram_command_auth
from .command_routing import resolve_command_runtime_context
from .command_parsing import parse_command_args, build_command_text_from_args
from .command_menus import resolve_command_arg_menu, build_inline_keyboard_for_menu
from .command_inbound_context import finalize_inbound_context
from .command_dispatcher import dispatch_reply_with_buffered_dispatcher
from .command_config import handle_config_command, parse_config_command

logger = logging.getLogger(__name__)


async def handle_native_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    command_spec: dict[str, Any],
    bot: Bot,
    cfg: dict[str, Any],
    account_id: str,
    message_handler: Any | None = None,
    channel_id: str = "telegram",
) -> None:
    """Handle any native command through unified pipeline.
    
    Mirrors TS bot-native-commands.ts lines 440-647
    
    Args:
        update: Telegram update
        context: Telegram context
        command_spec: Command specification from registry
        bot: Bot instance
        cfg: OpenClaw configuration
        account_id: Telegram account ID
        message_handler: Message handler callback from channel manager
        channel_id: Channel ID
    """
    msg = update.message or update.edited_message
    if not msg or not msg.from_user:
        return
    
    # 1. Validate (skip duplicates, etc.)
    # TODO: Add shouldSkipUpdate check
    
    # 2. Authenticate
    auth = await resolve_telegram_command_auth(
        update=update,
        context=context,
        bot=bot,
        cfg=cfg,
        account_id=account_id,
        require_auth=True,
    )
    
    if not auth:
        logger.debug(f"Command authentication failed for /{command_spec.get('native_name')}")
        return
    
    # 3. Resolve runtime context (routing, session key)
    try:
        runtime_ctx = resolve_command_runtime_context(
            update=update,
            cfg=cfg,
            account_id=account_id,
            auth=auth,
        )
    except Exception as exc:
        logger.error(f"Failed to resolve runtime context: {exc}")
        await context.bot.send_message(
            chat_id=auth["chat_id"],
            text=f"Error: Failed to resolve command context."
        )
        return
    
    # 4. Handle built-in intercepted commands (/config, /debug)
    command_key = command_spec.get("key") or command_spec.get("native_name", "")
    raw_text = " ".join(context.args) if context.args else ""

    if command_key == "config":
        result = await handle_config_command(
            command_body=raw_text,
            is_authorized_sender=bool(auth.get("command_authorized")),
            channel_id=channel_id,
            cfg=cfg,
        )
        if result is not None:
            reply_text = result.get("reply_text")
            if reply_text:
                try:
                    from telegram.constants import ParseMode
                    await context.bot.send_message(
                        chat_id=auth["chat_id"],
                        text=reply_text,
                        parse_mode=ParseMode.HTML if "<" in reply_text else None,
                        message_thread_id=auth["resolved_thread_id"] if auth.get("is_forum") else None,
                    )
                except Exception as exc:
                    logger.warning("Failed to send /config reply: %s", exc)
            return

    # 5. Parse arguments
    command_args = parse_command_args(command_spec, raw_text)
    
    # 5. Check for menu (if arg choices available and arg missing)
    menu = resolve_command_arg_menu(
        command=command_spec,
        args=command_args,
        cfg=cfg,
    )
    
    if menu:
        # Show inline keyboard menu
        title = menu.get("title")
        if not title:
            arg_desc = menu["arg"].get("description", menu["arg"]["name"])
            command_name = command_spec.get("native_name", command_spec.get("key"))
            title = f"Choose {arg_desc} for /{command_name}."
        
        keyboard = build_inline_keyboard_for_menu(menu, command_spec)
        
        await context.bot.send_message(
            chat_id=auth["chat_id"],
            text=title,
            reply_markup=keyboard,
            message_thread_id=auth["resolved_thread_id"] if auth["is_forum"] else None,
        )
        return
    
    # 6. Build inbound context
    command_text = build_command_text_from_args(command_spec, command_args)
    
    inbound_ctx = {
        "Body": command_text,
        "BodyForAgent": command_text,
        "CommandBody": command_text,
        "CommandArgs": command_args,
        "CommandAuthorized": auth["command_authorized"],
        "CommandSource": "native",
        "From": build_from_string(update, auth),
        "To": build_to_string(update, auth),
        "SessionKey": runtime_ctx["session_key"],
        "CommandTargetSessionKey": runtime_ctx["session_key"],
        "ChatType": "chat",
        "ConversationLabel": f"telegram:{auth['chat_id']}",
    }
    
    # Finalize context
    finalized_ctx = finalize_inbound_context(inbound_ctx)
    
    # 7. Dispatch via message handler
    await dispatch_reply_with_buffered_dispatcher(
        inbound_ctx=finalized_ctx,
        runtime_ctx=runtime_ctx,
        update=update,
        context=context,
        message_handler=message_handler,
        channel_id=channel_id,
    )


def build_from_string(update: Update, auth: dict[str, Any]) -> str:
    """Build From string (mirrors TS from building logic).
    
    Args:
        update: Telegram update
        auth: Authentication result
        
    Returns:
        From string
    """
    if auth["is_group"]:
        chat_id = auth["chat_id"]
        thread_id = auth["resolved_thread_id"]
        if auth["is_forum"] and thread_id:
            return f"telegram:group:{chat_id}:topic:{thread_id}"
        else:
            return f"telegram:group:{chat_id}"
    else:
        return f"telegram:{auth['chat_id']}"


def build_to_string(update: Update, auth: dict[str, Any]) -> str:
    """Build To string (mirrors TS to building logic).
    
    Args:
        update: Telegram update
        auth: Authentication result
        
    Returns:
        To string
    """
    return f"telegram:{auth['chat_id']}"


__all__ = [
    "handle_native_command",
    "build_from_string",
    "build_to_string",
]
