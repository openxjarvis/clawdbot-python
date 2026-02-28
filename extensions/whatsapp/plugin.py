"""WhatsApp channel plugin.

Mirrors TypeScript: openclaw/extensions/whatsapp/index.ts
"""
from __future__ import annotations


def register(api) -> None:
    try:
        from openclaw.channels.whatsapp import WhatsAppChannel
        api.register_channel(WhatsAppChannel())
    except ImportError:
        import logging
        logging.getLogger(__name__).warning("WhatsApp channel unavailable")

plugin = {
    "id": "whatsapp",
    "name": "WhatsApp",
    "description": "WhatsApp channel integration.",
    "register": register,
}
