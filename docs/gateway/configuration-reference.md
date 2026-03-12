---
title: "Configuration Reference"
description: "Complete field-by-field reference for ~/.openclaw/openclaw.json"
---

# Configuration Reference

Every field available in `~/.openclaw/openclaw.json`. For a task-oriented overview, see [Configuration](/gateway/configuration).

Config format is **JSON** (standard JSON; comments and trailing commas not allowed in the Python gateway). All fields are optional — OpenClaw uses safe defaults when omitted.

---

## Channels

Each channel starts automatically when its config section exists (unless `enabled: false`).

### DM and group access

All channels support DM policies and group policies:

| DM policy           | Behavior                                                        |
| ------------------- | --------------------------------------------------------------- |
| `pairing` (default) | Unknown senders get a one-time pairing code; owner must approve |
| `allowlist`         | Only senders in `allowFrom` (or paired allow store)             |
| `open`              | Allow all inbound DMs (requires `allowFrom: ["*"]`)             |
| `disabled`          | Ignore all inbound DMs                                          |

| Group policy          | Behavior                                               |
| --------------------- | ------------------------------------------------------ |
| `allowlist` (default) | Only groups matching the configured allowlist          |
| `open`                | Bypass group allowlists (mention-gating still applies) |
| `disabled`            | Block all group/room messages                          |

> `channels.defaults.groupPolicy` sets the default when a provider's `groupPolicy` is unset.
> Pairing codes expire after 1 hour. Pending DM pairing requests are capped at **3 per channel**.

### WhatsApp

```json
{
  "channels": {
    "whatsapp": {
      "dmPolicy": "pairing",
      "allowFrom": ["+15555550123", "+447700900123"],
      "textChunkLimit": 4000,
      "chunkMode": "length",
      "mediaMaxMb": 50,
      "sendReadReceipts": true,
      "groups": {
        "*": { "requireMention": true }
      },
      "groupPolicy": "allowlist",
      "groupAllowFrom": ["+15551234567"]
    }
  }
}
```

### Telegram

```json
{
  "channels": {
    "telegram": {
      "enabled": true,
      "botToken": "your-bot-token",
      "dmPolicy": "pairing",
      "allowFrom": ["tg:123456789"],
      "groups": {
        "*": { "requireMention": true }
      },
      "historyLimit": 50,
      "replyToMode": "first",
      "streamMode": "partial",
      "mediaMaxMb": 5
    }
  }
}
```

### Discord

```json
{
  "channels": {
    "discord": {
      "enabled": true,
      "token": "your-bot-token",
      "mediaMaxMb": 8,
      "allowBots": false,
      "dmPolicy": "pairing",
      "allowFrom": ["1234567890", "steipete"],
      "guilds": {
        "123456789012345678": {
          "slug": "friends-of-openclaw",
          "requireMention": false,
          "channels": {
            "general": { "allow": true },
            "help": { "allow": true, "requireMention": true }
          }
        }
      },
      "textChunkLimit": 2000
    }
  }
}
```

### Slack

```json
{
  "channels": {
    "slack": {
      "enabled": true,
      "botToken": "xoxb-...",
      "appToken": "xapp-...",
      "dmPolicy": "pairing",
      "allowFrom": ["U123", "U456"],
      "channels": {
        "C123": { "allow": true, "requireMention": true }
      },
      "historyLimit": 50,
      "textChunkLimit": 4000
    }
  }
}
```

### Multi-account (all channels)

```json
{
  "channels": {
    "telegram": {
      "accounts": {
        "default": {
          "name": "Primary bot",
          "botToken": "123456:ABC..."
        },
        "alerts": {
          "name": "Alerts bot",
          "botToken": "987654:XYZ..."
        }
      }
    }
  }
}
```

---

## Agent defaults

### `agents.defaults.workspace`

Default: `~/.openclaw/workspace`.

```json
{
  "agents": { "defaults": { "workspace": "~/.openclaw/workspace" } }
}
```

### `agents.defaults.bootstrapMaxChars`

Max characters per workspace bootstrap file before truncation. Default: `20000`.

```json
{
  "agents": { "defaults": { "bootstrapMaxChars": 20000 } }
}
```

### `agents.defaults.bootstrapTotalMaxChars`

Max total characters injected across all workspace bootstrap files. Default: `150000`.

```json
{
  "agents": { "defaults": { "bootstrapTotalMaxChars": 150000 } }
}
```

### `agents.defaults.model`

```json
{
  "agents": {
    "defaults": {
      "models": {
        "anthropic/claude-opus-4-6": { "alias": "opus" }
      },
      "model": {
        "primary": "anthropic/claude-opus-4-6",
        "fallbacks": ["openai/gpt-5.2"]
      },
      "thinkingDefault": "low",
      "timeoutSeconds": 600,
      "maxConcurrent": 3
    }
  }
}
```

