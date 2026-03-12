---
summary: "Telegram bot channel setup, allowlists, and group mode"
read_when:
  - Setting up the Telegram channel for OpenClaw Python
  - Configuring message allowlists, groups, or webhooks
title: "Telegram"
---

# Telegram

OpenClaw Python integrates with Telegram via `python-telegram-bot>=21.0`.

## Quick start

1. Create a Telegram bot with [@BotFather](https://t.me/BotFather) and copy the token.
2. Add to `~/.openclaw/openclaw.json`:

```json5
{
  channels: {
    telegram: {
      token: "1234567890:YOUR_TOKEN_HERE",
      allowFrom: ["+1234567890"],  // phone numbers or @username
    },
  },
}
```

3. Restart the gateway and send `/start` to your bot.

## Security: allowlists

> Without `allowFrom`, **anyone** can message your agent. Set it.

```json5
{
  channels: {
    telegram: {
      allowFrom: ["+1234567890", "+19876543210"],
    },
  },
}
```

Both phone numbers (with country code) and Telegram usernames (`@handle`) are supported.

## Group mode

To use the bot in a group:
1. Add your bot to the group.
2. Set the `agentTrigger` to control when the bot responds.

```json5
{
  channels: {
    telegram: {
      token: "...",
      groupMode: {
        agentTrigger: "mention",  // "mention" | "all" | "command"
      },
    },
  },
}
```

## Block streaming

Telegram supports streaming partial replies. Enabled by default:

```json5
{
  channels: {
    telegram: {
      blockStreaming: true,
    },
  },
}
```

## Media forwarding

Telegram can forward voice messages, photos, documents, and location to the agent:

```json5
{
  channels: {
    telegram: {
      media: {
        voice: true,
        photos: true,
        documents: false,
        location: false,
      },
    },
  },
}
```

## Configuration reference

| Key | Type | Description |
|-----|------|-------------|
| `token` | string | Telegram bot token from BotFather |
| `allowFrom` | string[] | Phone numbers or @usernames allowed to send messages |
| `blockStreaming` | boolean | Stream partial replies (default: true) |
| `groupMode.agentTrigger` | string | When to respond in groups |
| `agentId` | string | Route to a specific agent (default: "main") |
