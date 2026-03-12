---
summary: "TypeBox/Pydantic schemas as the single source of truth for the gateway protocol"
read_when:
  - Updating protocol schemas or codegen
title: "Protocol Schemas"
---

# Protocol schemas as source of truth

Last updated: 2026-01-10

In the TypeScript implementation, TypeBox is used to define the **Gateway WebSocket protocol** (handshake, request/response, server events). In the Python implementation, equivalent schemas are defined using **Python dataclasses and dicts** (or Pydantic models where available). Those schemas drive **runtime validation** and **JSON Schema export**. One source of truth; everything else is generated.

If you want the higher-level protocol context, start with
[Gateway architecture](/concepts/architecture).

## Mental model (30 seconds)

Every Gateway WS message is one of three frames:

- **Request**: `{ "type": "req", "id": ..., "method": ..., "params": ... }`
- **Response**: `{ "type": "res", "id": ..., "ok": ..., "payload" | "error": ... }`
- **Event**: `{ "type": "event", "event": ..., "payload": ..., "seq"?: ..., "stateVersion"?: ... }`

The first frame **must** be a `connect` request. After that, clients can call
methods (e.g. `health`, `send`, `chat.send`) and subscribe to events (e.g.
`presence`, `tick`, `agent`).

Connection flow (minimal):

```
Client                    Gateway
  |---- req:connect -------->|
  |<---- res:hello-ok --------|
  |<---- event:tick ----------|
  |---- req:health ---------->|
  |<---- res:health ----------|
```

Common methods + events:

| Category  | Examples                                                  | Notes                              |
| --------- | --------------------------------------------------------- | ---------------------------------- |
| Core      | `connect`, `health`, `status`                             | `connect` must be first            |
| Messaging | `send`, `poll`, `agent`, `agent.wait`                     | side-effects need `idempotencyKey` |
| Chat      | `chat.history`, `chat.send`, `chat.abort`, `chat.inject`  | WebChat uses these                 |
| Sessions  | `sessions.list`, `sessions.patch`, `sessions.delete`      | session admin                      |
| Nodes     | `node.list`, `node.invoke`, `node.pair.*`                 | Gateway WS + node actions          |
| Events    | `tick`, `presence`, `agent`, `chat`, `health`, `shutdown` | server push                        |

## Example frames

Connect (first message):

```json
{
  "type": "req",
  "id": "c1",
  "method": "connect",
  "params": {
    "minProtocol": 2,
    "maxProtocol": 2,
    "client": {
      "id": "openclaw-macos",
      "displayName": "macos",
      "version": "1.0.0",
      "platform": "macos 15.1",
      "mode": "ui",
      "instanceId": "A1B2"
    }
  }
}
```

Hello-ok response:

```json
{
  "type": "res",
  "id": "c1",
  "ok": true,
  "payload": {
    "type": "hello-ok",
    "protocol": 2,
    "server": { "version": "dev", "connId": "ws-1" },
    "features": { "methods": ["health"], "events": ["tick"] },
    "snapshot": {
      "presence": [],
      "health": {},
      "stateVersion": { "presence": 0, "health": 0 },
      "uptimeMs": 0
    },
    "policy": { "maxPayload": 1048576, "maxBufferedBytes": 1048576, "tickIntervalMs": 30000 }
  }
}
```

Request + response:

```json
{ "type": "req", "id": "r1", "method": "health" }
```

```json
{ "type": "res", "id": "r1", "ok": true, "payload": { "ok": true } }
```

Event:

```json
{ "type": "event", "event": "tick", "payload": { "ts": 1730000000 }, "seq": 12 }
```

## Minimal client (Python)

Smallest useful flow: connect + health.

```python
import asyncio
import json
import websockets

async def main():
    async with websockets.connect("ws://127.0.0.1:18789") as ws:
        # Connect
        await ws.send(json.dumps({
            "type": "req",
            "id": "c1",
            "method": "connect",
            "params": {
                "minProtocol": 3,
                "maxProtocol": 3,
                "client": {
                    "id": "cli",
                    "displayName": "example",
                    "version": "dev",
                    "platform": "python",
                    "mode": "cli",
                },
            },
        }))
        msg = json.loads(await ws.recv())
        if msg["type"] == "res" and msg["id"] == "c1" and msg["ok"]:
            await ws.send(json.dumps({"type": "req", "id": "h1", "method": "health"}))
        msg = json.loads(await ws.recv())
        if msg["type"] == "res" and msg["id"] == "h1":
            print("health:", msg["payload"])

asyncio.run(main())
```

## Worked example: add a method end‑to‑end

Example: add a new `system.echo` request that returns `{ ok: true, text }`.

1. **Schema (source of truth)**

Define input/output shapes (using dataclasses or dicts):

```python
from dataclasses import dataclass

@dataclass
class SystemEchoParams:
    text: str

@dataclass
class SystemEchoResult:
    ok: bool
    text: str
```

2. **Validation**

Validate inbound params before dispatch:

```python
def validate_system_echo_params(params: dict) -> SystemEchoParams:
    if not isinstance(params.get("text"), str) or not params["text"]:
        raise ValueError("text is required")
    return SystemEchoParams(text=params["text"])
```

3. **Server behavior**

Add a handler in the gateway server module:

```python
def handle_system_echo(params: dict, respond) -> None:
    p = validate_system_echo_params(params)
    respond(True, {"ok": True, "text": p.text})
```

Register it in the method dispatch table and add `"system.echo"` to `METHODS`.

4. **Regenerate**

```bash
python -m openclaw.gateway.protocol.gen
```

5. **Tests + docs**

Add a server test and note the method in docs.

## Versioning + compatibility

- `PROTOCOL_VERSION` lives in the protocol schema module.
- Clients send `minProtocol` + `maxProtocol`; the server rejects mismatches.
- Unknown frame types are preserved as raw payloads for forward compatibility.

## Schema patterns and conventions

- Most objects use strict validation (no extra fields) for strict payloads.
- Non-empty string is the default for IDs and method/event names.
- The top-level frame uses a **discriminator** on `type`.
- Methods with side effects usually require an `idempotency_key` in params
  (example: `send`, `poll`, `agent`, `chat.send`).

## Live schema JSON

Generated JSON Schema is in the repo at `dist/protocol.schema.json`. The
published raw file is typically available at:

- [https://raw.githubusercontent.com/openclaw/openclaw/main/dist/protocol.schema.json](https://raw.githubusercontent.com/openclaw/openclaw/main/dist/protocol.schema.json)

## When you change schemas

1. Update the schema definitions.
2. Run `python -m openclaw.gateway.protocol.gen`.
3. Commit the regenerated schema.
