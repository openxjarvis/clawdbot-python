---
summary: "Getting started with OpenClaw Python in 5 minutes"
read_when:
  - Setting up OpenClaw Python for the first time
  - Quick start guide
title: "Quickstart"
---

# Quickstart

Get OpenClaw Python running with a Telegram bot in 5 minutes.

## 1. Install

```bash
pip install openclaw-python
```

## 2. Setup

```bash
openclaw setup
```

This creates `~/.openclaw/openclaw.json` and initializes your workspace at
`~/.openclaw/workspace`.

## 3. Configure

Edit `~/.openclaw/openclaw.json`:

```json5
{
  agents: {
    defaults: {
      workspace: "~/.openclaw/workspace",
      model: "anthropic/claude-opus-4-5",
    },
  },
  models: {
    providers: {
      anthropic: { apiKey: "sk-ant-..." },
    },
  },
  channels: {
    telegram: {
      token: "1234567890:YOUR_BOT_TOKEN",
      allowFrom: ["+1234567890"],  // your phone number (with country code)
    },
  },
}
```

## 4. Start the gateway

```bash
openclaw start
```

## 5. Chat

Send a message to your Telegram bot. The agent will respond!

## Next steps

- [Add more channels](../channels/index.md)
- [Configure memory](../concepts/memory.md)
- [Install plugins](../tools/plugin.md)
- [Set up cron jobs](../automation/cron-jobs.md)
