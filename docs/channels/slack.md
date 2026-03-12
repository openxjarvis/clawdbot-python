---
summary: "Slack bot setup, OAuth scopes, and DM vs channel modes"
read_when:
  - Setting up Slack channel for OpenClaw Python
  - Configuring Slack app scopes or event subscriptions
title: "Slack"
---

# Slack

OpenClaw Python integrates with Slack via `slack-bolt` + `slack-sdk>=3.27`.

## Required Slack app scopes

Bot Token Scopes:
- `app_mentions:read`
- `channels:history`
- `chat:write`
- `groups:history`
- `im:history`
- `im:write`
- `mpim:history`
- `mpim:write`
- `users:read`

Event subscriptions:
- `message.im`
- `message.channels`
- `message.groups`
- `message.mpim`
- `app_mention`

## Quick start

```json5
{
  channels: {
    slack: {
      botToken: "xoxb-...",
      signingSecret: "...",
      appToken: "xapp-...",  // for Socket Mode
      socketMode: true,
    },
  },
}
```

## Socket Mode (recommended)

Socket Mode requires an app-level token (`xapp-...`). Enable **Socket Mode** in
the Slack app settings and generate an app-level token with `connections:write` scope.

## Allowlists

```json5
{
  channels: {
    slack: {
      allowFrom: ["U12345678", "W12345678"],  // Slack user IDs
    },
  },
}
```

## Group chat (channels)

```json5
{
  channels: {
    slack: {
      agentTrigger: "mention",  // "mention" | "all"
    },
  },
}
```

## Configuration reference

| Key | Type | Description |
|-----|------|-------------|
| `botToken` | string | Slack bot token (`xoxb-...`) |
| `signingSecret` | string | App signing secret |
| `appToken` | string | App-level token for Socket Mode |
| `socketMode` | boolean | Use Socket Mode (recommended) |
| `allowFrom` | string[] | Allowed Slack user IDs |
| `agentTrigger` | string | Group trigger mode |
| `agentId` | string | Route to a specific agent |
