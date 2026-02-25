"""Telegram command handler with dynamic registration.

Handles native command registration for Telegram bots.
Fully aligned with TypeScript openclaw/src/telegram/bot-native-commands.ts
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def register_telegram_native_commands(
    bot: Any,
    cfg: dict[str, Any],
    account_id: str,
    native_enabled: bool = True,
    native_skills_enabled: bool = True,
    native_disabled_explicit: bool = False,
) -> None:
    """Register native commands with Telegram bot (mirrors TS registerTelegramNativeCommands).
    
    This function:
    1. Builds the complete command list from native commands, skill commands, and custom commands
    2. Registers handlers for each command with the bot
    3. Syncs the command list with Telegram API via setMyCommands
    
    Args:
        bot: Telegram bot instance (grammy Bot or python-telegram-bot)
        cfg: OpenClaw configuration
        account_id: Telegram account ID
        native_enabled: Whether native commands are enabled
        native_skills_enabled: Whether skill commands are enabled
        native_disabled_explicit: Whether native commands are explicitly disabled
    """
    if not native_enabled:
        logger.info("Native commands disabled for Telegram")
        return
    
    try:
        from openclaw.auto_reply.skill_commands import list_skill_commands_for_agents
        from openclaw.channels.telegram.commands import sync_telegram_commands
        
        # Get skill commands if enabled
        skill_commands = []
        if native_skills_enabled:
            try:
                skill_commands = list_skill_commands_for_agents(cfg)
                logger.info(f"Loaded {len(skill_commands)} skill commands")
            except Exception as exc:
                logger.warning(f"Failed to load skill commands: {exc}")
        
        # Sync commands with Telegram API
        success = await sync_telegram_commands(
            bot=bot,
            cfg=cfg,
            account_id=account_id,
            skill_commands=skill_commands,
        )
        
        if success:
            logger.info("Successfully registered Telegram native commands")
        else:
            logger.warning("Failed to register Telegram native commands")
    
    except Exception as exc:
        logger.error(f"Error registering Telegram native commands: {exc}")
    
    # If explicitly disabled, clear commands
    if native_disabled_explicit:
        try:
            await bot.set_my_commands([])
            logger.info("Cleared Telegram commands (explicitly disabled)")
        except Exception as exc:
            logger.warning(f"Failed to clear Telegram commands: {exc}")


__all__ = [
    "register_telegram_native_commands",
]
