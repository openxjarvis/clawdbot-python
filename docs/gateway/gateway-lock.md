---
summary: "Gateway singleton guard using the WebSocket listener bind"
read_when:
  - Running or debugging the gateway process
  - Investigating single-instance enforcement
title: "Gateway Lock"
---

# Gateway lock

## Why

- Ensure only one gateway instance runs per base port on the same host.
- Survive crashes/SIGKILL without leaving stale lock files.
- Fail fast with a clear error when the control port is already occupied.

## Mechanism

The gateway binds the WebSocket listener (default `ws://127.0.0.1:18789`) immediately on startup via `aiohttp.web.TCPSite`. If the bind fails with an `OSError` (address in use), startup raises `GatewayLockError`.

The OS releases the listener automatically on any process exit, including crashes and SIGKILL — no separate lock file or cleanup step is needed.

## Python implementation

- `GatewayLockError` in `openclaw/gateway/error_codes.py`
- Raised in `GatewayServer.start()` when `site.start()` throws `OSError`

```python
from openclaw.gateway.error_codes import GatewayLockError

# Raised automatically by GatewayServer.start()
# Message: "another gateway instance is already listening on ws://127.0.0.1:18789"
```

## Error surface

- If another process holds the port: `"another gateway instance is already listening on ws://<host>:<port>"`
- Other bind failures: `"failed to bind gateway socket on ws://<host>:<port>: <os_error>"`
