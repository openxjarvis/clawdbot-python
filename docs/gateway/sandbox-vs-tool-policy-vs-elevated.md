---
title: Sandbox vs Tool Policy vs Elevated
summary: "Why a tool is blocked: sandbox runtime, tool allow/deny policy, and elevated exec gates"
read_when: "You hit a sandbox restriction or see a tool/elevated refusal and want the exact config key to change."
---

# Sandbox vs Tool Policy vs Elevated

OpenClaw has three related (but different) controls:

1. **Sandbox** (`agents.defaults.sandbox.*` / `agents.list[].sandbox.*`) decides **where tools run** (Docker vs host).
2. **Tool policy** (`tools.*`, `agents.list[].tools.*`) decides **which tools are available/allowed**.
3. **Elevated** (`tools.elevated.*`, `agents.list[].tools.elevated.*`) is an **exec-only escape hatch** to run on the host when you're sandboxed.

## Quick debug

```bash
openclaw sandbox explain
openclaw sandbox explain --agent work
openclaw sandbox explain --json
```

It prints:

- Effective sandbox mode/scope/workspace access.
- Whether the session is currently sandboxed.
- Effective tool allow/deny (and whether it came from agent/global/default).
- Elevated gates and fix-it key paths.

## Sandbox: where tools run

Sandboxing is controlled by `agents.defaults.sandbox.mode`:

- `"off"`: everything runs on the host.
- `"non-main"`: only non-main sessions are sandboxed.
- `"all"`: everything is sandboxed.

See [Sandboxing](/gateway/sandboxing) for the full matrix.

### Bind mounts (security quick check)

- `docker.binds` pierces the sandbox filesystem: whatever you mount is visible inside
  the container.
- `scope: "shared"` ignores per-agent binds (only global binds apply).

## Tool policy: which tools exist/are callable

Two layers matter:

- **Tool profile**: `tools.profile` (base allowlist)
- **Global/per-agent tool policy**: `tools.allow`/`tools.deny` and `agents.list[].tools.allow/deny`
- **Sandbox tool policy** (only applies when sandboxed): `tools.sandbox.tools.allow/deny`

### HTTP tool policy

HTTP requests to `POST /tools/invoke` are additionally constrained by:

- `DEFAULT_GATEWAY_HTTP_TOOL_DENY` — permanently blocked over HTTP: `sessions_spawn`, `sessions_send`, `gateway`, `whatsapp_login`.
- `gateway.tools.deny[]` — configurable deny list.
- `gateway.tools.allow[]` — configurable allow list (if set, only listed tools are accessible over HTTP).

See [Tools Invoke HTTP API](/gateway/tools-invoke-http-api).

## Elevated: host exec when sandboxed

Elevated tools let you call specific commands on the host even when the session is sandboxed.
Controlled by `tools.elevated.*`.

## Python implementation

- `openclaw/agents/tools/` — tool implementations with sandbox awareness
- `openclaw/gateway/http/tools_invoke.py` — HTTP tool policy enforcement
- `openclaw/sandbox/` — sandbox runtime management

## Related docs

- [Sandboxing](/gateway/sandboxing)
- [Tools Invoke HTTP API](/gateway/tools-invoke-http-api)
