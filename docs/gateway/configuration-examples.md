---
summary: "Schema-accurate configuration examples for common OpenClaw setups"
read_when:
  - Learning how to configure OpenClaw
  - Looking for configuration examples
  - Setting up OpenClaw for the first time
title: "Configuration Examples"
---

# Configuration Examples

Examples below are aligned with the current config schema. For the exhaustive reference and per-field notes, see [Configuration](/gateway/configuration).

> **Note:** The Python gateway uses standard **JSON** (not JSON5). Comments and trailing commas are not supported. Save all configs as valid JSON.

## Quick start

### Absolute minimum

```json
{
  "agent": { "workspace": "~/.openclaw/workspace" },
  "channels": { "whatsapp": { "allowFrom": ["+15555550123"] } }
}
```

Save to `~/.openclaw/openclaw.json` and you can DM the bot from that number.

### Recommended starter

```json
{
  "identity": {
    "name": "Clawd",
    "theme": "helpful assistant",
    "emoji": "🦞"
  },
  "agent": {
    "workspace": "~/.openclaw/workspace",
    "model": { "primary": "anthropic/claude-sonnet-4-5" }
  },
  "channels": {
    "whatsapp": {
      "allowFrom": ["+15555550123"],
      "groups": { "*": { "requireMention": true } }
    }
  }
}
```

