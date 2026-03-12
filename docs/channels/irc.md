---
summary: "IRC channel setup via asyncio IRC client"
read_when:
  - Setting up the IRC channel for OpenClaw Python
  - Configuring IRC server, nick, and allowlists
title: "IRC"
---

# IRC

OpenClaw Python integrates with IRC using an asyncio-based IRC client.

## Quick start

```json5
{
  channels: {
    irc: {
      server: "irc.libera.chat",
      port: 6697,
      tls: true,
      nick: "mybot",
      password: "nickserv-password",
      channels: ["#mychannel"],
      allowFrom: ["alice", "bob"],
    },
  },
}
```

## Security: allowlists

```json5
{
  channels: {
    irc: {
      allowFrom: ["alice", "bob"],
    },
  },
}
```

These are IRC nicks. Note: IRC nicks can be spoofed; for security-critical use
consider also enforcing NickServ identification.

## Private messages

By default, the bot responds to private messages and channel messages where it
is mentioned. Control this with:

```json5
{
  channels: {
    irc: {
      dmOnly: false,
      agentTrigger: "mention",  // "mention" | "all"
    },
  },
}
```

## TLS

Use port `6697` with `tls: true` for secure connections (recommended).

## Configuration reference

| Key | Type | Description |
|-----|------|-------------|
| `server` | string | IRC server hostname |
| `port` | number | IRC server port |
| `tls` | boolean | Use TLS/SSL |
| `nick` | string | Bot nick |
| `password` | string | NickServ password |
| `channels` | string[] | Channels to join on connect |
| `allowFrom` | string[] | Allowed nicks |
| `agentTrigger` | string | Channel trigger mode |
| `agentId` | string | Route to a specific agent |
