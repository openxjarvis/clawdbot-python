"""iMessage channel plugin.

Mirrors TypeScript: openclaw/extensions/imessage/index.ts
"""
from __future__ import annotations


def register(api) -> None:
    try:
        from openclaw.channels.imessage import iMessageChannel
        api.register_channel(iMessageChannel())
    except ImportError:
        import logging
        logging.getLogger(__name__).warning("iMessage channel unavailable")

plugin = {
    "id": "imessage",
    "name": "iMessage",
    "description": "iMessage channel integration.",
    "register": register,
}
