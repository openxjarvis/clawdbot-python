"""Nextcloud Talk channel plugin.

Mirrors TypeScript: openclaw/extensions/nextcloud-talk/index.ts
"""
from __future__ import annotations


def register(api) -> None:
    try:
        from openclaw.channels.nextcloud import NextcloudChannel
        api.register_channel(NextcloudChannel())
    except ImportError:
        import logging
        logging.getLogger(__name__).warning("Nextcloud Talk channel unavailable")

plugin = {
    "id": "nextcloud-talk",
    "name": "Nextcloud Talk",
    "description": "Nextcloud Talk channel integration.",
    "register": register,
}
