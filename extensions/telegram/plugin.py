"""Telegram channel plugin.

Mirrors TypeScript: openclaw/extensions/telegram/index.ts
"""
from __future__ import annotations


def register(api) -> None:
    try:
        from openclaw.channels.telegram import TelegramChannel
        api.register_channel(TelegramChannel())
    except ImportError:
        import logging
        logging.getLogger(__name__).warning("Telegram channel unavailable")

plugin = {
    "id": "telegram",
    "name": "Telegram",
    "description": "Telegram bot channel integration.",
    "register": register,
}
