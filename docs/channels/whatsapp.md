---
summary: "WhatsApp channel setup via the Meta Cloud API"
read_when:
  - Setting up WhatsApp for OpenClaw Python
  - Configuring Meta Cloud API credentials
title: "WhatsApp"
---

# WhatsApp

OpenClaw Python integrates with WhatsApp via the **Meta Cloud API** (free tier available).

## Prerequisites

1. A Meta for Developers account.
2. A WhatsApp Business account linked to your Meta app.
3. A phone number registered with the WhatsApp Business API.

## Quick start

```json5
{
  channels: {
    whatsapp: {
      accessToken: "EAA...",
      phoneNumberId: "123456789",
      verifyToken: "my-webhook-secret",
      webhookPort: 8080,
      allowFrom: ["+1234567890"],
    },
  },
}
```

## Webhook setup

WhatsApp requires a public HTTPS webhook endpoint. Options:
- Use `ngrok` to tunnel to your local port.
- Deploy OpenClaw behind a reverse proxy (nginx, Caddy).
- Use the gateway's built-in HTTPS support.

In the Meta Developer portal, set:
- **Webhook URL**: `https://your-domain.com/webhook/whatsapp`
- **Verify token**: matches your `verifyToken` config value
- **Subscribe to**: `messages`

## Security: allowlists

```json5
{
  channels: {
    whatsapp: {
      allowFrom: ["+1234567890", "+19876543210"],
    },
  },
}
```

Numbers must include country code.

## Configuration reference

| Key | Type | Description |
|-----|------|-------------|
| `accessToken` | string | Meta API access token |
| `phoneNumberId` | string | WhatsApp phone number ID |
| `verifyToken` | string | Webhook verification token |
| `webhookPort` | number | Port to listen for webhook (default: 8080) |
| `allowFrom` | string[] | Phone numbers allowed to send messages |
| `agentId` | string | Route to a specific agent |
