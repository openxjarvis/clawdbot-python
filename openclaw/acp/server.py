"""ACP gateway server — mirrors src/acp/server.ts

Entry point for running the ACP gateway server that bridges IDE clients
with the OpenClaw gateway via the ACP protocol (NDJSON over stdin/stdout).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
from typing import Any

from .session import create_in_memory_session_store
from .translator import AcpGatewayAgent
from .types import AcpServerOptions

logger = logging.getLogger(__name__)

# Map ACP wire method names to AcpGatewayAgent method names
_METHOD_MAP: dict[str, str] = {
    "initialize": "initialize",
    "newSession": "new_session",
    "loadSession": "load_session",
    "prompt": "prompt",
    "cancel": "cancel",
    "setSessionMode": "set_session_mode",
    "unstable_listSessions": "list_sessions",
    "listSessions": "list_sessions",
    "authenticate": "authenticate",
}


class _StdioConnection:
    """
    ACP connection adapter for stdin/stdout NDJSON transport.

    The agent calls session_update() to push streaming events (tool calls,
    message chunks) back to the IDE while a prompt is in-flight.

    Format for outgoing updates (server push, no request id):
        {"type": "sessionUpdate", "sessionId": "...", "update": {...}}
    """

    def __init__(self) -> None:
        self._stdout_lock = asyncio.Lock()

    async def session_update(self, params: dict) -> None:
        """Write a streaming session update to stdout."""
        line = json.dumps({"type": "sessionUpdate", **params}) + "\n"
        async with self._stdout_lock:
            sys.stdout.write(line)
            sys.stdout.flush()

    async def _write_response(self, req_id: str, result: Any = None, error: str | None = None) -> None:
        """Write a method response to stdout."""
        if error is not None:
            payload = {"id": req_id, "error": {"message": error}}
        else:
            payload = {"id": req_id, "result": result if result is not None else {}}
        line = json.dumps(payload) + "\n"
        async with self._stdout_lock:
            sys.stdout.write(line)
            sys.stdout.flush()


async def _read_stdin_lines() -> list[str]:
    """Read a single line from stdin (async, non-blocking)."""
    loop = asyncio.get_running_loop()
    line = await loop.run_in_executor(None, sys.stdin.readline)
    return line


async def serve_acp_gateway(opts: AcpServerOptions | None = None) -> None:
    """
    Start the ACP gateway server.

    1. Connects to the OpenClaw gateway (WebSocket).
    2. Waits for the gateway handshake (hello ok).
    3. Reads NDJSON requests from stdin and dispatches to AcpGatewayAgent.
    4. Writes NDJSON responses / streaming session-update notifications to stdout.

    Mirrors TS serveAcpGateway().
    """
    from openclaw.gateway.client import GatewayClient

    options = opts or AcpServerOptions()
    gateway_url = options.gateway_url or os.environ.get("OPENCLAW_GATEWAY_URL", "ws://127.0.0.1:18789")
    token = options.gateway_token or os.environ.get("OPENCLAW_GATEWAY_TOKEN")
    password = options.gateway_password or os.environ.get("OPENCLAW_GATEWAY_PASSWORD")

    # ---------- Gateway-ready promise (mirrors TS approach) ----------
    gateway_ready_future: asyncio.Future = asyncio.get_running_loop().create_future()
    gateway_ready_settled = False

    def resolve_gateway_ready() -> None:
        nonlocal gateway_ready_settled
        if gateway_ready_settled:
            return
        gateway_ready_settled = True
        if not gateway_ready_future.done():
            gateway_ready_future.set_result(None)

    def reject_gateway_ready(err: Exception) -> None:
        nonlocal gateway_ready_settled
        if gateway_ready_settled:
            return
        gateway_ready_settled = True
        if not gateway_ready_future.done():
            gateway_ready_future.set_exception(err)

    # ---------- Agent & connection ----------
    connection = _StdioConnection()
    session_store = create_in_memory_session_store()
    agent: AcpGatewayAgent | None = None
    stopped = False
    closed_event = asyncio.Event()

    def on_event(evt: dict) -> None:
        if agent:
            asyncio.ensure_future(agent.handle_gateway_event(evt))

    def on_hello_ok(hello: dict) -> None:
        resolve_gateway_ready()
        if agent:
            agent.handle_gateway_reconnect()

    def on_connect_error(err: Exception) -> None:
        reject_gateway_ready(err)

    def on_close(code: int, reason: str) -> None:
        if not stopped:
            reject_gateway_ready(Exception(f"gateway closed before ready ({code}): {reason}"))
        if agent:
            agent.handle_gateway_disconnect(f"{code}: {reason}")
        if stopped:
            closed_event.set()

    gateway = GatewayClient(
        url=gateway_url,
        token=token,
        password=password,
        client_name="acp",
        on_event=on_event,
        on_hello_ok=on_hello_ok,
        on_connect_error=on_connect_error,
        on_close=on_close,
        verbose=options.verbose,
    )

    def shutdown() -> None:
        nonlocal stopped
        if stopped:
            return
        stopped = True
        resolve_gateway_ready()
        gateway.stop()
        closed_event.set()

    loop = asyncio.get_running_loop()
    try:
        loop.add_signal_handler(signal.SIGINT, shutdown)
        loop.add_signal_handler(signal.SIGTERM, shutdown)
    except (ValueError, NotImplementedError):
        pass

    # Start gateway in a background task — mirrors gateway.start() in TS
    gateway_task = asyncio.create_task(gateway.start())

    # Wait for gateway hello (or error)
    try:
        await gateway_ready_future
    except Exception as exc:
        shutdown()
        raise RuntimeError(f"ACP gateway failed to connect: {exc}") from exc

    if stopped:
        await closed_event.wait()
        return

    # Create agent now that gateway is connected
    agent = AcpGatewayAgent(connection, gateway, options, session_store)
    agent.start()

    # ---------- NDJSON stdin dispatch loop ----------
    dispatch_task = asyncio.create_task(_stdin_dispatch_loop(agent, connection, lambda: stopped))

    await closed_event.wait()
    dispatch_task.cancel()
    gateway_task.cancel()


async def _stdin_dispatch_loop(
    agent: AcpGatewayAgent,
    connection: _StdioConnection,
    is_stopped: Any,
) -> None:
    """
    Read NDJSON lines from stdin and dispatch each to the agent.

    Wire request format:  {"id": "...", "method": "...", "params": {...}}
    Wire response format: {"id": "...", "result": {...}}
                          {"id": "...", "error": {"message": "..."}}
    Streaming push:       {"type": "sessionUpdate", "sessionId": "...", "update": {...}}
    """
    loop = asyncio.get_running_loop()

    while not is_stopped():
        try:
            line = await loop.run_in_executor(None, sys.stdin.readline)
        except Exception:
            break

        if not line:
            break

        line = line.strip()
        if not line:
            continue

        try:
            msg = json.loads(line)
        except json.JSONDecodeError as exc:
            logger.debug("acp stdin: invalid JSON: %s", exc)
            continue

        if not isinstance(msg, dict):
            continue

        req_id = msg.get("id")
        method = msg.get("method", "")
        params = msg.get("params") or {}

        if not isinstance(method, str) or not method:
            continue

        asyncio.create_task(
            _dispatch_request(agent, connection, req_id, method, params)
        )


async def _dispatch_request(
    agent: AcpGatewayAgent,
    connection: _StdioConnection,
    req_id: Any,
    method: str,
    params: dict,
) -> None:
    """Dispatch a single ACP request to the agent and write the response."""
    python_method = _METHOD_MAP.get(method)
    if python_method is None:
        if req_id is not None:
            await connection._write_response(
                str(req_id),
                error=f"Unknown method: {method}",
            )
        return

    handler = getattr(agent, python_method, None)
    if handler is None:
        if req_id is not None:
            await connection._write_response(str(req_id), error=f"Not implemented: {method}")
        return

    try:
        result = await handler(params)
        if req_id is not None:
            await connection._write_response(str(req_id), result=result)
    except Exception as exc:
        logger.debug("acp dispatch error for %s: %s", method, exc)
        if req_id is not None:
            await connection._write_response(str(req_id), error=str(exc))


def _parse_args(args: list[str]) -> AcpServerOptions:
    from .secret_file import read_secret_from_file

    opts = AcpServerOptions()
    token_file: str | None = None
    password_file: str | None = None
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("--url", "--gateway-url") and i + 1 < len(args):
            opts.gateway_url = args[i + 1]
            i += 2
            continue
        if arg in ("--token", "--gateway-token") and i + 1 < len(args):
            opts.gateway_token = args[i + 1]
            i += 2
            continue
        if arg in ("--token-file", "--gateway-token-file") and i + 1 < len(args):
            token_file = args[i + 1]
            i += 2
            continue
        if arg in ("--password", "--gateway-password") and i + 1 < len(args):
            opts.gateway_password = args[i + 1]
            i += 2
            continue
        if arg in ("--password-file", "--gateway-password-file") and i + 1 < len(args):
            password_file = args[i + 1]
            i += 2
            continue
        if arg == "--session" and i + 1 < len(args):
            opts.default_session_key = args[i + 1]
            i += 2
            continue
        if arg == "--session-label" and i + 1 < len(args):
            opts.default_session_label = args[i + 1]
            i += 2
            continue
        if arg == "--require-existing":
            opts.require_existing_session = True
        elif arg == "--reset-session":
            opts.reset_session = True
        elif arg == "--no-prefix-cwd":
            opts.prefix_cwd = False
        elif arg in ("--verbose", "-v"):
            opts.verbose = True
        elif arg in ("--help", "-h"):
            _print_help()
            sys.exit(0)
        i += 1

    if opts.gateway_token and token_file:
        raise ValueError("Use either --token or --token-file, not both.")
    if opts.gateway_password and password_file:
        raise ValueError("Use either --password or --password-file, not both.")
    if token_file:
        opts.gateway_token = read_secret_from_file(token_file, "Gateway token")
    if password_file:
        opts.gateway_password = read_secret_from_file(password_file, "Gateway password")
    return opts


def _print_help() -> None:
    print("""Usage: openclaw acp [options]

