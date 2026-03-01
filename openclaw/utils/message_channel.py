"""Message channel normalization utilities."""
from __future__ import annotations

_CHANNEL_ALIASES: dict[str, str] = {
    "tg": "telegram",
    "slack": "slack",
    "discord": "discord",
    "matrix": "matrix",
    "openai": "openai",
    "internal": "internal",
}


def normalize_message_channel(channel: str | None) -> str | None:
    """Normalize a channel identifier string to its canonical form."""
    if not channel:
        return channel
    lower = channel.strip().lower()
    return _CHANNEL_ALIASES.get(lower, lower)


def is_internal_channel(channel: str | None) -> bool:
    """Return True if the channel is the internal (non-routable) channel."""
    return normalize_message_channel(channel) == "internal"
