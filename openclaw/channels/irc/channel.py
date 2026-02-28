"""IRC channel implementation — aligned with TS ircPlugin / monitorIrcProvider / sendMessageIrc"""
from __future__ import annotations


import asyncio
import logging
import ssl
from datetime import UTC, datetime
from typing import Any

from ..base import ChannelCapabilities, ChannelPlugin, InboundMessage
from ..chunker import chunk_text

logger = logging.getLogger(__name__)

# IRC text chunk limit — TS: textChunkLimit: 350
_IRC_TEXT_CHUNK_LIMIT = 350

# NickServ auth timeout
_NICKSERV_TIMEOUT = 10.0

# Reconnect config
_RECONNECT_INITIAL = 2.0
_RECONNECT_MAX = 60.0
_RECONNECT_FACTOR = 2.0


class IrcChannel(ChannelPlugin):
    """IRC channel — fully aligned with TS ircPlugin

    Account fields align with TS ResolvedIrcAccount:
        host, port, tls, nick, username, realname, password

    Config keys (camelCase or snake_case both accepted):
        host / IRC_HOST
        port / IRC_PORT  (default: 6697 with TLS, 6667 without)
        tls / IRC_TLS  (default: True)
        nick / IRC_NICK
        username
        realname
        password / IRC_PASSWORD
        channels — list of channels to auto-join (e.g. ["#general"])
    """

    def __init__(self):
        super().__init__()
        self.id = "irc"
        self.label = "IRC"
        self.capabilities = ChannelCapabilities(
            chat_types=["direct", "group"],
            supports_media=False,
            supports_reactions=False,
            supports_threads=False,
            supports_polls=False,
            block_streaming=True,   # IRC has no streaming concept
            supports_reply=False,
            text_chunk_limit=_IRC_TEXT_CHUNK_LIMIT,
        )
        # Connection state
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._irc_task: asyncio.Task | None = None
        # Account fields (TS ResolvedIrcAccount)
        self._host: str = ""
        self._port: int = 6697
        self._tls: bool = True
        self._nick: str = "openclaw"
        self._username: str = "openclaw"
        self._realname: str = "OpenClaw Bot"
        self._password: str = ""
        self._channels: list[str] = []

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    async def start(self, config: dict[str, Any]) -> None:
        """Connect to IRC server — mirrors TS ircPlugin.start()"""
        import os

        self._host = (
            config.get("host") or os.environ.get("IRC_HOST") or ""
        )
        if not self._host:
            raise ValueError("IRC host not provided (config key: host or env IRC_HOST)")

        self._tls = bool(
            config.get("tls", config.get("IRC_TLS", os.environ.get("IRC_TLS", "true"))) in (True, "true", "1", "yes")
        )
        default_port = 6697 if self._tls else 6667
        self._port = int(
            config.get("port") or os.environ.get("IRC_PORT") or default_port
        )
        self._nick = (
            config.get("nick") or os.environ.get("IRC_NICK") or "openclaw"
        )
        self._username = config.get("username") or self._nick
        self._realname = config.get("realname") or "OpenClaw Bot"
        self._password = (
            config.get("password") or os.environ.get("IRC_PASSWORD") or ""
        )
        password_file = config.get("passwordFile") or config.get("password_file")
        if password_file and not self._password:
            try:
                with open(password_file) as f:
                    self._password = f.read().strip()
            except Exception as e:
                logger.warning(f"[irc] Could not read password file: {e}")

        self._channels = list(config.get("channels") or [])

        logger.info(f"[irc] Connecting to {self._host}:{self._port} (tls={self._tls})")

        await self._connect()
        self._running = True
        self._irc_task = asyncio.create_task(self._run_loop())

    async def _connect(self) -> None:
        """Open TCP/TLS connection to IRC server"""
        if self._tls:
            ssl_ctx = ssl.create_default_context()
            self._reader, self._writer = await asyncio.open_connection(
                self._host, self._port, ssl=ssl_ctx
            )
        else:
            self._reader, self._writer = await asyncio.open_connection(
                self._host, self._port
            )

        # Registration sequence: NICK + USER
        await self._send_raw(f"NICK {self._nick}")
        await self._send_raw(
            f"USER {self._username} 0 * :{self._realname}"
        )

        logger.info(f"[irc] Connected to {self._host}:{self._port}")

    async def stop(self) -> None:
        """Disconnect from IRC with QUIT — mirrors TS ircPlugin.stop()"""
        logger.info("[irc] Disconnecting...")
        self._running = False
        try:
            await self._send_raw("QUIT :shutdown")
        except Exception:
            pass
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
        if self._irc_task:
            self._irc_task.cancel()
            try:
                await self._irc_task
            except asyncio.CancelledError:
                pass

    # -------------------------------------------------------------------------
    # Core read loop
    # -------------------------------------------------------------------------

    async def _run_loop(self) -> None:
        """Main IRC read loop with exponential backoff reconnect"""
        backoff = _RECONNECT_INITIAL
        while self._running:
            try:
                await self._read_loop()
                if self._running:
                    logger.warning("[irc] Connection closed unexpectedly")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"[irc] Connection error: {e}")
            if not self._running:
                break
            logger.info(f"[irc] Reconnecting in {backoff:.1f}s...")
            await asyncio.sleep(backoff)
            backoff = min(backoff * _RECONNECT_FACTOR, _RECONNECT_MAX)
            try:
                await self._connect()
                backoff = _RECONNECT_INITIAL
            except Exception as e:
                logger.warning(f"[irc] Reconnect failed: {e}")

    async def _read_loop(self) -> None:
        """Read and dispatch IRC messages until connection closes"""
        assert self._reader is not None
        while self._running:
            try:
                line_bytes = await asyncio.wait_for(self._reader.readline(), timeout=300)
            except asyncio.TimeoutError:
                # Send PING to keep connection alive
                await self._send_raw(f"PING {self._host}")
                continue
            if not line_bytes:
                break
            line = line_bytes.decode("utf-8", errors="replace").rstrip("\r\n")
            if line:
                await self._handle_line(line)

    async def _handle_line(self, line: str) -> None:
        """Parse and handle a raw IRC line — mirrors TS monitorIrcProvider logic"""
        logger.debug(f"[irc] < {line}")

        # PING/PONG keepalive
        if line.startswith("PING"):
            token = line[5:] if len(line) > 5 else self._host
            await self._send_raw(f"PONG {token}")
            return

        parsed = _parse_irc_line(line)
        if not parsed:
            return

        prefix, command, params = parsed

        if command == "001":
            # Welcome — server registration complete
            logger.info("[irc] Registered with server")
            if self._password:
                await self._nickserv_auth()
            for ch in self._channels:
                await self._send_raw(f"JOIN {ch}")
            return

        if command == "433":
            # Nick already in use
            self._nick = self._nick + "_"
            await self._send_raw(f"NICK {self._nick}")
            return

        if command == "PRIVMSG":
            await self._handle_privmsg(prefix, params)
            return

        if command == "NOTICE":
            logger.debug(f"[irc] NOTICE: {params}")
            return

    async def _nickserv_auth(self) -> None:
        """Authenticate with NickServ if password is set"""
        logger.info("[irc] Authenticating with NickServ")
        await self._send_raw(f"PRIVMSG NickServ :IDENTIFY {self._password}")

    # -------------------------------------------------------------------------
    # PRIVMSG handler
    # -------------------------------------------------------------------------

    async def _handle_privmsg(self, prefix: str | None, params: list[str]) -> None:
        """Convert IRC PRIVMSG to InboundMessage — mirrors TS monitorIrcProvider"""
        if len(params) < 2:
            return

        target = params[0]
        text = params[1]

        # Skip NickServ / ChanServ service messages
        nick = _nick_from_prefix(prefix or "")
        if nick.lower() in ("nickserv", "chanserv", "memoserv"):
            return

        # Determine chat type: channel starts with # or &
        if target.startswith(("#", "&")):
            chat_id = target
            chat_type = "group"
        else:
            chat_id = nick or target
            chat_type = "direct"

        msg_id = f"irc-{int(datetime.now(UTC).timestamp() * 1000)}"
        inbound = InboundMessage(
            channel_id=self.id,
            message_id=msg_id,
            sender_id=nick,
            sender_name=nick,
            chat_id=chat_id,
            chat_type=chat_type,
            text=text,
            timestamp=datetime.now(UTC).isoformat(),
            metadata={
                "prefix": prefix,
                "target": target,
                "raw_nick": nick,
            },
        )
        await self._handle_message(inbound)

    # -------------------------------------------------------------------------
    # Outbound
    # -------------------------------------------------------------------------

    async def send_text(
        self,
        target: str,
        text: str,
        reply_to: str | None = None,
    ) -> str:
        """Send PRIVMSG, auto-chunking at 350 chars — mirrors TS sendMessageIrc"""
        if not self._running or not self._writer:
            raise RuntimeError("IRC channel not started or not connected")

        chunks = chunk_text(text, _IRC_TEXT_CHUNK_LIMIT, mode="length")
        last_id = ""
        for chunk in chunks:
            await self._send_raw(f"PRIVMSG {target} :{chunk}")
            last_id = f"irc-{int(datetime.now(UTC).timestamp() * 1000)}"
            # Small delay between chunks to avoid flooding
            if len(chunks) > 1:
                await asyncio.sleep(0.5)

        return last_id or f"irc-{int(datetime.now(UTC).timestamp() * 1000)}"

    # -------------------------------------------------------------------------
    # Raw IRC write
    # -------------------------------------------------------------------------

    async def _send_raw(self, line: str) -> None:
        """Write a raw IRC command"""
        if not self._writer:
            return
        data = (line + "\r\n").encode("utf-8", errors="replace")
        self._writer.write(data)
        await self._writer.drain()
        logger.debug(f"[irc] > {line}")


