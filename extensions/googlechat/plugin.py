"""Google Chat channel plugin.

Mirrors TypeScript: openclaw/extensions/googlechat/index.ts
"""
from __future__ import annotations


def register(api) -> None:
    try:
        from openclaw.channels.googlechat import GoogleChatChannel
        api.register_channel(GoogleChatChannel())
    except ImportError:
        import logging
        logging.getLogger(__name__).warning("Google Chat channel unavailable")

plugin = {
    "id": "googlechat",
    "name": "Google Chat",
    "description": "Google Chat channel integration.",
    "register": register,
}
