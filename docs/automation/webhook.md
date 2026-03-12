---
summary: "Inbound webhook triggers for automating agent runs from external systems"
read_when:
  - Triggering agent runs from external services via HTTP
  - Configuring webhook authentication and routing
title: "Webhooks"
---

# Webhooks

OpenClaw Python can receive **inbound webhooks** from external services and trigger
agent runs in response.

## Configuration

```json5
{
  webhook: {
    enabled: true,
    port: 8088,
    secret: "my-webhook-secret",  // HMAC verification token
    endpoints: [
      {
        id: "github-events",
        path: "/hooks/github",
        agentId: "main",
        prompt: "Process this GitHub event: {{body}}",
        allowedSources: ["192.30.252.0/22"],  // GitHub IP ranges
      },
    ],
  },
}
```

## Authentication

Webhooks support HMAC-SHA256 signature verification compatible with GitHub, Stripe,
and other services that sign payloads:

```json5
{
  webhook: {
    endpoints: [
      {
        id: "stripe",
        path: "/hooks/stripe",
        signatureHeader: "Stripe-Signature",
        signingSecret: "whsec_...",
        agentId: "main",
        prompt: "A Stripe event occurred: {{body.type}}",
      },
    ],
  },
}
```

## Prompt templating

Webhook prompts support simple `{{field}}` template substitution from the request:

- `{{body}}` — full JSON body (pretty-printed)
- `{{body.field}}` — specific JSON field
- `{{headers.X-My-Header}}` — request header value
- `{{query.param}}` — query parameter value

## CLI commands

```bash
openclaw webhook list     # List configured webhooks
openclaw webhook test <id> --payload '{"key":"val"}'  # Test a webhook
```
