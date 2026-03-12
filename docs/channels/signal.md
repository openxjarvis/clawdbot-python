---
summary: "Signal messaging channel setup for OpenClaw Python"
read_when:
  - Setting up Signal channel for OpenClaw Python
title: "Signal"
---

# Signal

OpenClaw Python integrates with Signal via `python-signalbot`.

## Prerequisites

Signal requires a Signal CLI bridge (signal-cli or signal-api) running locally.

## Quick start

```bash
pip install python-signalbot
```

```json5
{
  channels: {
    signal: {
      apiUrl: "http://localhost:8080",
      phoneNumber: "+1234567890",
      allowFrom: ["+19876543210"],
    },
  },
}
```

## Configuration reference

| Key | Type | Description |
|-----|------|-------------|
| `apiUrl` | string | signal-cli REST API URL |
| `phoneNumber` | string | Your Signal phone number |
| `allowFrom` | string[] | Allowed sender phone numbers |
| `agentId` | string | Route to a specific agent |
