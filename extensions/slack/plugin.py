"""Slack channel plugin.

Mirrors TypeScript: openclaw/extensions/slack/index.ts
"""
from __future__ import annotations


def register(api) -> None:
    try:
        from openclaw.channels.slack import SlackChannel
        api.register_channel(SlackChannel())
    except ImportError:
        import logging
        logging.getLogger(__name__).warning("Slack channel unavailable")

plugin = {
    "id": "slack",
    "name": "Slack",
    "description": "Slack bot channel integration.",
    "register": register,
}