# ---------------------------------------------------------------------------
# IRC line parser
# ---------------------------------------------------------------------------

def _parse_irc_line(line: str) -> tuple[str | None, str, list[str]] | None:
    """Parse a raw IRC line into (prefix, command, params).

    Format:  [:prefix] COMMAND [params...] [:trailing]
    Returns None if the line cannot be parsed.
    """
    if not line.strip():
        return None
    try:
        pos = 0
        prefix: str | None = None

        if line.startswith(":"):
            end = line.find(" ")
            if end == -1:
                return None
            prefix = line[1:end]
            pos = end + 1

        # Command
        space = line.find(" ", pos)
        if space == -1:
            command = line[pos:]
            return prefix, command.upper(), []
        command = line[pos:space].upper()
        pos = space + 1

        # Parameters
        params: list[str] = []
        while pos < len(line):
            if line[pos] == ":":
                params.append(line[pos + 1:])
                break
            space = line.find(" ", pos)
            if space == -1:
                params.append(line[pos:])
                break
            params.append(line[pos:space])
            pos = space + 1

        return prefix, command, params
    except Exception:
        return None


def _nick_from_prefix(prefix: str) -> str:
    """Extract nick from IRC prefix (nick!user@host)"""
    bang = prefix.find("!")
    if bang != -1:
        return prefix[:bang]
    return prefix
