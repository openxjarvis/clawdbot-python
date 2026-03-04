"""GatewayClient — persistent WebSocket client for the OpenClaw gateway.

Mirrors TypeScript src/gateway/client.ts:
- Connects to the gateway WebSocket
- Handles connect.challenge → connect handshake
- Sends JSON-RPC requests and awaits typed responses
- Routes gateway events (chat, agent, tick, etc.) via on_event callback
- Automatic reconnect with exponential backoff
- start() / stop() lifecycle
"""
from __future__ import annotations

import asyncio
import json
import logging
import ipaddress
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)

GATEWAY_CLOSE_CODE_HINTS: dict[int, str] = {
    1000: "normal closure",
    1006: "abnormal closure (no close frame)",
    1008: "policy violation",
    1012: "service restart",
}

PROTOCOL_VERSION = 3

# Tick watchdog: if no tick received within TICK_WATCHDOG_FACTOR * tick interval,
# close the socket so the reconnect loop can re-establish the connection.
_DEFAULT_TICK_INTERVAL_MS = 5_000   # must match server TICK_INTERVAL_S
_TICK_WATCHDOG_FACTOR = 2           # close after 2 missed ticks


def _is_loopback(url: str) -> bool:
    """Return True if *url* targets a loopback address (127.x or ::1 or 'localhost')."""
    try:
        from urllib.parse import urlparse
        host = urlparse(url).hostname or ""
        if host in ("localhost", "127.0.0.1", "::1"):
            return True
        addr = ipaddress.ip_address(host)
        return addr.is_loopback
    except Exception:
        return False


def describe_gateway_close_code(code: int) -> str | None:
    return GATEWAY_CLOSE_CODE_HINTS.get(code)


@dataclass
class _PendingRequest:
    future: asyncio.Future
    expect_final: bool


@dataclass
class GatewayClientOptions:
    url: str = "ws://127.0.0.1:18789"
    token: str | None = None
    password: str | None = None
    client_name: str = "gateway-client"
    client_version: str = "1.0.0"
    role: str = "operator"
    scopes: list[str] = field(default_factory=lambda: ["operator.admin"])
    min_protocol: int = PROTOCOL_VERSION
    max_protocol: int = PROTOCOL_VERSION
    on_event: Callable[[dict[str, Any]], None] | None = None
    on_hello_ok: Callable[[dict[str, Any]], None] | None = None
    on_connect_error: Callable[[Exception], None] | None = None
    on_close: Callable[[int, str], None] | None = None
    verbose: bool = False


