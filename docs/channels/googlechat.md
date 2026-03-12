---
summary: "Google Chat bot channel setup for OpenClaw Python"
read_when:
  - Setting up Google Chat channel for OpenClaw Python
title: "Google Chat"
---

# Google Chat

OpenClaw Python integrates with Google Chat via Google Cloud Pub/Sub.

## Requirements

```bash
pip install google-cloud-pubsub google-auth
```

## Quick start

1. Create a Google Cloud project and enable the Chat API and Pub/Sub API.
2. Create a service account with Pub/Sub subscriber permissions.
3. Configure the bot in Google Workspace admin.

```json5
{
  channels: {
    googlechat: {
      credentialsFile: "~/.openclaw/google-credentials.json",
      projectId: "my-gcp-project",
      subscriptionId: "openclaw-chat-sub",
    },
  },
}
```

## Configuration reference

| Key | Type | Description |
|-----|------|-------------|
| `credentialsFile` | string | Path to Google service account JSON |
| `projectId` | string | Google Cloud project ID |
| `subscriptionId` | string | Pub/Sub subscription ID |
| `allowFrom` | string[] | Allowed Google Chat user IDs |
| `agentId` | string | Route to a specific agent |