### `agents.defaults.heartbeat`

Periodic heartbeat runs.

```json
{
  "agents": {
    "defaults": {
      "heartbeat": {
        "every": "30m",
        "model": "anthropic/claude-opus-4-6",
        "target": "last",
        "to": "+15555550123",
        "prompt": "Read HEARTBEAT.md if it exists...",
        "ackMaxChars": 300
      }
    }
  }
}
```

### `agents.defaults.sandbox`

Optional **Docker sandboxing** for the embedded agent. See [Sandboxing](/gateway/sandboxing).

```json
{
  "agents": {
    "defaults": {
      "sandbox": {
        "mode": "non-main",
        "scope": "agent",
        "workspaceAccess": "none",
        "workspaceRoot": "~/.openclaw/sandboxes",
        "docker": {
          "image": "openclaw-sandbox:bookworm-slim",
          "containerPrefix": "openclaw-sbx-",
          "workdir": "/workspace",
          "readOnlyRoot": true,
          "tmpfs": ["/tmp", "/var/tmp", "/run"],
          "network": "none",
          "user": "1000:1000",
          "capDrop": ["ALL"],
          "env": { "LANG": "C.UTF-8" },
          "pidsLimit": 256,
          "memory": "1g",
          "cpus": 1
        }
      }
    }
  }
}
```

Build images:

```bash
scripts/sandbox-setup.sh           # main sandbox image
scripts/sandbox-browser-setup.sh   # optional browser image
```

### `agents.list` (per-agent overrides)

```json
{
  "agents": {
    "list": [
      {
        "id": "main",
        "default": true,
        "name": "Main Agent",
        "workspace": "~/.openclaw/workspace",
        "model": "anthropic/claude-opus-4-6",
        "identity": {
          "name": "Samantha",
          "theme": "helpful sloth",
          "emoji": "🦥"
        },
        "sandbox": { "mode": "off" }
      }
    ]
  }
}
```

---

## Multi-agent routing

```json
{
  "agents": {
    "list": [
      { "id": "home", "default": true, "workspace": "~/.openclaw/workspace-home" },
      { "id": "work", "workspace": "~/.openclaw/workspace-work" }
    ]
  },
  "bindings": [
    { "agentId": "home", "match": { "channel": "whatsapp", "accountId": "personal" } },
    { "agentId": "work", "match": { "channel": "whatsapp", "accountId": "biz" } }
  ]
}
```

---

## Session

```json
{
  "session": {
    "dmScope": "per-channel-peer",
    "reset": {
      "mode": "daily",
      "atHour": 4,
      "idleMinutes": 60
    },
    "resetTriggers": ["/new", "/reset"],
    "store": "~/.openclaw/agents/{agentId}/sessions/sessions.json",
    "maintenance": {
      "mode": "warn",
      "pruneAfter": "30d",
      "maxEntries": 500,
      "rotateBytes": "10mb"
    }
  }
}
```

---

## Messages

```json
{
  "messages": {
    "responsePrefix": "🦞",
    "ackReaction": "👀",
    "ackReactionScope": "group-mentions",
    "removeAckAfterReply": false,
    "queue": {
      "mode": "collect",
      "debounceMs": 1000,
      "cap": 20,
      "drop": "summarize"
    }
  }
}
```

---

## Tools

### Tool profiles

`tools.profile` sets a base allowlist before `tools.allow`/`tools.deny`:

| Profile     | Includes                                                                                  |
| ----------- | ----------------------------------------------------------------------------------------- |
| `minimal`   | `session_status` only                                                                     |
| `coding`    | `group:fs`, `group:runtime`, `group:sessions`, `group:memory`, `image`                    |
| `messaging` | `group:messaging`, `sessions_list`, `sessions_history`, `sessions_send`, `session_status` |
| `full`      | No restriction (same as unset)                                                            |

### `tools.allow` / `tools.deny`

```json
{
  "tools": { "deny": ["browser", "canvas"] }
}
```

### `tools.elevated`

```json
{
  "tools": {
    "elevated": {
      "enabled": true,
      "allowFrom": {
        "whatsapp": ["+15555550123"],
        "discord": ["steipete"]
      }
    }
  }
}
```

### `tools.exec`

```json
{
  "tools": {
    "exec": {
      "backgroundMs": 10000,
      "timeoutSec": 1800,
      "cleanupMs": 1800000,
      "notifyOnExit": true,
      "notifyOnExitEmptySuccess": false
    }
  }
}
```

### `tools.web`

```json
{
  "tools": {
    "web": {
      "search": {
        "enabled": true,
        "apiKey": "brave_api_key",
        "maxResults": 5,
        "timeoutSeconds": 30,
        "cacheTtlMinutes": 15
      },
      "fetch": {
        "enabled": true,
        "maxChars": 50000,
        "timeoutSeconds": 30
      }
    }
  }
}
```

