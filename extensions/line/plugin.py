"""LINE channel plugin.

Mirrors TypeScript: openclaw/extensions/line/index.ts
"""
from __future__ import annotations


def register(api) -> None:
    try:
        from openclaw.channels.line import LINEChannel
        api.register_channel(LINEChannel())
    except ImportError:
        import logging
        logging.getLogger(__name__).warning("LINE channel unavailable")

plugin = {
    "id": "line",
    "name": "LINE",
    "description": "LINE messaging channel integration.",
    "register": register,
}
