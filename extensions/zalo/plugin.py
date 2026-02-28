"""Zalo channel plugin.

Mirrors TypeScript: openclaw/extensions/zalo/index.ts
"""
from __future__ import annotations


def register(api) -> None:
    try:
        from openclaw.channels.zalo import ZaloChannel
        api.register_channel(ZaloChannel())
    except ImportError:
        import logging
        logging.getLogger(__name__).warning("Zalo channel unavailable")

plugin = {
    "id": "zalo",
    "name": "Zalo",
    "description": "Zalo channel integration.",
    "register": register,
}
