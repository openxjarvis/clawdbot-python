"""Microsoft Teams channel plugin.

Mirrors TypeScript: openclaw/extensions/msteams/index.ts
"""
from __future__ import annotations


def register(api) -> None:
    try:
        from openclaw.channels.teams import TeamsChannel
        api.register_channel(TeamsChannel())
    except ImportError:
        import logging
        logging.getLogger(__name__).warning("Microsoft Teams channel unavailable")

plugin = {
    "id": "msteams",
    "name": "Microsoft Teams",
    "description": "Microsoft Teams channel integration.",
    "register": register,
}
