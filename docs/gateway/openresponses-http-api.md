---
summary: "Expose an OpenResponses-compatible /v1/responses HTTP endpoint from the Gateway"
read_when:
  - Integrating clients that speak the OpenResponses API
title: "OpenResponses API"
---

# OpenResponses API (HTTP)

OpenClaw's Gateway can serve an OpenResponses-compatible `POST /v1/responses` endpoint.

Disabled by default. Enable via config:

```json5
{
  gateway: {
    http: {
      endpoints: {
        responses: { enabled: true },
      },
    },
  },
}
```

## Python implementation

- `openclaw/gateway/http/responses.py` — `ResponsesRequest`, `handle_responses_request()`
- Route registered in `GatewayServer._handle_responses_route()` when enabled

## Supported input types

- `input`: string or items array (`message`, `function_call_output`)
- `instructions`: merged into system prompt
- `tools`: client-side function tools
- `stream`: not yet implemented (returns non-streaming JSON)
- `user`: stable session routing

## Session routing

- Stateless per request by default (ephemeral session key)
- Stable session when `user` is set (derived from SHA-256 hash of user string)
  - Session key format: `agent:<id>:responses:<16-hex>`

## Response shape

```json
{
  "id": "resp_<24-hex>",
  "object": "response",
  "created_at": 1234567890,
  "status": "completed",
  "model": "openclaw",
  "output": [
    {
      "type": "message",
      "role": "assistant",
      "content": [{"type": "output_text", "text": "..."}]
    }
  ]
}
```

## Authentication

Same as `/v1/chat/completions` — bearer token via `Authorization: Bearer <token>`.
