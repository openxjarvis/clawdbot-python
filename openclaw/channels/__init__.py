"""
Channel plugins for ClawdBot
"""

from .base import (
    ChannelCapabilities,
    ChannelPlugin,
    InboundMessage,
    MessageHandler,
    OutboundMessage,
)
from .connection import (
    ConnectionManager,
    ConnectionMetrics,
    ConnectionState,
    HealthChecker,
    ReconnectConfig,
)
from .registry import ChannelRegistry, get_channel, get_channel_registry, register_channel
from .webchat import WebChatChannel

try:
    from .telegram import EnhancedTelegramChannel, TelegramChannel
except ImportError:
    EnhancedTelegramChannel = None
    TelegramChannel = None

try:
    from .discord import DiscordChannel
except ImportError:
    DiscordChannel = None

try:
    from .slack import SlackChannel
except ImportError:
    SlackChannel = None

__all__ = [
    # Base classes
    "ChannelPlugin",
    "ChannelCapabilities",
    "InboundMessage",
    "OutboundMessage",
    "MessageHandler",
    # Registry
    "ChannelRegistry",
    "get_channel_registry",
    "register_channel",
    "get_channel",
    # Connection management
    "ConnectionManager",
    "ConnectionState",
    "ConnectionMetrics",
    "ReconnectConfig",
    "HealthChecker",
    # Channels
    "WebChatChannel",
]

if TelegramChannel:
    __all__.append("TelegramChannel")
if EnhancedTelegramChannel:
    __all__.append("EnhancedTelegramChannel")
if DiscordChannel:
    __all__.append("DiscordChannel")
if SlackChannel:
    __all__.append("SlackChannel")
