"""
Unit tests for ChannelPlugin base class.

Tests the channel plugin interface aligned with TS ChannelCapabilities:
  - chatTypes, edit, media, blockStreaming, nativeCommands, etc.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from openclaw.channels.base import (
    ChannelPlugin,
    ChannelCapabilities,
    InboundMessage,
    OutboundMessage,
)


class MockChannel(ChannelPlugin):
    """Minimal concrete channel implementation for testing."""

    def __init__(self, config: dict = None):
        super().__init__()
        self.config = config or {}
        self.started = False
        self.stopped = False
        self.sent: list = []

    async def on_start(self, config: dict):
        """Lifecycle hook called by start() template."""
        self.started = True

    async def on_stop(self):
        """Lifecycle hook called by stop() template."""
        self.stopped = True

    async def send_text(self, target: str, text: str, reply_to: str | None = None) -> str:
        """Required abstract method — TS: ChannelMessagingAdapter.sendText."""
        self.sent.append({"target": target, "text": text})
        return "123"


class TestChannelCapabilities:
    """Test ChannelCapabilities aligned with TS ChannelCapabilities type."""

    def test_default_capabilities(self):
        """ChannelCapabilities defaults match TS — most features are opt-in."""
        caps = ChannelCapabilities()

        # TS: chatTypes is required, default to ["direct"]
        assert hasattr(caps, "chat_types")

        # TS optional fields that default to off/False
        assert hasattr(caps, "supports_edit")
        assert hasattr(caps, "supports_media") or hasattr(caps, "supports_reply")
        assert caps.supports_edit is False

    def test_block_streaming_flag(self):
        """blockStreaming disables streaming (send full message at once)."""
        caps = ChannelCapabilities(block_streaming=True)
        assert caps.block_streaming is True

    def test_native_commands_flag(self):
        """nativeCommands enables platform slash/native command handling."""
        caps = ChannelCapabilities(native_commands=True)
        assert caps.native_commands is True

    def test_edit_flag(self):
        """edit capability — can modify already-sent messages."""
        caps = ChannelCapabilities(supports_edit=True)
        assert caps.supports_edit is True

    def test_media_flag(self):
        """media capability — can send/receive media attachments."""
        caps = ChannelCapabilities(supports_media=True)
        assert caps.supports_media is True


class TestInboundMessage:
    """Test InboundMessage aligned with TS InboundMessage."""

    def test_create_inbound_message(self):
        """InboundMessage requires channel_id, message_id, sender_id, text, etc."""
        msg = InboundMessage(
            channel_id="telegram",
            message_id="msg_1",
            sender_id="123",
            sender_name="Alice",
            chat_id="chat_1",
            chat_type="direct",
            text="Hello",
            timestamp="2024-01-01T00:00:00Z",
        )

        assert msg.channel_id == "telegram"
        assert msg.sender_id == "123"
        assert msg.text == "Hello"
        assert msg.message_id == "msg_1"

    def test_inbound_message_with_metadata(self):
        """InboundMessage can carry arbitrary metadata."""
        msg = InboundMessage(
            channel_id="telegram",
            message_id="msg_1",
            sender_id="123",
            sender_name="Alice",
            chat_id="chat_1",
            chat_type="private",
            text="Hello",
            timestamp="2024-01-01T00:00:00Z",
            metadata={"chat_type": "private"},
        )

        assert msg.metadata == {"chat_type": "private"}

    def test_inbound_message_defaults(self):
        """Optional fields have sensible defaults."""
        msg = InboundMessage(
            channel_id="telegram",
            message_id="m1",
            sender_id="u1",
            sender_name="User",
            chat_id="c1",
            chat_type="direct",
            text="Hi",
            timestamp="2024-01-01T00:00:00Z",
        )

        assert msg.reply_to is None
        assert isinstance(msg.attachments, list)
        assert isinstance(msg.metadata, dict)


class TestOutboundMessage:
    """Test OutboundMessage aligned with TS outbound model."""

    def test_create_outbound_message(self):
        """OutboundMessage requires channel_id, target, text."""
        msg = OutboundMessage(
            channel_id="telegram",
            target="123",
            text="Hello back",
        )

        assert msg.channel_id == "telegram"
        assert msg.target == "123"
        assert msg.text == "Hello back"

    def test_outbound_with_reply_to(self):
        """OutboundMessage supports reply_to for threaded replies."""
        msg = OutboundMessage(
            channel_id="telegram",
            target="123",
            text="Reply here",
            reply_to="msg_1",
        )

        assert msg.reply_to == "msg_1"


class TestChannelPluginLifecycle:
    """Test channel plugin lifecycle."""

    @pytest.mark.asyncio
    async def test_start_channel(self):
        channel = MockChannel(config={})
        await channel.start({})
        assert channel.started is True

    @pytest.mark.asyncio
    async def test_stop_channel(self):
        channel = MockChannel(config={})
        await channel.stop()
        assert channel.stopped is True

    @pytest.mark.asyncio
    async def test_start_stop_cycle(self):
        channel = MockChannel(config={})
        await channel.start({})
        assert channel.started is True
        await channel.stop()
        assert channel.stopped is True


class TestChannelMessaging:
    """Test channel messaging functionality."""

    @pytest.mark.asyncio
    async def test_send_text(self):
        """send_text is the primary outbound method (TS: ChannelMessagingAdapter)."""
        channel = MockChannel(config={})
        await channel.send_text("chat_123", "Hello!")
        assert channel.sent[0]["text"] == "Hello!"

    def test_get_capabilities(self):
        """capabilities attribute returns a ChannelCapabilities instance."""
        channel = MockChannel(config={})
        caps = channel.capabilities
        assert isinstance(caps, ChannelCapabilities)


class TestChannelConfiguration:
    """Test channel configuration."""

    def test_channel_receives_config(self):
        """Channel stores its configuration."""
        config = {"botToken": "test_token", "enabled": True}
        channel = MockChannel(config=config)

        assert channel.config == config
        assert channel.config["botToken"] == "test_token"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
