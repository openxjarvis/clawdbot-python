"""WhatsApp monitor: starts the Baileys bridge subprocess and manages
a local aiohttp webhook server to receive inbound events.

Architecture:
  Python starts bridge as a child process via asyncio.create_subprocess_exec.
  Bridge listens on a random free port and POSTs events to Python's webhook server.
  Python's webhook server routes events to handle_wa_message().

Mirrors TypeScript: src/web/auto-reply/monitor.ts and src/web/auto-reply/monitor/on-message.ts
"""
from __future__ import annotations

import asyncio
import logging
import os
import secrets
import socket
import sys
from pathlib import Path
from typing import Any, Callable, Awaitable, TYPE_CHECKING

if TYPE_CHECKING:
    from .config import ResolvedWhatsAppAccount
    from .bridge_client import BridgeClient

logger = logging.getLogger(__name__)

_BRIDGE_READY_TIMEOUT = 30.0   # seconds to wait for bridge to print BRIDGE_READY
_BRIDGE_SRC = str(
    Path(__file__).parent.parent.parent.parent.parent
    / "extensions" / "whatsapp" / "bridge" / "src" / "server.ts"
)


def _find_free_port() -> int:
    """Find an available TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def _wait_for_bridge_ready(proc: asyncio.subprocess.Process, timeout: float) -> int:
    """
    Read stdout until we see the BRIDGE_READY line, then return the port.
    The bridge prints: BRIDGE_READY port=<N>
    """
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            raise TimeoutError("Bridge did not signal BRIDGE_READY within timeout")
        try:
            line_bytes = await asyncio.wait_for(
                proc.stdout.readline(),  # type: ignore
                timeout=remaining,
            )
        except asyncio.TimeoutError:
            raise TimeoutError("Bridge did not signal BRIDGE_READY within timeout")
        if not line_bytes:
            raise RuntimeError("Bridge process exited unexpectedly before BRIDGE_READY")
        line = line_bytes.decode().strip()
        logger.debug("[whatsapp-bridge] %s", line)
        if line.startswith("BRIDGE_READY"):
            # Parse: BRIDGE_READY port=15000
            for token in line.split():
                if token.startswith("port="):
                    return int(token.split("=")[1])
            raise RuntimeError(f"Malformed BRIDGE_READY line: {line!r}")


async def start_bridge_process(port: int, secret: str) -> asyncio.subprocess.Process:
    """
    Start the Baileys bridge as a subprocess.

    Tries tsx (dev) first, falls back to node dist/server.js.
    """
    bridge_dir = Path(_BRIDGE_SRC).parent.parent
    env = {
        **os.environ,
        "BRIDGE_PORT": str(port),
        "BRIDGE_SECRET": secret,
        "BRIDGE_HOST": "127.0.0.1",
    }

    # Try tsx (TypeScript dev runner)
    tsx_candidates = ["tsx", "npx tsx", str(bridge_dir / "node_modules" / ".bin" / "tsx")]
    for tsx in tsx_candidates:
        tsx_parts = tsx.split()
        cmd = [*tsx_parts, _BRIDGE_SRC]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=str(bridge_dir),
            )
            logger.info("[whatsapp] Bridge started with tsx (pid=%s)", proc.pid)
            return proc
        except FileNotFoundError:
            continue

    # Fallback: pre-compiled node dist/server.js
    dist_entry = bridge_dir / "dist" / "server.js"
    if dist_entry.exists():
        proc = await asyncio.create_subprocess_exec(
            "node", str(dist_entry),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=str(bridge_dir),
        )
        logger.info("[whatsapp] Bridge started with node dist/server.js (pid=%s)", proc.pid)
        return proc

    raise RuntimeError(
        "Cannot start Baileys bridge: neither tsx nor node dist/server.js found. "
        "Run: cd extensions/whatsapp/bridge && npm install && npm run build"
    )


async def _pipe_stderr(proc: asyncio.subprocess.Process, prefix: str) -> None:
    """Forward bridge stderr to Python logger."""
    while True:
        try:
            line = await proc.stderr.readline()  # type: ignore
            if not line:
                break
            logger.debug("[%s] %s", prefix, line.decode().rstrip())
        except Exception:
            break


async def _drain_stdout(proc: asyncio.subprocess.Process) -> None:
    """Continuously drain bridge stdout to avoid pipe blocking."""
    while True:
        try:
            line = await proc.stdout.readline()  # type: ignore
            if not line:
                break
            logger.debug("[whatsapp-bridge] %s", line.decode().rstrip())
        except Exception:
            break


async def _handle_wa_message_update(
    event: dict[str, Any],
    account: Any,
    dispatch_fn: Callable[[Any], Awaitable[None]],
) -> None:
    """
    Handle messages.update events (reactions, poll vote tallies, etc.)
    forwarded from the Baileys bridge.

    Mirrors TypeScript messages.update handler in monitor.ts.
    """
    from ...channels.base import InboundMessage

    data = event.get("data", {})
    key = data.get("key", {})
    remote_jid: str = key.get("remoteJid", "")
    account_id: str = account.account_id

    # Reactions are in update.reactions[]
    reactions: list[dict[str, Any]] = data.get("reactions", []) or []
    for reaction in reactions:
        emoji: str | None = reaction.get("text") or reaction.get("emoji")
        sender_jid: str | None = (reaction.get("key") or {}).get("participant") or (
            reaction.get("key") or {}
        ).get("remoteJid")
        if not emoji or not sender_jid:
            continue

        # Build a synthetic InboundMessage for the reaction
        msg = InboundMessage(
            channel="whatsapp",
            account_id=account_id,
            sender_id=sender_jid.split("@")[0],
            sender_display_name=sender_jid.split("@")[0],
            chat_id=remote_jid,
            is_group=remote_jid.endswith("@g.us"),
            text=None,
            attachments=[],
            raw=event,
            metadata={
                "event_type": "reaction",
                "emoji": emoji,
                "target_message_id": key.get("id"),
                "reaction_sender_jid": sender_jid,
            },
        )
        try:
            await dispatch_fn(msg)
        except Exception as exc:
            logger.error("[whatsapp] Error dispatching reaction update: %s", exc)


class WhatsAppMonitor:
    """
    Manages the Baileys bridge subprocess and the aiohttp webhook server.

    Also tracks per-account runtime status and provides a watchdog that
    auto-restarts the bridge subprocess on crash.
    """

    def __init__(self) -> None:
        self._bridge_proc: asyncio.subprocess.Process | None = None
        self._webhook_server: Any = None
        self._webhook_port: int = 0
        self._bridge_port: int = 0
        self._bridge_secret: str = ""
        self._accounts: list[ResolvedWhatsAppAccount] = []
        self._bridge_client: BridgeClient | None = None
        self._dispatch_fn: Callable[[Any], Awaitable[None]] | None = None
        self._running = False
        self._tasks: list[asyncio.Task] = []

        # Runtime status tracking (mirrors TS account status fields)
        self._status: dict[str, dict[str, Any]] = {}   # account_id → status dict
        self._connected_at_ms: int = 0

    async def start(
        self,
        accounts: list["ResolvedWhatsAppAccount"],
        dispatch_fn: Callable[[Any], Awaitable[None]],
    ) -> "BridgeClient":
        """
        Start the bridge subprocess + webhook server + register all accounts.
        Returns the BridgeClient for outbound operations.
        """
        from .bridge_client import BridgeClient
        from .dedup import get_dedup
        from .inbound import handle_wa_message, _Debouncer

        self._accounts = accounts
        self._dispatch_fn = dispatch_fn
        self._bridge_secret = secrets.token_hex(16)

        # Find free ports
        self._bridge_port = _find_free_port()
        self._webhook_port = _find_free_port()

        # Start bridge subprocess
        self._bridge_proc = await start_bridge_process(self._bridge_port, self._bridge_secret)

        # Start piping stderr
        stderr_task = asyncio.create_task(
            _pipe_stderr(self._bridge_proc, "whatsapp-bridge")
        )
        self._tasks.append(stderr_task)

        # Wait for bridge ready signal
        try:
            actual_port = await _wait_for_bridge_ready(self._bridge_proc, _BRIDGE_READY_TIMEOUT)
            logger.info("[whatsapp] Bridge ready on port %d", actual_port)
            self._bridge_port = actual_port
        except TimeoutError:
            logger.warning("[whatsapp] Bridge BRIDGE_READY not received; using port %d", self._bridge_port)

        # Start draining remaining stdout
        stdout_task = asyncio.create_task(_drain_stdout(self._bridge_proc))
        self._tasks.append(stdout_task)

        self._bridge_client = BridgeClient(
            f"http://127.0.0.1:{self._bridge_port}",
            self._bridge_secret,
        )

        # Create per-account debouncers
        debouncers = {
            acct.account_id: _Debouncer(acct.debounce_ms)
            for acct in accounts
        }

        # Start webhook server
        webhook_url = f"http://127.0.0.1:{self._webhook_port}/events"

        import aiohttp.web as web  # type: ignore
        import aiohttp  # type: ignore

        connected_at_ms = int(__import__("time").time() * 1000)

        async def handle_event(request: web.Request) -> web.Response:
            try:
                event: dict[str, Any] = await request.json()
            except Exception:
                return web.Response(status=400, text="Bad JSON")

            event_type = event.get("type")
            account_id = event.get("accountId", "default")

            # Update last event time in status
            import time as _time
            if account_id in self._status:
                self._status[account_id]["lastEventAt"] = int(_time.time() * 1000)

            if event_type == "message":
                account = next(
                    (a for a in self._accounts if a.account_id == account_id), None
                )
                if account:
                    debouncer = debouncers.get(account_id) or _Debouncer(0)
                    dedup = get_dedup(account_id)
                    if account_id in self._status:
                        self._status[account_id]["lastMessageAt"] = int(_time.time() * 1000)
                    asyncio.create_task(
                        handle_wa_message(
                            event,
                            account,
                            dedup,
                            self._bridge_client,  # type: ignore
                            self._dispatch_fn,  # type: ignore
                            debouncer,
                            connected_at_ms,
                        )
                    )

            elif event_type == "message_update":
                # Forward reactions and poll vote tallies to the dispatch function
                account = next(
                    (a for a in self._accounts if a.account_id == account_id), None
                )
                if account and self._dispatch_fn:
                    asyncio.create_task(
                        _handle_wa_message_update(event, account, self._dispatch_fn)
                    )

            elif event_type == "connection":
                state = event.get("state")
                logger.info("[whatsapp] Account %s connection: %s", account_id, state)
                if account_id in self._status:
                    stat = self._status[account_id]
                    if state == "open":
                        stat["connected"] = True
                        stat["lastConnectedAt"] = int(_time.time() * 1000)
                        stat["selfJid"] = event.get("selfJid")
                    else:
                        if stat["connected"]:
                            stat["reconnectAttempts"] = stat.get("reconnectAttempts", 0) + 1
                        stat["connected"] = False
                        stat["lastDisconnect"] = state

            elif event_type == "qr":
                logger.info("[whatsapp] QR available for account %s", account_id)

            return web.Response(status=200, text="ok")

        app = web.Application()
        app.router.add_post("/events", handle_event)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", self._webhook_port)
        await site.start()
        self._webhook_server = runner
        logger.info("[whatsapp] Webhook server started on port %d", self._webhook_port)

        # Register all accounts with the bridge
        for account in accounts:
            try:
                await self._bridge_client.start_session(
                    account.account_id,
                    account.auth_dir,
                    webhook_url,
                )
                logger.info("[whatsapp] Registered account %s with bridge", account.account_id)
            except Exception as e:
                logger.error("[whatsapp] Failed to register account %s: %s", account.account_id, e)

        self._connected_at_ms = int(__import__("time").time() * 1000)
        # Initialize status for each account
        for account in accounts:
            self._status[account.account_id] = {
                "connected": False,
                "reconnectAttempts": 0,
                "lastConnectedAt": None,
                "lastDisconnect": None,
                "lastMessageAt": None,
                "lastEventAt": None,
                "lastError": None,
                "selfJid": None,
            }

        self._running = True

        # Start bridge watchdog
        watchdog_task = asyncio.create_task(self._watchdog())
        self._tasks.append(watchdog_task)

        return self._bridge_client

    async def stop(self) -> None:
        """Gracefully shut down the monitor."""
        self._running = False

        # Stop sessions
        if self._bridge_client:
            for account in self._accounts:
                try:
                    await self._bridge_client.stop_session(account.account_id)
                except Exception:
                    pass
            await self._bridge_client.close()
            self._bridge_client = None

        # Stop webhook server
        if self._webhook_server:
            try:
                await self._webhook_server.cleanup()
            except Exception:
                pass
            self._webhook_server = None

        # Terminate bridge process
        if self._bridge_proc:
            try:
                self._bridge_proc.terminate()
                await asyncio.wait_for(self._bridge_proc.wait(), timeout=5.0)
            except Exception:
                try:
                    self._bridge_proc.kill()
                except Exception:
                    pass
            self._bridge_proc = None

        # Cancel background tasks
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()

        logger.info("[whatsapp] Monitor stopped")

    async def _watchdog(self) -> None:
        """Periodically check that the bridge subprocess is alive; restart on crash."""
        _WATCHDOG_INTERVAL = 10.0  # seconds
        _RESTART_DELAY = 3.0

        while self._running:
            await asyncio.sleep(_WATCHDOG_INTERVAL)
            if not self._running:
                break
            if self._bridge_proc is None:
                continue

            ret = self._bridge_proc.returncode
            if ret is not None:
                # Process has exited
                logger.warning(
                    "[whatsapp] Bridge subprocess exited with code %s — restarting", ret
                )
                for account_id, stat in self._status.items():
                    stat["connected"] = False
                    stat["lastError"] = f"bridge_exited:{ret}"

                await asyncio.sleep(_RESTART_DELAY)
                if not self._running:
                    break

                try:
                    self._bridge_proc = await start_bridge_process(
                        self._bridge_port, self._bridge_secret
                    )
                    # Re-register accounts
                    if self._bridge_client:
                        webhook_url = f"http://127.0.0.1:{self._webhook_port}/events"
                        for account in self._accounts:
                            try:
                                await self._bridge_client.start_session(
                                    account.account_id,
                                    account.auth_dir,
                                    webhook_url,
                                )
                            except Exception as reg_err:
                                logger.error(
                                    "[whatsapp] Failed to re-register account %s after restart: %s",
                                    account.account_id, reg_err,
                                )
                    logger.info("[whatsapp] Bridge restarted after crash")
                except Exception as restart_err:
                    logger.error("[whatsapp] Failed to restart bridge: %s", restart_err)

    def get_status(self, account_id: str | None = None) -> dict[str, Any]:
        """Return runtime status for an account (or all accounts)."""
        if account_id:
            return dict(self._status.get(account_id, {}))
        return {k: dict(v) for k, v in self._status.items()}

    @property
    def bridge_client(self) -> "BridgeClient | None":
        return self._bridge_client

    @property
    def is_running(self) -> bool:
        return self._running
