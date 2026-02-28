"""BlueBubbles channel plugin.

Mirrors TypeScript: openclaw/extensions/bluebubbles/index.ts
"""
from __future__ import annotations


def register(api) -> None:
    try:
        from openclaw.channels.bluebubbles import BlueBubblesChannel
        api.register_channel(BlueBubblesChannel())
    except ImportError:
        import logging
        logging.getLogger(__name__).warning("BlueBubbles channel unavailable")

plugin = {
    "id": "bluebubbles",
    "name": "BlueBubbles",
    "description": "BlueBubbles iMessage bridge channel.",
    "register": register,
}