class GatewayClient:
    """
    Persistent WebSocket client for the OpenClaw gateway.

    Manages the full gateway protocol lifecycle:
    1. WebSocket connection open
    2. Server sends connect.challenge with nonce
    3. Client sends connect request (with token/password/role/scopes)
    4. Server responds with hello — client calls on_hello_ok
    5. Gateway events flow in via on_event callback
    6. Requests sent via request() → asyncio.Future resolved on response
    7. Auto-reconnect with exponential backoff on disconnect
    """

    def __init__(
        self,
        url: str | None = None,
        token: str | None = None,
        password: str | None = None,
        client_name: str = "acp",
        tick_interval_ms: int = _DEFAULT_TICK_INTERVAL_MS,
        on_event: Callable[[dict[str, Any]], None] | None = None,
        on_hello_ok: Callable[[dict[str, Any]], None] | None = None,
        on_connect_error: Callable[[Exception], None] | None = None,
        on_close: Callable[[int, str], None] | None = None,
        verbose: bool = False,
        **kwargs: Any,
    ) -> None:
        effective_url = url or "ws://127.0.0.1:18789"

        # Plaintext security guard: reject ws:// connections to non-loopback hosts.
        # wss:// is always allowed.  Mirrors TS tlsFingerprintPinning check.
        if effective_url.startswith("ws://") and not _is_loopback(effective_url):
            raise ValueError(
                f"Plaintext WebSocket (ws://) to non-loopback host is not allowed: {effective_url}. "
                "Use wss:// for remote connections."
            )

        self._url = effective_url
        self._token = token
        self._password = password
        self._client_name = client_name
        self._tick_interval_ms = tick_interval_ms
        self._on_event = on_event
        self._on_hello_ok = on_hello_ok
        self._on_connect_error = on_connect_error
        self._on_close = on_close
        self._verbose = verbose

        self._ws: Any = None
        self._pending: dict[str, _PendingRequest] = {}
        self._closed = False
        self._connect_nonce: str | None = None
        self._connect_sent = False
        self._backoff_ms = 1000
        self._last_seq: int | None = None
        self._connected = False
        self._last_tick_ms: float = 0.0   # wall-clock ms of last received tick

        self._reader_task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    @property
    def is_connected(self) -> bool:
        return self._connected and self._ws is not None

    async def start(self) -> None:
        """Connect to gateway and start the event reader loop."""
        self._closed = False
        self._stop_event.clear()
        await self._connect_loop()

    def stop(self) -> None:
        """Stop the client and close the WebSocket."""
        self._closed = True
        self._stop_event.set()
        if self._ws is not None:
            asyncio.ensure_future(self._ws.close())
            self._ws = None
        self._connected = False
        self._flush_pending_errors(Exception("gateway client stopped"))

    async def _connect_loop(self) -> None:
        """Main connection loop — reconnects with exponential backoff."""
        while not self._closed:
            try:
                await self._run_connection()
            except Exception as exc:
                if self._closed:
                    break
                if self._verbose:
                    logger.debug("gateway connection error: %s", exc)
            if self._closed:
                break
            delay = self._backoff_ms / 1000.0
            self._backoff_ms = min(self._backoff_ms * 2, 30_000)
            if self._verbose:
                logger.debug("gateway reconnecting in %.1fs", delay)
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass
            if self._stop_event.is_set():
                break

    async def _run_connection(self) -> None:
        """Single connection attempt — runs until disconnect."""
        try:
            import websockets
            from websockets.exceptions import WebSocketException
        except ImportError as exc:
            raise RuntimeError("websockets package required for GatewayClient") from exc

        self._connect_nonce = None
        self._connect_sent = False
        self._connected = False

        try:
            async with websockets.connect(
                self._url,
                max_size=25 * 1024 * 1024,
                ping_interval=None,
            ) as ws:
                self._ws = ws
                self._last_tick_ms = time.time() * 1000  # initialise so watchdog doesn't fire immediately
                close_code = 1006
                close_reason = ""

                # Tick watchdog task — closes the socket if no tick within
                # tickIntervalMs * TICK_WATCHDOG_FACTOR (mirrors TS).
                watchdog_interval = (
                    self._tick_interval_ms * _TICK_WATCHDOG_FACTOR / 1000.0
                )

                async def _tick_watchdog() -> None:
                    await asyncio.sleep(watchdog_interval)
                    while not self._closed and ws.open:
                        elapsed = time.time() * 1000 - self._last_tick_ms
                        if elapsed > self._tick_interval_ms * _TICK_WATCHDOG_FACTOR:
                            logger.warning(
                                "gateway tick watchdog: no tick in %.0f ms, closing socket",
                                elapsed,
                            )
                            await ws.close(1001, "tick watchdog timeout")
                            return
                        await asyncio.sleep(watchdog_interval)

                watchdog_task = asyncio.create_task(_tick_watchdog())

                try:
                    async for raw in ws:
                        if self._closed:
                            break
                        if isinstance(raw, bytes):
                            raw = raw.decode("utf-8", errors="replace")
                        await self._handle_message(raw)
                except Exception as exc:
                    if not self._closed:
                        logger.debug("gateway reader error: %s", exc)
                finally:
                    watchdog_task.cancel()
                    self._ws = None
                    self._connected = False
                    try:
                        code = ws.close_code or 1006
                        reason = ws.close_reason or ""
                        close_code = int(code)
                        close_reason = str(reason)
                    except Exception:
                        pass
                    self._flush_pending_errors(
                        Exception(f"gateway closed ({close_code}): {close_reason}")
                    )
                    if self._on_close:
                        try:
                            self._on_close(close_code, close_reason)
                        except Exception:
                            pass
        except Exception as exc:
            self._ws = None
            self._connected = False
            if not self._closed and self._on_connect_error:
                try:
                    self._on_connect_error(exc if isinstance(exc, Exception) else Exception(str(exc)))
                except Exception:
                    pass
            raise

    async def _handle_message(self, raw: str) -> None:
        """Route a raw JSON message to the appropriate handler."""
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.debug("gateway: invalid JSON: %s", raw[:200])
            return

        if not isinstance(parsed, dict):
            return

        # Event frame: has "event" key but no "id"
        if "event" in parsed and "id" not in parsed:
            event_name = parsed.get("event", "")

            if event_name == "connect.challenge":
                payload = parsed.get("payload") or {}
                nonce = payload.get("nonce", "") if isinstance(payload, dict) else ""
                if not nonce or not nonce.strip():
                    err = Exception("gateway connect challenge missing nonce")
                    if self._on_connect_error:
                        self._on_connect_error(err)
                    if self._ws:
                        await self._ws.close(1008, "connect challenge missing nonce")
                    return
                self._connect_nonce = nonce.strip()
                await self._send_connect()
                return

            seq = parsed.get("seq")
            if isinstance(seq, int):
                if self._last_seq is not None and seq > self._last_seq + 1:
                    logger.debug(
                        "gateway seq gap: expected %d got %d",
                        self._last_seq + 1,
                        seq,
                    )
                self._last_seq = seq

            # Update tick watchdog timestamp
            if event_name == "tick":
                self._last_tick_ms = time.time() * 1000

            if self._on_event:
                try:
                    self._on_event(parsed)
                except Exception as exc:
                    logger.debug("on_event callback error: %s", exc)
            return

        # Response frame: has "id" key
        if "id" in parsed:
            req_id = parsed.get("id")
            if not req_id or not isinstance(req_id, str):
                return
            pending = self._pending.get(req_id)
            if not pending:
                return

            # Skip accepted acks when expect_final=True
            payload = parsed.get("payload")
            if (
                pending.expect_final
                and isinstance(payload, dict)
                and payload.get("status") == "accepted"
            ):
                return

            self._pending.pop(req_id, None)
            if not pending.future.done():
                ok = parsed.get("ok", True)
                if ok:
                    pending.future.set_result(payload)
                else:
                    err_obj = parsed.get("error") or {}
                    msg = (
                        err_obj.get("message", "unknown error")
                        if isinstance(err_obj, dict)
                        else str(err_obj)
                    )
                    pending.future.set_exception(Exception(msg))

    async def _send_connect(self) -> None:
        """Send the connect request after receiving the challenge nonce."""
        if self._connect_sent or not self._ws:
            return
        nonce = (self._connect_nonce or "").strip()
        if not nonce:
            err = Exception("gateway connect challenge missing nonce")
            if self._on_connect_error:
                self._on_connect_error(err)
            return
        self._connect_sent = True

        token = (self._token or "").strip() or None
        password = (self._password or "").strip() or None
        auth: dict[str, Any] | None = None
        if token or password:
            auth = {}
            if token:
                auth["token"] = token
            if password:
                auth["password"] = password

        params: dict[str, Any] = {
            "minProtocol": PROTOCOL_VERSION,
            "maxProtocol": PROTOCOL_VERSION,
            "client": {
                "id": self._client_name,
                "version": "1.0.0",
                "platform": "python",
                "mode": "backend",
            },
            "role": "operator",
            "scopes": ["operator.admin"],
        }
        if auth:
            params["auth"] = auth

        try:
            result = await self.request("connect", params)
            self._backoff_ms = 1000
            self._connected = True
            if self._on_hello_ok:
                self._on_hello_ok(result or {})
        except Exception as exc:
            if self._on_connect_error:
                self._on_connect_error(exc if isinstance(exc, Exception) else Exception(str(exc)))
            if self._ws:
                try:
                    await self._ws.close(1008, "connect failed")
                except Exception:
                    pass

    async def request(
        self,
        method: str,
        params: Any = None,
        *,
        expect_final: bool = False,
    ) -> Any:
        """
        Send a request to the gateway and return the response payload.

        For long-running requests (e.g. chat.send), pass expect_final=True
        so that interim 'accepted' acks are ignored until the final response.
        """
        if self._ws is None:
            raise Exception("gateway not connected")

        req_id = str(uuid.uuid4())
        frame = {
            "type": "req",
            "id": req_id,
            "method": method,
        }
        if params is not None:
            frame["params"] = params

        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        self._pending[req_id] = _PendingRequest(future=future, expect_final=expect_final)

        try:
            await self._ws.send(json.dumps(frame))
        except Exception as exc:
            self._pending.pop(req_id, None)
            raise Exception(f"gateway send failed: {exc}") from exc

        return await future

    def _flush_pending_errors(self, err: Exception) -> None:
        """Reject all pending requests with the given error."""
        pending = dict(self._pending)
        self._pending.clear()
        for p in pending.values():
            if not p.future.done():
                p.future.set_exception(err)
