"""Signal channel plugin.

Mirrors TypeScript: openclaw/extensions/signal/index.ts
"""
from __future__ import annotations


def register(api) -> None:
    try:
        from openclaw.channels.signal import SignalChannel
        api.register_channel(SignalChannel())
    except ImportError:
        import logging
        logging.getLogger(__name__).warning("Signal channel unavailable")

plugin = {
    "id": "signal",
    "name": "Signal",
    "description": "Signal messaging channel integration.",
    "register": register,
}
