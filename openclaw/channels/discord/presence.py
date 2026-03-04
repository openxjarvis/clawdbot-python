"""
Discord bot presence/activity management.
Mirrors src/discord/monitor/presence.ts and presence-cache.ts.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Discord activity type mapping (matches TS/Discord API spec)
# 0=Game/Playing, 1=Streaming, 2=Listening, 3=Watching, 4=Custom, 5=Competing
_ACTIVITY_TYPE_MAP = {
    0: "playing",
    1: "streaming",
    2: "listening",
    3: "watching",
    4: "custom",
    5: "competing",
}

_STATUS_MAP = {
    "online": "online",
    "dnd": "dnd",
    "idle": "idle",
    "invisible": "invisible",
}


async def set_presence(
    client: Any,
    activity_text: str | None = None,
    activity_type: int = 0,
    status: str | None = None,
    activity_url: str | None = None,
) -> None:
    """
    Set the bot's presence (activity + status).
    Wraps client.change_presence() with discord.Activity.

    activity_type values:
      0 = Playing (Game)
      1 = Streaming (requires activity_url pointing to Twitch/YouTube)
      2 = Listening to
      3 = Watching
      4 = Custom status
      5 = Competing in
    """
    import discord

    status_obj: discord.Status = _resolve_status(status)
    activity_obj: discord.BaseActivity | None = None

    if activity_text:
        activity_obj = _build_activity(activity_text, activity_type, activity_url)

    try:
        await client.change_presence(activity=activity_obj, status=status_obj)
        logger.debug(
            "[discord][presence] Set presence: activity=%r type=%d status=%s",
            activity_text,
            activity_type,
            status,
        )
    except Exception as exc:
        logger.warning("[discord][presence] Failed to set presence: %s", exc)


def _resolve_status(status: str | None) -> Any:
    import discord

    mapping = {
        "online": discord.Status.online,
        "dnd": discord.Status.dnd,
        "idle": discord.Status.idle,
        "invisible": discord.Status.invisible,
    }
    return mapping.get(status or "online", discord.Status.online)


def _build_activity(text: str, activity_type: int, url: str | None) -> Any:
    import discord

    if activity_type == 1:
        # Streaming — requires a valid Twitch/YouTube URL
        return discord.Streaming(name=text, url=url or "https://twitch.tv/placeholder")
    if activity_type == 2:
        return discord.Activity(type=discord.ActivityType.listening, name=text)
    if activity_type == 3:
        return discord.Activity(type=discord.ActivityType.watching, name=text)
    if activity_type == 4:
        return discord.CustomActivity(name=text)
    if activity_type == 5:
        return discord.Activity(type=discord.ActivityType.competing, name=text)
    # Default: Playing
    return discord.Game(name=text)


async def init_presence_from_config(client: Any, account: Any) -> None:
    """Apply initial presence from account config on bot ready."""
    await set_presence(
        client,
        activity_text=account.activity,
        activity_type=account.activity_type,
        status=account.status,
        activity_url=account.activity_url,
    )
