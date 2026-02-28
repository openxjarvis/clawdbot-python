"""Tests for IrcChannel — no real IRC connection required (mocked)"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openclaw.channels.irc.channel import (
    IrcChannel,
    _nick_from_prefix,
    _parse_irc_line,
)
from openclaw.channels.base import InboundMessage


class TestIrcLineParser:
    """Unit tests for the IRC line parser"""

    def test_ping(self):
        result = _parse_irc_line("PING :irc.example.com")
        assert result is not None
        prefix, cmd, params = result
        assert prefix is None
        assert cmd == "PING"
        assert params == ["irc.example.com"]

    def test_privmsg_channel(self):
        result = _parse_irc_line(":nick!user@host PRIVMSG #general :Hello world")
        assert result is not None
        prefix, cmd, params = result
        assert prefix == "nick!user@host"
        assert cmd == "PRIVMSG"
        assert params[0] == "#general"
        assert params[1] == "Hello world"

    def test_privmsg_direct(self):
        result = _parse_irc_line(":alice!alice@host PRIVMSG openclaw :Hi bot")
        assert result is not None
        prefix, cmd, params = result
        assert params[0] == "openclaw"
        assert params[1] == "Hi bot"

    def test_numeric_reply(self):
        result = _parse_irc_line(":irc.example.com 001 openclaw :Welcome!")
        assert result is not None
        prefix, cmd, params = result
        assert cmd == "001"
        assert params[-1] == "Welcome!"

    def test_nick_in_use(self):
        result = _parse_irc_line(":irc.example.com 433 * openclaw :Nickname is already in use")
        assert result is not None
        _, cmd, _ = result
        assert cmd == "433"

    def test_empty_line(self):
        result = _parse_irc_line("")
        assert result is None

    def test_nick_from_prefix(self):
        assert _nick_from_prefix("alice!alice@host.com") == "alice"
        assert _nick_from_prefix("bob") == "bob"
        assert _nick_from_prefix("") == ""


class TestIrcChannelInit:
    """IrcChannel can be instantiated and has correct capabilities"""

    def test_init(self):
        ch = IrcChannel()
        assert ch.id == "irc"
        assert ch.label == "IRC"
        cap = ch.capabilities
        assert cap.block_streaming is True
        assert cap.text_chunk_limit == 350
        assert cap.supports_reactions is False
        assert cap.supports_threads is False

    def test_default_account_fields(self):
        ch = IrcChannel()
        assert ch._host == ""
        assert ch._port == 6697
        assert ch._tls is True
        assert ch._nick == "openclaw"


class TestIrcChannelPrivmsg:
    """Test _handle_privmsg message parsing"""

    @pytest.mark.asyncio
    async def test_channel_message(self):
        ch = IrcChannel()
        ch.id = "irc"
        received: list[InboundMessage] = []

        async def handler(msg: InboundMessage):
            received.append(msg)

        ch.set_message_handler(handler)

        await ch._handle_privmsg("alice!alice@host", ["#general", "Hello everyone"])

        assert len(received) == 1
        msg = received[0]
        assert msg.sender_id == "alice"
        assert msg.sender_name == "alice"
        assert msg.chat_id == "#general"
        assert msg.chat_type == "group"
        assert msg.text == "Hello everyone"
        assert msg.channel_id == "irc"

    @pytest.mark.asyncio
    async def test_direct_message(self):
        ch = IrcChannel()
        ch._nick = "openclaw"
        received: list[InboundMessage] = []

        async def handler(msg: InboundMessage):
            received.append(msg)

        ch.set_message_handler(handler)

        await ch._handle_privmsg("bob!bob@host", ["openclaw", "Private message"])

        assert len(received) == 1
        msg = received[0]
        assert msg.chat_type == "direct"
        assert msg.chat_id == "bob"
        assert msg.text == "Private message"

    @pytest.mark.asyncio
    async def test_nickserv_skipped(self):
        """Messages from NickServ should be ignored"""
        ch = IrcChannel()
        received: list[InboundMessage] = []

        async def handler(msg: InboundMessage):
            received.append(msg)

        ch.set_message_handler(handler)

        await ch._handle_privmsg("NickServ!NickServ@services", ["openclaw", "Password accepted"])

        assert len(received) == 0


class TestIrcTextChunking:
    """Test that send_text chunks long messages at 350 characters"""

    @pytest.mark.asyncio
    async def test_short_message_single_chunk(self):
        ch = IrcChannel()
        ch._running = True

        sent_lines: list[str] = []

        async def mock_send_raw(line: str):
            sent_lines.append(line)

        ch._send_raw = mock_send_raw
        ch._writer = MagicMock()

        await ch.send_text("#general", "Hello, world!")
        assert len(sent_lines) == 1
        assert "Hello, world!" in sent_lines[0]

    @pytest.mark.asyncio
    async def test_long_message_chunked(self):
        ch = IrcChannel()
        ch._running = True

        sent_lines: list[str] = []

        async def mock_send_raw(line: str):
            sent_lines.append(line)

        ch._send_raw = mock_send_raw
        ch._writer = MagicMock()

        # Message longer than 350 chars
        long_text = "A" * 800
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await ch.send_text("#general", long_text)

        assert len(sent_lines) > 1
        # Each chunk should be a PRIVMSG
        for line in sent_lines:
            assert line.startswith("PRIVMSG #general :")
            payload = line[len("PRIVMSG #general :"):]
            assert len(payload) <= 350

    @pytest.mark.asyncio
    async def test_send_text_not_running_raises(self):
        ch = IrcChannel()
        ch._running = False
        with pytest.raises(RuntimeError, match="not started"):
            await ch.send_text("#general", "hello")


class TestIrcChannelStart:
    """Test IrcChannel.start() with mocked network"""

    @pytest.mark.asyncio
    async def test_start_requires_host(self):
        ch = IrcChannel()
        with pytest.raises(ValueError, match="host"):
            await ch.start({})

    @pytest.mark.asyncio
    async def test_start_connects_and_registers(self):
        ch = IrcChannel()

        written_lines: list[str] = []

        mock_reader = AsyncMock()
        mock_reader.readline = AsyncMock(side_effect=asyncio.TimeoutError)
        mock_writer = MagicMock()
        mock_writer.write = MagicMock(side_effect=lambda data: written_lines.append(data.decode()))
        mock_writer.drain = AsyncMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        with patch("asyncio.open_connection", new_callable=AsyncMock, return_value=(mock_reader, mock_writer)):
            with patch("asyncio.create_task"):
                await ch.start({
                    "host": "irc.example.com",
                    "port": 6667,
                    "tls": False,
                    "nick": "testbot",
                })

        assert ch._running is True
        assert ch._host == "irc.example.com"
        assert ch._nick == "testbot"
        # NICK and USER commands should have been sent
        assert any("NICK testbot" in line for line in written_lines)
        assert any("USER" in line for line in written_lines)
