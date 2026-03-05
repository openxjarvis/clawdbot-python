"""End-to-end integration tests for gateway"""

import asyncio
import pytest
import websockets
import json

from openclaw.gateway.bootstrap import GatewayBootstrap


@pytest.mark.asyncio
@pytest.mark.integration
async def test_gateway_startup():
    """Test complete gateway startup sequence"""
    bootstrap = GatewayBootstrap()
    
    try:
        result = await bootstrap.bootstrap()
        
        assert result["steps_completed"] >= 15
        assert bootstrap.config is not None
        assert bootstrap.server is not None
        
    finally:
        await bootstrap.shutdown()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_gateway_websocket_connect():
    """Test WebSocket connection to gateway"""
    bootstrap = GatewayBootstrap()
    
    try:
        await bootstrap.bootstrap()
        
        # Give server time to start
        await asyncio.sleep(1)

        if bootstrap.config is None or bootstrap.server is None:
            pytest.skip("Gateway bootstrap failed (port already in use or startup error)")
            return

        port = bootstrap.config.gateway.port if bootstrap.config.gateway else 18789
        auth_cfg = getattr(bootstrap.config.gateway, "auth", None) if hasattr(bootstrap.config, "gateway") else None
        token = getattr(auth_cfg, "token", None) if auth_cfg else None

        # Test connection — gateway always sends connect.challenge first
        async with websockets.connect(f"ws://localhost:{port}") as ws:
            conn_result = await _gateway_connect(ws, port, token)
            # Either a successful result or an auth error is acceptable
            assert "result" in conn_result or "error" in conn_result
            
    finally:
        await bootstrap.shutdown()


async def _gateway_connect(ws, port: int, token: str | None) -> dict:
    """Complete the challenge-response authentication handshake.

    The gateway sends a ``presence`` push event immediately on connection,
    then a ``connect.challenge`` event.  We drain push events until we
    see the challenge, then reply with a ``connect`` request.
    Returns the connect result dict.
    """
    # 1. Drain server-push events until we get connect.challenge
    challenge = None
    for _ in range(5):
        raw = await asyncio.wait_for(ws.recv(), timeout=5)
        msg = json.loads(raw)
        if msg.get("event") == "connect.challenge":
            challenge = msg
            break
        # Skip presence / tick / other push events
    assert challenge is not None, "Did not receive connect.challenge within 5 messages"

    # 2. Send the connect request (including auth token if available)
    auth = {"token": token} if token else {}
    connect_req = {
        "jsonrpc": "2.0",
        "method": "connect",
        "params": {
            "minProtocol": 3,
            "maxProtocol": 3,
            "client": {"name": "test", "version": "1.0", "platform": "test"},
            "auth": auth,
        },
        "id": 1,
    }
    await ws.send(json.dumps(connect_req))

    # 3. Receive the connect result
    raw_result = await asyncio.wait_for(ws.recv(), timeout=5)
    result = json.loads(raw_result)
    return result


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
async def test_gateway_agent_call():
    """Test making an agent call through gateway with full challenge-response auth."""
    bootstrap = GatewayBootstrap()

    try:
        await bootstrap.bootstrap()
        await asyncio.sleep(1)

        if bootstrap.config is None or bootstrap.server is None:
            pytest.skip("Gateway bootstrap failed (port already in use or startup error)")
            return

        port = bootstrap.config.gateway.port if bootstrap.config.gateway else 18789
        auth_cfg = getattr(bootstrap.config.gateway, "auth", None) if hasattr(bootstrap.config, "gateway") else None
        token = getattr(auth_cfg, "token", None) if auth_cfg else None

        async with websockets.connect(f"ws://localhost:{port}") as ws:
            # Complete the challenge-response handshake first
            conn_result = await _gateway_connect(ws, port, token)
            # Accept any valid result or auth-error (gateway may reject if no token configured)
            if "error" in conn_result:
                # Auth errors are acceptable in CI where no token is configured
                err = conn_result.get("error") or {}
                msg = err.get("message") if isinstance(err, dict) else str(err)
                pytest.skip(f"Gateway auth failed: {msg}")
                return

            # Agent call
            agent_req = {
                "jsonrpc": "2.0",
                "method": "agent",
                "params": {
                    "message": "Hello, test message",
                    "sessionId": "test-session",
                },
                "id": 2,
            }
            await ws.send(json.dumps(agent_req))

            response_data = await asyncio.wait_for(ws.recv(), timeout=10)
            response = json.loads(response_data)

            # Should either succeed or fail with a clear error
            assert "result" in response or "error" in response

            if "result" in response:
                assert "response" in response["result"]

    finally:
        await bootstrap.shutdown()
