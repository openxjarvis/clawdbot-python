"""
Discord channel plugin.
Mirrors TypeScript: openclaw/extensions/discord/index.ts.

Registers:
  - DiscordChannel (channel plugin)
  - Discord agent tools (messaging, guild, moderation, presence, channels, reactions)
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def register(api) -> None:
    # ---- Channel ----
    try:
        from openclaw.channels.discord import DiscordChannel
        api.register_channel(DiscordChannel())
        logger.info("Discord channel registered")
    except ImportError as e:
        logger.warning(
            "Discord channel unavailable — install discord.py: "
            "pip install 'discord.py>=2.3.0' PyNaCl>=1.5.0  (%s)",
            e,
        )

    # ---- Agent Tools ----
    _register_tools(api)


def _register_tools(api) -> None:
    """Register all Discord-specific agent tools."""
    tool_modules = [
        ("discord_messaging", "openclaw.channels.discord.tools.discord_messaging"),
        ("discord_guild", "openclaw.channels.discord.tools.discord_guild"),
        ("discord_moderation", "openclaw.channels.discord.tools.discord_moderation"),
        ("discord_presence", "openclaw.channels.discord.tools.discord_presence_tools"),
        ("discord_channels", "openclaw.channels.discord.tools.discord_channels"),
        ("discord_reactions", "openclaw.channels.discord.tools.discord_reactions_tools"),
    ]

    for tool_name, module_path in tool_modules:
        try:
            import importlib
            mod = importlib.import_module(module_path)
            if hasattr(mod, "register"):
                mod.register(api)
                logger.debug("Discord tool module registered: %s", tool_name)
        except ImportError as e:
            logger.debug("Discord tool module '%s' not available: %s", tool_name, e)
        except Exception as e:
            logger.warning("Failed to register Discord tool module '%s': %s", tool_name, e)


plugin = {
    "id": "discord",
    "name": "Discord",
    "description": (
        "Full-featured Discord bot channel with DM/guild policies, slash commands, "
        "voice support, streaming, interactive components, exec approvals, and PluralKit."
    ),
    "register": register,
}
