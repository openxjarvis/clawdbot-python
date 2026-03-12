---
summary: "Configuration overview: common tasks, quick setup, and links to the full reference"
read_when:
  - Setting up OpenClaw for the first time
  - Looking for common configuration patterns
  - Navigating to specific config sections
title: "Configuration"
---

# Configuration

OpenClaw reads an optional **JSON** config from `~/.openclaw/openclaw.json`.

If the file is missing, OpenClaw uses safe defaults. Common reasons to add a config:

- Connect channels and control who can message the bot
- Set models, tools, sandboxing, or automation (cron, hooks)
- Tune sessions, media, networking, or UI

See the [full reference](/gateway/configuration-reference) for every available field.

> **New to configuration?** Start with `openclaw onboard` for interactive setup, or check out the [Configuration Examples](/gateway/configuration-examples) guide for complete copy-paste configs.

## Minimal config

```json
{
  "agents": { "defaults": { "workspace": "~/.openclaw/workspace" } },
  "channels": { "whatsapp": { "allowFrom": ["+15555550123"] } }
}
```

## Editing config

**Interactive wizard:**
```bash
openclaw onboard       # full setup wizard
openclaw configure     # config wizard
```

**CLI (one-liners):**
```bash
openclaw config get agents.defaults.workspace
openclaw config set agents.defaults.heartbeat.every "2h"
openclaw config unset tools.web.search.apiKey
```

