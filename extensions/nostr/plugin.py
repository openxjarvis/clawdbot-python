"""Nostr channel plugin.

Mirrors TypeScript: openclaw/extensions/nostr/index.ts
"""
from __future__ import annotations


def register(api) -> None:
    try:
        from openclaw.channels.nostr import NostrChannel
        api.register_channel(NostrChannel())
    except ImportError:
        import logging
        logging.getLogger(__name__).warning("Nostr channel unavailable")

plugin = {
    "id": "nostr",
    "name": "Nostr",
    "description": "Nostr protocol channel integration.",
    "register": register,
}