Gateway-backed ACP server for IDE integration.

Options:
  --url <url>                    Gateway WebSocket URL
  --token <token>                Gateway auth token
  --token-file <path>            Read gateway auth token from file
  --password <password>          Gateway auth password
  --password-file <path>         Read gateway auth password from file
  --session <key>                Default session key (e.g. "agent:main:main")
  --session-label <label>        Default session label to resolve
  --require-existing             Fail if the session key/label does not exist
  --reset-session                Reset the session key before first use
  --no-prefix-cwd                Do not prefix prompts with the working directory
  --verbose, -v                  Verbose logging to stderr
  --help, -h                     Show this help message
""")


if __name__ == "__main__":
    argv = sys.argv[1:]
    if "--token" in argv or "--gateway-token" in argv:
        print(
            "Warning: --token can be exposed via process listings. "
            "Prefer --token-file or OPENCLAW_GATEWAY_TOKEN.",
            file=sys.stderr,
        )
    if "--password" in argv or "--gateway-password" in argv:
        print(
            "Warning: --password can be exposed via process listings. "
            "Prefer --password-file or OPENCLAW_GATEWAY_PASSWORD.",
            file=sys.stderr,
        )
    _opts = _parse_args(argv)
    asyncio.run(serve_acp_gateway(_opts))
