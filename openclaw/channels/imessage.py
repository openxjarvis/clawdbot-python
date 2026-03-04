"""iMessage channel implementation for macOS — aligned with TS iMessagePlugin"""
from __future__ import annotations


import asyncio
import logging
import platform
from datetime import UTC, datetime
from typing import Any

from .base import ChannelCapabilities, ChannelPlugin, InboundMessage

logger = logging.getLogger(__name__)


class iMessageChannel(ChannelPlugin):
    """iMessage integration using AppleScript + imsg monitor subprocess (macOS only)

    Aligned with TS iMessagePlugin:
    - block_streaming=True: full message sent at once
    - Monitor subprocess reads incoming messages via `imsg monitor`
    - send_text via AppleScript
    """

    def __init__(self):
        super().__init__()
        self.id = "imessage"
        self.label = "iMessage"
        self.capabilities = ChannelCapabilities(
            chat_types=["direct", "group"],
            supports_media=True,
            supports_reactions=True,
            supports_threads=False,
            supports_polls=False,
            block_streaming=True,  # TS: iMessage doesn't support streaming
            supports_reply=True,
        )
        self._is_macos = platform.system() == "Darwin"
        self._monitor_proc: asyncio.subprocess.Process | None = None
        self._monitor_task: asyncio.Task | None = None

    async def start(self, config: dict[str, Any]) -> None:
        """Start iMessage integration and launch monitor subprocess"""
        if not self._is_macos:
            raise RuntimeError("iMessage channel requires macOS")

        logger.info("Starting iMessage channel...")

        try:
            proc = await asyncio.create_subprocess_exec(
                "osascript", "-e", 'tell application "Messages" to get name',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                _stdout, _stderr = await asyncio.wait_for(proc.communicate(), timeout=5)
            except asyncio.TimeoutError:
                proc.kill()
                raise RuntimeError("Messages.app not responding")

            if proc.returncode != 0:
                raise RuntimeError("Cannot access Messages.app")

            logger.info("Messages.app accessible")
            self._running = True

            # Try to start imsg monitor for inbound messages
            await self._start_monitor()
            logger.info("iMessage channel started")

        except FileNotFoundError:
            raise RuntimeError("osascript not found (macOS required)")
        except Exception as e:
            logger.error(f"Failed to start iMessage channel: {e}", exc_info=True)
            raise

    async def _start_monitor(self) -> None:
        """Start `imsg monitor` subprocess to receive incoming messages.

        imsg is a third-party CLI tool that wraps Messages.app.
        If not available, falls back to send-only mode gracefully.
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                "imsg", "monitor",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self._monitor_proc = proc
            self._monitor_task = asyncio.create_task(self._read_monitor(proc))
            logger.info("[imessage] imsg monitor started")
        except FileNotFoundError:
            logger.warning("[imessage] imsg not found — running in send-only mode")
            logger.warning("[imessage] Install imsg: https://github.com/nicholasgasior/imsg")
        except Exception as e:
            logger.warning(f"[imessage] Failed to start imsg monitor: {e} — send-only mode")

    async def _read_monitor(self, proc: asyncio.subprocess.Process) -> None:
        """Read lines from imsg monitor stdout and emit InboundMessage events"""
        import json
        assert proc.stdout is not None
        while self._running:
            try:
                line = await proc.stdout.readline()
                if not line:
                    break
                decoded = line.decode("utf-8", errors="replace").strip()
                if not decoded:
                    continue
                await self._parse_monitor_line(decoded)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"[imessage] Monitor read error: {e}")
                await asyncio.sleep(1)

    async def _parse_monitor_line(self, line: str) -> None:
        """Parse a single line from imsg monitor output.

        imsg monitor outputs JSON-like lines:
        {"from": "handle", "text": "...", "group": null, "date": "..."}
        """
        import json
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            # Plain text line — skip or log
            logger.debug(f"[imessage] Non-JSON monitor line: {line[:80]}")
            return

        sender = data.get("from") or data.get("handle") or "unknown"
        text = data.get("text") or data.get("message") or ""
        group = data.get("group") or data.get("chat")
        date_str = data.get("date") or data.get("timestamp") or datetime.now(UTC).isoformat()

        chat_id = group or sender
        chat_type = "group" if group else "direct"

        msg_id = f"imsg-{int(datetime.now(UTC).timestamp() * 1000)}"
        inbound = InboundMessage(
            channel_id=self.id,
            message_id=msg_id,
            sender_id=sender,
            sender_name=sender,
            chat_id=chat_id,
            chat_type=chat_type,
            text=text,
            timestamp=date_str,
            metadata={"raw": data},
        )
        await self._handle_message(inbound)

    async def stop(self) -> None:
        """Stop iMessage integration"""
        logger.info("Stopping iMessage channel...")
        self._running = False

        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None

        if self._monitor_proc:
            try:
                self._monitor_proc.terminate()
            except Exception:
                pass
            self._monitor_proc = None

    async def send_text(self, target: str, text: str, reply_to: str | None = None) -> str:
        """Send text message via AppleScript — mirrors TS iMessage send"""
        if not self._running:
            raise RuntimeError("iMessage channel not started")

        try:
            escaped_text = text.replace('"', '\\"').replace("\\", "\\\\")

            script = f"""
            tell application "Messages"
                set targetService to 1st service whose service type = iMessage
                set targetBuddy to buddy "{target}" of targetService
                send "{escaped_text}" to targetBuddy
            end tell
            """

            proc = await asyncio.create_subprocess_exec(
                "osascript", "-e", script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                _stdout, _stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
            except asyncio.TimeoutError:
                proc.kill()
                raise RuntimeError("osascript timed out sending iMessage")

            if proc.returncode == 0:
                message_id = f"imsg-{int(datetime.now(UTC).timestamp() * 1000)}"
                logger.info(f"Sent iMessage to {target}")
                return message_id
            else:
                error = (_stderr or b"").decode(errors="replace") or "Unknown error"
                raise RuntimeError(f"Failed to send message: {error}")

        except Exception as e:
            logger.error(f"iMessage send error: {e}", exc_info=True)
            raise

    async def send_media(
        self, target: str, media_url: str, media_type: str, caption: str | None = None
    ) -> str:
        """Send media message (limited AppleScript support — send as text fallback)"""
        if not self._running:
            raise RuntimeError("iMessage channel not started")

        logger.warning("iMessage media sending has limited AppleScript support")
        return await self.send_text(target, caption or f"[Media: {media_url}]")
