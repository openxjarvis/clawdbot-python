---
summary: "Channel integrations overview for OpenClaw Python"
read_when:
  - Deciding which messaging channels to connect
  - Overview of available OpenClaw Python channel plugins
title: "Channels"
---

# Channels

OpenClaw Python supports the following messaging channels via bundled extension plugins.

## Available channels

| Channel | Plugin | Status | Requirements |
|---------|--------|--------|-------------|
| [Telegram](telegram.md) | `telegram` | Stable | `python-telegram-bot>=21.0` |
| [Discord](discord.md) | `discord` | Stable | `discord.py>=2.3` |
| [Slack](slack.md) | `slack` | Stable | `slack-bolt`, `slack-sdk>=3.27` |
| [WhatsApp](whatsapp.md) | `whatsapp` | Stable | Meta Cloud API credentials |
| [Matrix](matrix.md) | `matrix` | Stable | `matrix-nio` |
| [IRC](irc.md) | `irc` | Beta | built-in |
| [Signal](signal.md) | `signal` | Beta | Signal CLI or signal-cli bridge |
| [Google Chat](googlechat.md) | `googlechat` | Beta | `google-cloud-pubsub`, `google-auth` |
| Microsoft Teams | `msteams` | Beta | Microsoft App credentials |
| Feishu/Lark | `feishu` | Beta | Feishu app credentials |
| iMessage | `imessage` | macOS only | BlueBubbles or AppleScript bridge |
| BlueBubbles | `bluebubbles` | macOS only | BlueBubbles server |
| LINE | `line` | Beta | LINE Developers channel token |
| Mattermost | `mattermost` | Beta | Mattermost server credentials |
| Nostr | `nostr` | Beta | Nostr key pair |
| Twitch | `twitch` | Beta | Twitch OAuth token |
| Nextcloud Talk | `nextcloud-talk` | Beta | Nextcloud server credentials |
| Zalo | `zalo` | Beta | Zalo App credentials |

## Enabling channels

Enable a channel by adding its configuration to `~/.openclaw/openclaw.json`:

```json5
{
  channels: {
    telegram: {
      token: "...",
      allowFrom: ["+1234567890"],
    },
    discord: {
      token: "...",
    },
  },
}
```

Multiple channels can be active simultaneously. Each channel routes to the
default agent unless `agentId` is specified.

## Security baseline

> **Set `allowFrom` on every channel.** Without it, anyone who discovers your bot
> can interact with your agent.

See the individual channel docs for format details.
