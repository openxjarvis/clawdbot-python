---
summary: "OpenClaw Python configuration reference"
read_when:
  - Looking up all available config options
  - Checking config field types and defaults
title: "Configuration Reference"
---

# Configuration Reference (`openclaw.json`)

Full reference for `~/.openclaw/openclaw.json` (JSON5 format).

## Top-level structure

```json5
{
  agents: {
    defaults: { ... },
    list: [ ... ],
  },
  channels: { ... },
  models: { ... },
  plugins: { ... },
  session: { ... },
  cron: { ... },
  webhook: { ... },
  gateway: { ... },
  skills: { ... },
  messages: { ... },
  tools: { ... },
}
```

## `agents.defaults`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `workspace` | string | `~/.openclaw/workspace` | Agent workspace directory |
| `model` | string | — | Model ref (`provider/model`) |
| `agentId` | string | `"main"` | Default agent ID |
| `blockStreamingDefault` | string | `"off"` | Default streaming mode |
| `compaction.reserveTokensFloor` | number | 20000 | Min token reserve before compaction |

## `channels`

Each channel key is the channel slug (e.g. `telegram`, `discord`, `slack`).
See channel-specific docs for available fields.

## `models.providers`

| Provider key | Fields |
|-------------|--------|
| `anthropic` | `apiKey`, `baseUrl` |
| `openai` | `apiKey`, `baseUrl`, `organization` |
| `google` | `apiKey` |
| `ollama` | `baseUrl` |
| `openrouter` | `apiKey` |
| `bedrock` | `region`, `accessKeyId`, `secretAccessKey` |

## `plugins`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | boolean | `true` | Enable the plugin system |
| `allow` | string[] | — | Allowlist of plugin IDs |
| `deny` | string[] | — | Denylist of plugin IDs |
| `loadPaths` | string[] | — | Extra plugin search paths |
| `slots.memory` | string | `"memory-core"` | Active memory plugin ID or `"none"` |
| `entries.<id>.enabled` | boolean | — | Enable/disable a specific plugin |
| `entries.<id>.config` | object | — | Plugin-specific config (validated by plugin's configSchema) |

## `session`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `dmScope` | string | `"main"` | DM session scoping mode |
| `reset.mode` | string | `"daily"` | Reset mode (`daily`, `idle`, `off`) |
| `reset.atHour` | number | `4` | Daily reset hour (local time) |
| `reset.idleMinutes` | number | — | Idle reset window |
| `mainKey` | string | `"main"` | Main session key name |

## `cron`

```json5
{
  cron: {
    jobs: [
      {
        id: "job-id",      // unique job id
        schedule: "0 9 * * *",  // crontab
        agentId: "main",   // target agent
        prompt: "...",     // injection prompt
        timezone: "UTC",   // IANA timezone
      },
    ],
  },
}
```

## `gateway`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `host` | string | `"127.0.0.1"` | Bind address |
| `port` | number | `8080` | Listen port |
| `auth.type` | string | `"none"` | Auth type (`none` or `token`) |
| `auth.token` | string | — | Auth token |
| `logLevel` | string | `"info"` | Log level |

## Config file location

- Default: `~/.openclaw/openclaw.json`
- Override: `OPENCLAW_CONFIG` environment variable
- CLI: `openclaw config edit`
