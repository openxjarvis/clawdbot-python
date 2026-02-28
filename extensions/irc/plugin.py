"""IRC extension — registers the IRC channel plugin.

Mirrors TypeScript: openclaw/extensions/irc/index.ts
"""
from __future__ import annotations



def register(api) -> None:
    try:
        from openclaw.channels.irc.channel import IrcChannel

        api.register_channel(IrcChannel())
    except ImportError:
        import logging

        logging.getLogger(__name__).warning(
            "IRC channel unavailable — install optional IRC dependencies"
        )

plugin = {
    "id": "irc",
    "name": "IRC",
    "description": "IRC channel plugin.",
    "register": register,
}
