---
summary: "OpenClaw Python gateway: configuration, WebSocket API, and authentication"
read_when:
  - Configuring the gateway WebSocket API
  - Setting up gateway authentication
title: "Gateway"
---

# Gateway

The **OpenClaw Python Gateway** is the central process that:

1. Loads all plugins and channels
2. Runs the agent event loop
3. Exposes a **WebSocket API** for the control interface and CLI tools

## Starting the gateway

```bash
openclaw start         # foreground
openclaw start --daemon  # background (writes PID to ~/.openclaw/gateway.pid)
```

Stop with:

```bash
openclaw stop
```

## WebSocket API

The gateway exposes a WebSocket endpoint on port **8080** by default (configurable
via `gateway.port`).

```json5
{
  gateway: {
    host: "0.0.0.0",
    port: 8080,
    auth: {
      type: "token",
      token: "my-secret-token",
    },
  },
}
```

## Authentication

Authentication for the WebSocket API:

```json5
{
  gateway: {
    auth: {
      type: "token",  // "token" | "none"
      token: "my-secret-token",
    },
  },
}
```

> **Set a token in production.** Without it, any local process can connect.

## Remote access

Connect to a remote gateway via the CLI:

```bash
openclaw --gateway ws://remote-host:8080 --token my-token plugins list
```

Or set `OPENCLAW_GATEWAY` and `OPENCLAW_TOKEN` environment variables.

## Gateway RPC methods

Plugins can register custom RPC methods:

```python
def register(api) -> None:
    def handle_ping(params, respond):
        respond(True, {"pong": True})

    api.register_gateway_method("myplugin.ping", handle_ping)
```

Call from CLI:

```bash
openclaw gateway call myplugin.ping
```

## Health check

```bash
openclaw status        # shows gateway PID, uptime, loaded plugins, active channels
```

## Configuration reference

```json5
{
  gateway: {
    host: "127.0.0.1",
    port: 8080,
    auth: { type: "token", token: "..." },
    corsOrigins: ["http://localhost:3000"],
    logLevel: "info",
  },
}
```
