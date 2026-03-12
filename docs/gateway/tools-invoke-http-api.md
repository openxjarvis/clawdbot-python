---
summary: "Invoke a single tool directly via the Gateway HTTP endpoint"
read_when:
  - Calling tools without running a full agent turn
  - Building automations that need tool policy enforcement
title: "Tools Invoke API"
---

# Tools Invoke (HTTP)

OpenClaw's Gateway exposes a simple HTTP endpoint for invoking a single tool directly. It is always enabled, but gated by Gateway auth and tool policy.

- `POST /tools/invoke`
- Same port as the Gateway (WS + HTTP multiplex): `http://<gateway-host>:<port>/tools/invoke`

Default max payload size is 2 MB.

## Authentication

Uses the Gateway auth configuration. Send a bearer token:

- `Authorization: Bearer <token>`

Notes:

- When `gateway.auth.mode="token"`, use `gateway.auth.token` (or `OPENCLAW_GATEWAY_TOKEN`).
- When `gateway.auth.mode="password"`, use `gateway.auth.password` (or `OPENCLAW_GATEWAY_PASSWORD`).

## Request body

```json
{
  "tool": "sessions_list",
  "action": "json",
  "args": {},
  "sessionKey": "main",
  "dryRun": false
}
```

Fields:

- `tool` (string, required): tool name to invoke.
- `action` (string, optional): merged into args if the tool schema supports an `action` property and the caller omitted it.
- `args` (object, optional): tool-specific arguments.
- `sessionKey` (string, optional): target session key. Defaults to the main session key.
- `dryRun` (boolean, optional): reserved for future use.

## Policy + routing behavior

Tool availability is filtered through the policy chain:

- `tools.allow` / `tools.deny` (gateway config)
- Per-agent policies (when session key maps to an agent session)

### Default HTTP deny list

Even if session policy allows a tool, these tools are always blocked over HTTP:

- `sessions_spawn`
- `sessions_send`
- `gateway`
- `whatsapp_login`

Customize via `gateway.tools`:

```json5
{
  gateway: {
    tools: {
      deny: ["browser"],   // Additional tools to block
      allow: ["gateway"],  // Remove from default deny list
    },
  },
}
```

To help group policies resolve context, you can optionally pass headers:

- `x-openclaw-message-channel: <channel>` (e.g. `slack`, `telegram`)
- `x-openclaw-account-id: <accountId>`

## Responses

- `200` → `{ ok: true, result, details? }`
- `400` → `{ ok: false, error: { code, message } }` (invalid request)
- `403` → `{ ok: false, error: { code, message } }` (tool denied by policy)
- `404` → tool not found
- `500` → `{ ok: false, error: { code, message } }` (execution error)

## Example

```bash
curl -sS http://127.0.0.1:18789/tools/invoke \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{
    "tool": "sessions_list",
    "action": "json",
    "args": {}
  }'
```

## Python implementation

- **`openclaw/gateway/http/tools_invoke.py`** — `handle_tool_invoke_request()`, `ToolInvokeRequest`, `ToolInvokeResponse`, `DEFAULT_GATEWAY_HTTP_TOOL_DENY`, `check_tool_policy()`, `_merge_action_into_args()`.
