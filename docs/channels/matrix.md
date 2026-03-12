---
summary: "Matrix channel setup via matrix-nio"
read_when:
  - Setting up Matrix channel for OpenClaw Python
  - Configuring matrix-nio credentials and homeserver
title: "Matrix"
---

# Matrix

OpenClaw Python integrates with Matrix via `matrix-nio`.

## Install

```bash
pip install matrix-nio
```

## Quick start

1. Create a Matrix account for your bot (or use an existing one).
2. Add to `~/.openclaw/openclaw.json`:

```json5
{
  channels: {
    matrix: {
      homeserverUrl: "https://matrix.org",
      userId: "@mybot:matrix.org",
      accessToken: "syt_...",
      deviceId: "OPENCLAW",
    },
  },
}
```

## Authentication

Obtain an access token by logging in with the Matrix client API or using
`matrix-nio` directly:

```python
import asyncio
from nio import AsyncClient

async def login():
    client = AsyncClient("https://matrix.org", "@mybot:matrix.org")
    response = await client.login("my-password", device_name="OPENCLAW")
    print(response.access_token)
    print(response.device_id)
    await client.close()

asyncio.run(login())
```

## Allowlists

```json5
{
  channels: {
    matrix: {
      allowFrom: ["@alice:matrix.org", "@bob:example.com"],
    },
  },
}
```

## Room allowlists

```json5
{
  channels: {
    matrix: {
      allowRooms: ["!roomid:matrix.org"],
    },
  },
}
```

## E2E encryption

`matrix-nio` supports E2E encryption. Enable with:

```json5
{
  channels: {
    matrix: {
      e2eEnabled: true,
      storeDir: "~/.openclaw/matrix-store",
    },
  },
}
```

## Configuration reference

| Key | Type | Description |
|-----|------|-------------|
| `homeserverUrl` | string | Matrix homeserver URL |
| `userId` | string | Full Matrix user ID (e.g. `@bot:matrix.org`) |
| `accessToken` | string | Access token from login |
| `deviceId` | string | Device ID from login |
| `allowFrom` | string[] | Allowed Matrix user IDs |
| `allowRooms` | string[] | Allowed room IDs |
| `e2eEnabled` | boolean | Enable E2E encryption |
| `storeDir` | string | Local key store directory for E2E |
| `agentId` | string | Route to a specific agent |