---

## Custom providers and base URLs

```json
{
  "models": {
    "mode": "merge",
    "providers": {
      "custom-proxy": {
        "baseUrl": "http://localhost:4000/v1",
        "apiKey": "LITELLM_KEY",
        "api": "openai-completions",
        "models": [
          {
            "id": "llama-3.1-8b",
            "name": "Llama 3.1 8B",
            "reasoning": false,
            "input": ["text"],
            "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
            "contextWindow": 128000,
            "maxTokens": 32000
          }
        ]
      }
    }
  }
}
```

---

## Skills

```json
{
  "skills": {
    "allowBundled": ["gemini", "peekaboo"],
    "load": {
      "extraDirs": ["~/Projects/agent-scripts/skills"]
    },
    "install": {
      "preferBrew": true,
      "nodeManager": "pip"
    },
    "entries": {
      "peekaboo": { "enabled": true }
    }
  }
}
```

---

## Plugins

```json
{
  "plugins": {
    "enabled": true,
    "allow": ["voice-call"],
    "deny": [],
    "load": {
      "paths": ["~/Projects/oss/voice-call-extension"]
    },
    "entries": {
      "voice-call": {
        "enabled": true,
        "config": { "provider": "twilio" }
      }
    }
  }
}
```

Plugins are loaded from `~/.openclaw/extensions`, `<workspace>/.openclaw/extensions`, plus `plugins.load.paths`. **Config changes require a gateway restart.**

---

## Gateway

```json
{
  "gateway": {
    "mode": "local",
    "port": 18789,
    "bind": "loopback",
    "auth": {
      "mode": "token",
      "token": "your-token",
      "allowTailscale": true,
      "rateLimit": {
        "maxAttempts": 10,
        "windowMs": 60000,
        "lockoutMs": 300000,
        "exemptLoopback": true
      }
    },
    "tailscale": {
      "mode": "off",
      "resetOnExit": false
    },
    "controlUi": {
      "enabled": true,
      "basePath": "/openclaw"
    },
    "remote": {
      "url": "ws://gateway.tailnet:18789",
      "transport": "ssh",
      "token": "your-token"
    },
    "trustedProxies": ["10.0.0.1"],
    "tools": {
      "deny": ["browser"],
      "allow": ["gateway"]
    }
  }
}
```

### OpenAI-compatible endpoints

- Chat Completions: disabled by default. Enable with `gateway.http.endpoints.chatCompletions.enabled: true`.
- Responses API: `gateway.http.endpoints.responses.enabled`.

### Multi-instance isolation

```bash
OPENCLAW_CONFIG_PATH=~/.openclaw/a.json \
OPENCLAW_STATE_DIR=~/.openclaw-a \
python -m openclaw gateway --port 19001
```

---

## Hooks

```json
{
  "hooks": {
    "enabled": true,
    "token": "shared-secret",
    "path": "/hooks",
    "defaultSessionKey": "hook:ingress",
    "allowRequestSessionKey": false,
    "allowedSessionKeyPrefixes": ["hook:"],
    "mappings": [
      {
        "match": { "path": "gmail" },
        "action": "agent",
        "agentId": "main",
        "deliver": true
      }
    ]
  }
}
```

---

## Logging

```json
{
  "logging": {
    "level": "info",
    "file": "/tmp/openclaw/openclaw.log",
    "consoleLevel": "info",
    "consoleStyle": "pretty",
    "redactSensitive": "tools"
  }
}
```

---

## Discovery

### mDNS (Bonjour)

```json
{
  "discovery": {
    "mdns": {
      "mode": "minimal"
    }
  }
}
```

- `minimal` (default): omit `cliPath` + `sshPort` from TXT records.
- `full`: include `cliPath` + `sshPort`.

---

## Environment

```json
{
  "env": {
    "OPENROUTER_API_KEY": "sk-or-...",
    "vars": {
      "GROQ_API_KEY": "gsk-..."
    },
    "shellEnv": {
      "enabled": true,
      "timeoutMs": 15000
    }
  }
}
```

---

## Cron

```json
{
  "cron": {
    "enabled": true,
    "maxConcurrentRuns": 2,
    "sessionRetention": "24h"
  }
}
```

---

## Config includes (`$include`)

```json
{
  "gateway": { "port": 18789 },
  "agents": { "$include": "./agents.json" },
  "broadcast": {
    "$include": ["./clients/a.json", "./clients/b.json"]
  }
}
```

---

_Related: [Configuration](/gateway/configuration) · [Configuration Examples](/gateway/configuration-examples) · [Doctor](/gateway/doctor)_
