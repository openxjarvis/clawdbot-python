"""Discord channel plugin.

Mirrors TypeScript: openclaw/extensions/discord/index.ts
"""
from __future__ import annotations


def register(api) -> None:
    try:
        from openclaw.channels.discord import DiscordChannel
        api.register_channel(DiscordChannel())
    except ImportError:
        import logging
        logging.getLogger(__name__).warning("Discord channel unavailable")

plugin = {
    "id": "discord",
    "name": "Discord",
    "description": "Discord bot channel.",
    "register": register,
}