**Control UI:**
Open [http://127.0.0.1:18789](http://127.0.0.1:18789) and use the **Config** tab.
The Control UI renders a form from the config schema, with a **Raw JSON** editor as an escape hatch.

**Direct edit:**
Edit `~/.openclaw/openclaw.json` directly. The Gateway watches the file and applies changes automatically (see [hot reload](#config-hot-reload)).

## Strict validation

> **Warning:** OpenClaw only accepts configurations that fully match the schema. Unknown keys, malformed types, or invalid values cause the Gateway to **refuse to start**. The only root-level exception is `$schema` (string), so editors can attach JSON Schema metadata.

When validation fails:

- The Gateway does not boot
- Only diagnostic commands work (`openclaw doctor`, `openclaw logs`, `openclaw health`, `openclaw status`)
- Run `openclaw doctor` to see exact issues
- Run `openclaw doctor --fix` (or `--yes`) to apply repairs

## Common tasks

### Set up a channel (WhatsApp, Telegram, Discord, etc.)

Each channel has its own config section under `channels.<provider>`. See the dedicated channel page for setup steps:

- [WhatsApp](/channels/whatsapp) — `channels.whatsapp`
- [Telegram](/channels/telegram) — `channels.telegram`
- [Discord](/channels/discord) — `channels.discord`
- [Slack](/channels/slack) — `channels.slack`
- [Signal](/channels/signal) — `channels.signal`
- [iMessage](/channels/imessage) — `channels.imessage`
- [Google Chat](/channels/googlechat) — `channels.googlechat`
- [Mattermost](/channels/mattermost) — `channels.mattermost`
- [MS Teams](/channels/msteams) — `channels.msteams`

All channels share the same DM policy pattern:

```json
{
  "channels": {
    "telegram": {
      "enabled": true,
      "botToken": "123:abc",
      "dmPolicy": "pairing",
      "allowFrom": ["tg:123"]
    }
  }
}
```

### Choose and configure models

Set the primary model and optional fallbacks:

```json
{
  "agents": {
    "defaults": {
      "model": {
        "primary": "anthropic/claude-sonnet-4-5",
        "fallbacks": ["openai/gpt-5.2"]
      },
      "models": {
        "anthropic/claude-sonnet-4-5": { "alias": "Sonnet" },
        "openai/gpt-5.2": { "alias": "GPT" }
      }
    }
  }
}
```

- `agents.defaults.models` defines the model catalog and acts as the allowlist for `/model`.
- Model refs use `provider/model` format (e.g. `anthropic/claude-opus-4-6`).
- `agents.defaults.imageMaxDimensionPx` controls transcript/tool image downscaling (default `1200`).
- See [Models CLI](/concepts/models) for switching models in chat.
- For custom/self-hosted providers, see [Custom providers](/gateway/configuration-reference#custom-providers-and-base-urls) in the reference.

### Control who can message the bot

DM access is controlled per channel via `dmPolicy`:

- `"pairing"` (default): unknown senders get a one-time pairing code to approve
- `"allowlist"`: only senders in `allowFrom` (or the paired allow store)
- `"open"`: allow all inbound DMs (requires `allowFrom: ["*"]`)
- `"disabled"`: ignore all DMs

### Enable sandboxing

Run agent sessions in isolated Docker containers:

```json
{
  "agents": {
    "defaults": {
      "sandbox": {
        "mode": "non-main",
        "scope": "agent"
      }
    }
  }
}
```

Build the image first: `scripts/sandbox-setup.sh`

See [Sandboxing](/gateway/sandboxing) for the full guide.

### Set up heartbeat (periodic check-ins)

```json
{
  "agents": {
    "defaults": {
      "heartbeat": {
        "every": "30m",
        "target": "last"
      }
    }
  }
}
```

### Split config into multiple files ($include)

Use `$include` to organize large configs:

```json
{
  "gateway": { "port": 18789 },
  "agents": { "$include": "./agents.json" },
  "broadcast": {
    "$include": ["./clients/a.json", "./clients/b.json"]
  }
}
```

- **Single file**: replaces the containing object
- **Array of files**: deep-merged in order (later wins)
- **Sibling keys**: merged after includes (override included values)
- **Nested includes**: supported up to 10 levels deep
- **Relative paths**: resolved relative to the including file

## Config hot reload

The Gateway watches `~/.openclaw/openclaw.json` and applies changes automatically — no manual restart needed for most settings.

### Reload modes

| Mode                   | Behavior                                                                                |
| ---------------------- | --------------------------------------------------------------------------------------- |
| **`hybrid`** (default) | Hot-applies safe changes instantly. Automatically restarts for critical ones.           |
| **`hot`**              | Hot-applies safe changes only. Logs a warning when a restart is needed — you handle it. |
| **`restart`**          | Restarts the Gateway on any config change, safe or not.                                 |
| **`off`**              | Disables file watching. Changes take effect on the next manual restart.                 |

```json
{
  "gateway": {
    "reload": { "mode": "hybrid", "debounceMs": 300 }
  }
}
```

### What hot-applies vs what needs a restart

| Category            | Fields                                                               | Restart needed? |
| ------------------- | -------------------------------------------------------------------- | --------------- |
| Channels            | `channels.*`, `web` (WhatsApp) — all built-in and extension channels | No              |
| Agent & models      | `agent`, `agents`, `models`, `routing`                               | No              |
| Automation          | `hooks`, `cron`, `agent.heartbeat`                                   | No              |
| Sessions & messages | `session`, `messages`                                                | No              |
| Tools & media       | `tools`, `browser`, `skills`, `audio`, `talk`                        | No              |
| UI & misc           | `ui`, `logging`, `identity`, `bindings`                              | No              |
| Gateway server      | `gateway.*` (port, bind, auth, tailscale, TLS, HTTP)                 | **Yes**         |
| Infrastructure      | `discovery`, `canvasHost`, `plugins`                                 | **Yes**         |

> `gateway.reload` and `gateway.remote` are exceptions — changing them does **not** trigger a restart.

## Config RPC (programmatic updates)

### config.apply (full replace)

Validates + writes the full config and restarts the Gateway in one step.

> **Warning:** `config.apply` replaces the **entire config**. Use `config.patch` for partial updates, or `openclaw config set` for single keys.

Params:

- `raw` (str) — JSON payload for the entire config
- `baseHash` (optional) — config hash from `config.get` (required when config exists)
- `sessionKey` (optional) — session key for the post-restart wake-up ping
- `note` (optional) — note for the restart sentinel
- `restartDelayMs` (optional) — delay before restart (default 2000)

```bash
openclaw gateway call config.get --params '{}'  # capture payload.hash
openclaw gateway call config.apply --params '{
  "raw": "{ \"agents\": { \"defaults\": { \"workspace\": \"~/.openclaw/workspace\" } } }",
  "baseHash": "<hash>",
  "sessionKey": "agent:main:whatsapp:dm:+15555550123"
}'
```

### config.patch (partial update)

Merges a partial update into the existing config (JSON merge patch semantics):

- Objects merge recursively
- `null` deletes a key
- Arrays replace

Params:

- `raw` (str) — JSON with just the keys to change
- `baseHash` (required) — config hash from `config.get`
- `sessionKey`, `note`, `restartDelayMs` — same as `config.apply`

```bash
openclaw gateway call config.patch --params '{
  "raw": "{ \"channels\": { \"telegram\": { \"groups\": { \"*\": { \"requireMention\": false } } } } }",
  "baseHash": "<hash>"
}'
```

## Environment variables

OpenClaw reads env vars from the parent process plus:

- `.env` from the current working directory (if present)
- `~/.openclaw/.env` (global fallback)

Neither file overrides existing env vars. You can also set inline env vars in config:

```json
{
  "env": {
    "OPENROUTER_API_KEY": "sk-or-...",
    "vars": { "GROQ_API_KEY": "gsk-..." }
  }
}
```

**Shell env import (optional):**

If enabled and expected keys aren't set, OpenClaw runs your login shell and imports only the missing keys:

```json
{
  "env": {
    "shellEnv": { "enabled": true, "timeoutMs": 15000 }
  }
}
```

Env var equivalent: `OPENCLAW_LOAD_SHELL_ENV=1`

**Env var substitution in config values:**

Reference env vars in any config string value with `${VAR_NAME}`:

```json
{
  "gateway": { "auth": { "token": "${OPENCLAW_GATEWAY_TOKEN}" } },
  "models": { "providers": { "custom": { "apiKey": "${CUSTOM_API_KEY}" } } }
}
```

Rules:

- Only uppercase names matched: `[A-Z_][A-Z0-9_]*`
- Missing/empty vars throw an error at load time
- Escape with `$${VAR}` for literal output
- Works inside `$include` files

See [Environment](/help/environment) for full precedence and sources.

## Config notes (Python)

- The Python gateway uses standard **JSON** (not JSON5). Comments and trailing commas are not supported.
- `bootstrapMaxChars` and `bootstrapTotalMaxChars` are documented in `agents.defaults` — these keys are referenced in the docs and the Python project uses them for workspace bootstrap file size controls.

## Full reference

For the complete field-by-field reference, see **[Configuration Reference](/gateway/configuration-reference)**.

---

_Related: [Configuration Examples](/gateway/configuration-examples) · [Configuration Reference](/gateway/configuration-reference) · [Doctor](/gateway/doctor)_
