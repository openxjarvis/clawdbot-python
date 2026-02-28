"""Tests for ChannelCapabilities alignment with TS — no tokens required"""
from __future__ import annotations

import pytest

from openclaw.channels.base import ChannelCapabilities, ChatAttachment, InboundMessage


class TestChannelCapabilities:
    """Verify ChannelCapabilities has all TS-aligned fields with correct defaults"""

    def test_default_fields_exist(self):
        cap = ChannelCapabilities()
        assert hasattr(cap, "chat_types")
        assert hasattr(cap, "supports_media")
        assert hasattr(cap, "supports_reactions")
        assert hasattr(cap, "supports_threads")
        assert hasattr(cap, "supports_polls")
        # TS-aligned fields
        assert hasattr(cap, "block_streaming")
        assert hasattr(cap, "native_commands")
        assert hasattr(cap, "supports_edit")
        assert hasattr(cap, "supports_unsend")
        assert hasattr(cap, "supports_reply")
        assert hasattr(cap, "group_management")
        assert hasattr(cap, "text_chunk_limit")

    def test_default_values(self):
        cap = ChannelCapabilities()
        assert cap.chat_types == ["direct", "group"]
        assert cap.supports_media is False
        assert cap.supports_reactions is False
        assert cap.supports_threads is False
        assert cap.supports_polls is False
        assert cap.block_streaming is False
        assert cap.native_commands is False
        assert cap.supports_edit is False
        assert cap.supports_unsend is False
        assert cap.supports_reply is True   # default True (most channels support reply)
        assert cap.group_management is False
        assert cap.text_chunk_limit is None

    def test_telegram_capabilities(self):
        from openclaw.channels.telegram.channel import TelegramChannel
        ch = TelegramChannel()
        cap = ch.capabilities
        assert cap.block_streaming is True
        assert cap.native_commands is True
        assert cap.supports_edit is True
        assert cap.supports_unsend is True
        assert cap.supports_media is True
        assert cap.supports_reactions is True
        assert cap.supports_polls is True

    def test_discord_capabilities(self):
        from openclaw.channels.discord.channel import DiscordChannel
        ch = DiscordChannel()
        cap = ch.capabilities
        assert cap.supports_polls is True
        assert cap.native_commands is True
        assert cap.supports_media is True
        assert cap.supports_reactions is True
        assert cap.supports_threads is True

    def test_slack_capabilities(self):
        from openclaw.channels.slack.channel import SlackChannel
        ch = SlackChannel()
        cap = ch.capabilities
        assert cap.native_commands is True
        assert cap.supports_reactions is True
        assert cap.supports_threads is True

    def test_irc_capabilities(self):
        from openclaw.channels.irc.channel import IrcChannel
        ch = IrcChannel()
        cap = ch.capabilities
        assert cap.block_streaming is True
        assert cap.text_chunk_limit == 350
        assert cap.supports_reactions is False

    def test_imessage_capabilities(self):
        from openclaw.channels.imessage import iMessageChannel
        ch = iMessageChannel()
        cap = ch.capabilities
        assert cap.block_streaming is True

    def test_whatsapp_capabilities(self):
        from openclaw.channels.whatsapp.channel import WhatsAppChannel
        ch = WhatsAppChannel()
        cap = ch.capabilities
        assert cap.supports_media is True
        assert cap.supports_reactions is True

    def test_signal_capabilities(self):
        from openclaw.channels.signal.channel import SignalChannel
        ch = SignalChannel()
        cap = ch.capabilities
        assert cap.supports_media is True
        assert cap.supports_reactions is True

    def test_googlechat_capabilities(self):
        from openclaw.channels.googlechat.channel import GoogleChatChannel
        ch = GoogleChatChannel()
        cap = ch.capabilities
        assert cap.supports_threads is True
        assert cap.supports_media is True

    def test_capabilities_model_dump(self):
        """ChannelCapabilities should be serializable"""
        cap = ChannelCapabilities(
            chat_types=["direct"],
            supports_media=True,
            block_streaming=True,
            text_chunk_limit=350,
        )
        d = cap.model_dump()
        assert d["block_streaming"] is True
        assert d["text_chunk_limit"] == 350
        assert "native_commands" in d


class TestChatAttachment:
    """Verify ChatAttachment schema matches TS ChatAttachment"""

    def test_required_fields(self):
        att = ChatAttachment(type="image")
        assert att.type == "image"
        assert att.mime_type is None
        assert att.content is None
        assert att.url is None
        assert att.filename is None
        assert att.size is None

    def test_all_fields(self):
        att = ChatAttachment(
            type="file",
            mime_type="application/pdf",
            content="base64data==",
            url="https://example.com/doc.pdf",
            filename="doc.pdf",
            size=12345,
        )
        assert att.type == "file"
        assert att.mime_type == "application/pdf"
        assert att.content == "base64data=="
        assert att.size == 12345

    def test_types(self):
        """All valid type values from TS ChatAttachment"""
        for t in ("image", "audio", "video", "file", "sticker"):
            att = ChatAttachment(type=t)
            assert att.type == t


class TestInboundMessage:
    """Verify InboundMessage has proper ChatAttachment list"""

    def test_inbound_message_with_attachments(self):
        msg = InboundMessage(
            channel_id="telegram",
            message_id="123",
            sender_id="user1",
            sender_name="User One",
            chat_id="chat1",
            chat_type="direct",
            text="Hello",
            timestamp="2026-01-01T00:00:00",
            attachments=[
                ChatAttachment(type="image", mime_type="image/jpeg", size=1024),
            ],
        )
        assert len(msg.attachments) == 1
        assert msg.attachments[0].type == "image"
        assert msg.attachments[0].size == 1024

    def test_inbound_message_default_attachments(self):
        msg = InboundMessage(
            channel_id="discord",
            message_id="456",
            sender_id="user2",
            sender_name="User Two",
            chat_id="channel1",
            chat_type="group",
            text="Hi",
            timestamp="2026-01-01T00:00:00",
        )
        assert msg.attachments == []
        assert msg.reply_to is None