## Expanded example (major options)

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
  },

  "identity": {
    "name": "Samantha",
    "theme": "helpful sloth",
    "emoji": "🦥"
  },

  "logging": {
    "level": "info",
    "file": "/tmp/openclaw/openclaw.log",
    "consoleLevel": "info",
    "consoleStyle": "pretty",
    "redactSensitive": "tools"
  },

  "messages": {
    "responsePrefix": ">",
    "ackReaction": "👀",
    "ackReactionScope": "group-mentions"
  },

  "session": {
    "scope": "per-sender",
    "reset": {
      "mode": "daily",
      "atHour": 4,
      "idleMinutes": 60
    },
    "resetTriggers": ["/new", "/reset"],
    "store": "~/.openclaw/agents/default/sessions/sessions.json",
    "maintenance": {
      "mode": "warn",
      "pruneAfter": "30d",
      "maxEntries": 500,
      "rotateBytes": "10mb"
    }
  },

  "channels": {
    "whatsapp": {
      "dmPolicy": "pairing",
      "allowFrom": ["+15555550123"],
      "groupPolicy": "allowlist",
      "groupAllowFrom": ["+15555550123"],
      "groups": { "*": { "requireMention": true } }
    },

    "telegram": {
      "enabled": true,
      "botToken": "YOUR_TELEGRAM_BOT_TOKEN",
      "allowFrom": ["123456789"],
      "groupPolicy": "allowlist",
      "groupAllowFrom": ["123456789"],
      "groups": { "*": { "requireMention": true } }
    },

    "discord": {
      "enabled": true,
      "token": "YOUR_DISCORD_BOT_TOKEN",
      "dm": { "enabled": true, "allowFrom": ["steipete"] },
      "guilds": {
        "123456789012345678": {
          "slug": "friends-of-openclaw",
          "requireMention": false,
          "channels": {
            "general": { "allow": true },
            "help": { "allow": true, "requireMention": true }
          }
        }
      }
    },

    "slack": {
      "enabled": true,
      "botToken": "xoxb-REPLACE_ME",
      "appToken": "xapp-REPLACE_ME",
      "channels": {
        "#general": { "allow": true, "requireMention": true }
      },
      "dm": { "enabled": true, "allowFrom": ["U123"] }
    }
  },

  "agents": {
    "defaults": {
      "workspace": "~/.openclaw/workspace",
      "userTimezone": "America/Chicago",
      "model": {
        "primary": "anthropic/claude-sonnet-4-5",
        "fallbacks": ["anthropic/claude-opus-4-6", "openai/gpt-5.2"]
      },
      "models": {
        "anthropic/claude-opus-4-6": { "alias": "opus" },
        "anthropic/claude-sonnet-4-5": { "alias": "sonnet" },
        "openai/gpt-5.2": { "alias": "gpt" }
      },
      "thinkingDefault": "low",
      "timeoutSeconds": 600,
      "maxConcurrent": 3,
      "heartbeat": {
        "every": "30m",
        "model": "anthropic/claude-sonnet-4-5",
        "target": "last",
        "to": "+15555550123"
      },
      "sandbox": {
        "mode": "non-main",
        "workspaceRoot": "~/.openclaw/sandboxes",
        "docker": {
          "image": "openclaw-sandbox:bookworm-slim",
          "workdir": "/workspace",
          "readOnlyRoot": true,
          "tmpfs": ["/tmp", "/var/tmp", "/run"],
          "network": "none",
          "user": "1000:1000"
        }
      }
    }
  },

  "tools": {
    "allow": ["exec", "process", "read", "write", "edit", "apply_patch"],
    "deny": ["browser", "canvas"],
    "exec": {
      "backgroundMs": 10000,
      "timeoutSec": 1800,
      "cleanupMs": 1800000
    },
    "elevated": {
      "enabled": true,
      "allowFrom": {
        "whatsapp": ["+15555550123"],
        "telegram": ["123456789"],
        "discord": ["steipete"]
      }
    }
  },

  "models": {
    "mode": "merge",
    "providers": {
      "custom-proxy": {
        "baseUrl": "http://localhost:4000/v1",
        "apiKey": "LITELLM_KEY",
        "api": "openai-responses",
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
  },

  "cron": {
    "enabled": true,
    "maxConcurrentRuns": 2,
    "sessionRetention": "24h"
  },

  "hooks": {
    "enabled": true,
    "path": "/hooks",
    "token": "shared-secret"
  },

  "gateway": {
    "mode": "local",
    "port": 18789,
    "bind": "loopback",
    "controlUi": { "enabled": true, "basePath": "/openclaw" },
    "auth": {
      "mode": "token",
      "token": "gateway-token",
      "allowTailscale": true
    },
    "tailscale": { "mode": "serve", "resetOnExit": false },
    "reload": { "mode": "hybrid", "debounceMs": 300 }
  }
}
```

## Common patterns

### Multi-platform setup

```json
{
  "agent": { "workspace": "~/.openclaw/workspace" },
  "channels": {
    "whatsapp": { "allowFrom": ["+15555550123"] },
    "telegram": {
      "enabled": true,
      "botToken": "YOUR_TOKEN",
      "allowFrom": ["123456789"]
    },
    "discord": {
      "enabled": true,
      "token": "YOUR_TOKEN",
      "dm": { "allowFrom": ["yourname"] }
    }
  }
}
```

### Secure DM mode (shared inbox / multi-user DMs)

```json
{
  "session": { "dmScope": "per-channel-peer" },
  "channels": {
    "whatsapp": {
      "dmPolicy": "allowlist",
      "allowFrom": ["+15555550123", "+15555550124"]
    },
    "discord": {
      "enabled": true,
      "token": "YOUR_DISCORD_BOT_TOKEN",
      "dm": { "enabled": true, "allowFrom": ["alice", "bob"] }
    }
  }
}
```

### Local models only

```json
{
  "agent": {
    "workspace": "~/.openclaw/workspace",
    "model": { "primary": "lmstudio/minimax-m2.1-gs32" }
  },
  "models": {
    "mode": "merge",
    "providers": {
      "lmstudio": {
        "baseUrl": "http://127.0.0.1:1234/v1",
        "apiKey": "lmstudio",
        "api": "openai-responses",
        "models": [
          {
            "id": "minimax-m2.1-gs32",
            "name": "MiniMax M2.1 GS32",
            "reasoning": false,
            "input": ["text"],
            "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
            "contextWindow": 196608,
            "maxTokens": 8192
          }
        ]
      }
    }
  }
}
```

### Work bot (restricted access)

```json
{
  "identity": {
    "name": "WorkBot",
    "theme": "professional assistant"
  },
  "agent": {
    "workspace": "~/work-openclaw",
    "elevated": { "enabled": false }
  },
  "channels": {
    "slack": {
      "enabled": true,
      "botToken": "xoxb-...",
      "channels": {
        "#engineering": { "allow": true, "requireMention": true },
        "#general": { "allow": true, "requireMention": true }
      }
    }
  }
}
```

## Tips

- If you set `dmPolicy: "open"`, the matching `allowFrom` list must include `"*"`.
- Provider IDs differ (phone numbers, user IDs, channel IDs). Use the provider docs to confirm the format.
- Optional sections to add later: `web`, `browser`, `ui`, `discovery`, `canvasHost`, `talk`, `signal`, `imessage`.
- See [Providers](/channels/whatsapp) and [Troubleshooting](/gateway/troubleshooting) for deeper setup notes.
- The Python gateway uses standard JSON — no comments or trailing commas. Use a JSON validator when editing manually.
