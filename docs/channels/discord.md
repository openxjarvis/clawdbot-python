---
summary: "Discord bot channel setup, allowlists, and group message handling"
read_when:
  - Setting up the Discord channel for OpenClaw Python
  - Configuring Discord bot permissions and allowlists
title: "Discord"
---

# Discord

OpenClaw Python integrates with Discord via `discord.py>=2.3`.

## Quick start

1. Create a Discord application at [discord.com/developers](https://discord.com/developers/applications).
2. Create a bot under your application and copy the token.
3. Enable **Message Content Intent** in the bot settings.
4. Add to `~/.openclaw/openclaw.json`:

```json5
{
  channels: {
    discord: {
      token: "YOUR_DISCORD_BOT_TOKEN",
      allowFrom: ["user#1234", "12345678901234567"],  // username#discriminator or snowflake id
    },
  },
}
```

5. Restart the gateway and invite your bot to a server.

## Security: allowlists

```json5
{
  channels: {
    discord: {
      allowFrom: ["username#1234", "987654321012345678"],
    },
  },
}
```

Accepted formats:
- `username#discriminator` (legacy format)
- `username` (new username format)
- User snowflake ID (18-digit numeric)

## Guild (server) allowlist

Restrict which servers the bot responds in:

```json5
{
  channels: {
    discord: {
      allowGuilds: ["987654321012345678"],
    },
  },
}
```

## DM-only mode

```json5
{
  channels: {
    discord: {
      dmOnly: true,
    },
  },
}
```

## Streaming

Discord does not support live message edits on all client versions. Block streaming
is disabled by default for Discord.

## Configuration reference

| Key | Type | Description |
|-----|------|-------------|
| `token` | string | Discord bot token |
| `allowFrom` | string[] | Allowed users (username#tag or snowflake) |
| `allowGuilds` | string[] | Allowed guild (server) IDs |
| `dmOnly` | boolean | Only respond in DMs |
| `agentId` | string | Route to a specific agent |
