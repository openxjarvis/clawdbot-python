"""ACP gateway server — mirrors src/acp/server.ts

Entry point for running the ACP gateway server that bridges IDE clients
with the OpenClaw gateway via the ACP protocol.
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from typing import Any

from .session import create_in_memory_session_store
from .translator import AcpGatewayAgent
from .types import AcpServerOptions

logger = logging.getLogger(__name__)


async def serve_acp_gateway(opts: AcpServerOptions | None = None) -> None:
    """
    Start the ACP gateway server.

    Connects to the OpenClaw gateway and serves the ACP protocol over stdin/stdout
    (ndjson framing).  Mirrors TS serveAcpGateway().
    """
    from openclaw.config.loader import load_config
    from openclaw.gateway.client import GatewayClient

    options = opts or AcpServerOptions()
    cfg = load_config()

    gateway_url = options.gateway_url or os.environ.get("OPENCLAW_GATEWAY_URL", "ws://localhost:7890")
    token = options.gateway_token or os.environ.get("OPENCLAW_GATEWAY_TOKEN")
    password = options.gateway_password or os.environ.get("OPENCLAW_GATEWAY_PASSWORD")

    closed_event = asyncio.Event()
    stopped = False
    agent: AcpGatewayAgent | None = None

    def on_event(evt: dict) -> None:
        if agent:
            asyncio.ensure_future(agent.handle_gateway_event(evt))

    def on_hello_ok() -> None:
        if agent:
            agent.handle_gateway_reconnect()

    def on_close(code: int, reason: str) -> None:
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
        on_close=on_close,
    )

    session_store = create_in_memory_session_store()

    class _StdioConnection:
        """Minimal ACP connection adapter for stdin/stdout ndjson."""

        async def session_update(self, params: dict) -> None:
            import json
            line = json.dumps(params) + "\n"
            sys.stdout.write(line)
            sys.stdout.flush()

    connection = _StdioConnection()
    agent = AcpGatewayAgent(connection, gateway, options, session_store)
    agent.start()

    def shutdown() -> None:
        nonlocal stopped
        if stopped:
            return
        stopped = True
        gateway.stop()
        closed_event.set()

    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGINT, shutdown)
    loop.add_signal_handler(signal.SIGTERM, shutdown)

    await gateway.start()
    await closed_event.wait()


def _parse_args(args: list[str]) -> AcpServerOptions:
    opts = AcpServerOptions()
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
        if arg in ("--password", "--gateway-password") and i + 1 < len(args):
            opts.gateway_password = args[i + 1]
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
    return opts


def _print_help() -> None:
    print("""Usage: openclaw acp [options]

Gateway-backed ACP server for IDE integration.

Options:
  --url <url>             Gateway WebSocket URL
  --token <token>         Gateway auth token
  --password <password>   Gateway auth password
  --session <key>         Default session key (e.g. "agent:main:main")
  --session-label <label> Default session label to resolve
  --require-existing      Fail if the session key/label does not exist
  --reset-session         Reset the session key before first use
  --no-prefix-cwd         Do not prefix prompts with the working directory
  --verbose, -v           Verbose logging to stderr
  --help, -h              Show this help message
""")


if __name__ == "__main__":
    _opts = _parse_args(sys.argv[1:])
    asyncio.run(serve_acp_gateway(_opts))
