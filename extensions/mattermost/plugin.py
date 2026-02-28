"""Mattermost channel plugin.

Mirrors TypeScript: openclaw/extensions/mattermost/index.ts
"""
from __future__ import annotations


def register(api) -> None:
    try:
        from openclaw.channels.mattermost import MattermostChannel
        api.register_channel(MattermostChannel())
    except ImportError:
        import logging
        logging.getLogger(__name__).warning("Mattermost channel unavailable")

plugin = {
    "id": "mattermost",
    "name": "Mattermost",
    "description": "Mattermost channel integration.",
    "register": register,
}
