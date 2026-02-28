"""Tlon (Urbit) channel plugin.

Mirrors TypeScript: openclaw/extensions/tlon/index.ts
"""
from __future__ import annotations


def register(api) -> None:
    try:
        from openclaw.channels.tlon import TlonChannel
        api.register_channel(TlonChannel())
    except ImportError:
        import logging
        logging.getLogger(__name__).warning("Tlon channel unavailable")

plugin = {
    "id": "tlon",
    "name": "Tlon (Urbit)",
    "description": "Tlon/Urbit channel integration.",
    "register": register,
}
