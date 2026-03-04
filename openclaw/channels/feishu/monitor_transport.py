"""WebSocket and Webhook transport implementations for Feishu channel.

WebSocket mode (default):
  - Uses lark_oapi.ws.Client for long-lived connection to Feishu
  - No public endpoint required
  - Auto-reconnects via SDK
  - IMPORTANT: lark_oapi.ws.Client.start() is blocking and uses a
    module-level event loop captured at import time. It MUST be run in a
    dedicated daemon thread with its own asyncio event loop — NOT via
    run_in_executor which would share the main loop and raise
    "RuntimeError: This event loop is already running".

Webhook mode:
  - Starts an aiohttp HTTP server on webhookHost:webhookPort
  - Fixed-window rate limiting per IP+path
  - Max body 1 MB, body read timeout 30s
  - autoChallenge for Feishu URL verification

Mirrors TypeScript: extensions/feishu/src/monitor.transport.ts
"""
from __future__ import annotations

import asyncio
import logging
import threading
from typing import TYPE_CHECKING, Any

from .monitor_state import get_webhook_rate_limiter, remove_ws_client, set_ws_client

if TYPE_CHECKING:
    from .config import ResolvedFeishuAccount

logger = logging.getLogger(__name__)

_MAX_BODY_BYTES = 1 * 1024 * 1024   # 1 MB
_BODY_READ_TIMEOUT = 30.0            # seconds

# Serialize concurrent multi-account WS starts so that each thread's
# asyncio.set_event_loop() call (which sets the thread-local loop) is
# complete before the next thread starts. Avoids the race where two
# threads could interleave and one thread sees the other's loop.
_WS_START_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# WebSocket transport
# ---------------------------------------------------------------------------

async def start_websocket_transport(
    account: ResolvedFeishuAccount,
    event_handler: Any,
    stop_event: asyncio.Event,
) -> None:
    """
    Start a Feishu WebSocket long connection in a dedicated daemon thread.

    lark_oapi.ws.Client uses a module-level asyncio event loop captured at
    import time. If the module is imported while the main loop is running,
    calling loop.run_until_complete() from run_in_executor would raise
    "RuntimeError: This event loop is already running".

    Fix: run ws_client.start() in a plain threading.Thread that creates and
    owns its own asyncio event loop, then patches the SDK's module-level
    `loop` so the client uses that thread-local loop. Mirrors the approach
    used by nanobot/nanobot/channels/feishu.py.

    Mirrors TS monitorWebSocket().
    """
    from .client import create_feishu_ws_client

    ws_client = create_feishu_ws_client(account, event_handler)
    set_ws_client(account.account_id, ws_client)

    logger.info(
        "[feishu] Starting WebSocket transport for account=%s domain=%s",
        account.account_id, account.domain_url,
    )

    ws_thread: threading.Thread | None = None

    def _run_ws_thread() -> None:
        """
        Entry point for the dedicated WS daemon thread.

        lark_oapi.ws.Client internally captures asyncio.get_event_loop() at
        module import time. When imported while the main loop is running (the
        normal case), it stores the main loop. If we don't override that, the
        SDK calls loop.run_until_complete() on the main loop from this thread,
        which raises "This event loop is already running".

        Fix: create a fresh loop for this thread, set it as the thread-local
        loop, AND override the SDK's module-level loop reference so the client
        uses our thread-local loop rather than the captured main loop.

        _WS_START_LOCK serializes multi-account starts: only one account
        patches _lark_ws_mod.loop and calls start() at a time, preventing
        races where two threads could interleave their loop assignments.
        """
        import lark_oapi.ws.client as _lark_ws_mod

        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)   # thread-local: safe
        with _WS_START_LOCK:
            # Override SDK's captured-at-import main loop reference.
            # This MUST be inside the lock so concurrent accounts don't race.
            _lark_ws_mod.loop = new_loop
            try:
                ws_client.start()
            except Exception as exc:
                logger.warning(
                    "[feishu] WS thread exited with error for account=%s: %s",
                    account.account_id, exc,
                )
            finally:
                try:
                    new_loop.close()
                except Exception:
                    pass

    ws_thread = threading.Thread(
        target=_run_ws_thread,
        daemon=True,
        name=f"feishu-ws-{account.account_id}",
    )
    ws_thread.start()

    try:
        # Wait until the gateway shuts down
        await stop_event.wait()
    finally:
        remove_ws_client(account.account_id)
        # Attempt graceful stop if SDK exposes it (currently it does not,
        # but future SDK versions may add ws_client.stop())
        if hasattr(ws_client, "stop"):
            try:
                ws_client.stop()
            except Exception:
                pass
        # The daemon thread will exit naturally when the process exits

    logger.info("[feishu] WebSocket transport stopped for account=%s", account.account_id)


# ---------------------------------------------------------------------------
# Webhook transport
# ---------------------------------------------------------------------------

async def start_webhook_transport(
    account: ResolvedFeishuAccount,
    event_handler: Any,
    stop_event: asyncio.Event,
) -> None:
    """
    Start an aiohttp HTTP server to receive Feishu webhook events.

    Mirrors TS monitorWebhook() (Node http.createServer).
    """
    try:
        from aiohttp import web
    except ImportError as e:
        raise ImportError(
            "aiohttp is required for Feishu webhook mode. "
            "Install it with: pip install aiohttp"
        ) from e

    host = account.webhook_host
    port = account.webhook_port
    path = account.webhook_path

    rate_limiter = get_webhook_rate_limiter()

    async def handle_event(request: web.Request) -> web.Response:
        # Rate limiting by client IP + path
        client_ip = request.remote or "unknown"
        rl_key = f"{client_ip}:{path}"
        if not await rate_limiter.is_allowed(rl_key):
            logger.warning("[feishu] Webhook rate limit exceeded for %s", rl_key)
            return web.Response(status=429, text="Too Many Requests")

        # Validate Content-Type
        ct = request.content_type or ""
        if "application/json" not in ct:
            return web.Response(status=400, text="Expected application/json")

        # Read body with size + timeout limits
        try:
            body = await asyncio.wait_for(
                request.read(),
                timeout=_BODY_READ_TIMEOUT,
            )
        except asyncio.TimeoutError:
            return web.Response(status=408, text="Body read timeout")

        if len(body) > _MAX_BODY_BYTES:
            return web.Response(status=413, text="Payload too large")

        # Dispatch to Feishu event handler
        try:
            import lark_oapi as lark

            # Build a minimal request-like object for the SDK dispatcher
            lark_req = lark.Request(
                path=path,
                http_method="POST",
                headers=dict(request.headers),
                body=body,
            )
            lark_resp = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: event_handler.do(lark_req),
            )

            resp_body = lark_resp.body if hasattr(lark_resp, "body") else b""
            resp_status = lark_resp.status_code if hasattr(lark_resp, "status_code") else 200

            return web.Response(
                status=resp_status,
                body=resp_body,
                content_type="application/json",
            )

        except Exception as e:
            logger.warning("[feishu] Webhook handler error: %s", e)
            return web.Response(status=500, text="Internal error")

    app = web.Application()
    app.router.add_post(path, handle_event)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)

    try:
        await site.start()
        logger.info(
            "[feishu] Webhook server listening on http://%s:%s%s for account=%s",
            host, port, path, account.account_id,
        )
        await stop_event.wait()
    finally:
        await runner.cleanup()
        logger.info("[feishu] Webhook transport stopped for account=%s", account.account_id)
