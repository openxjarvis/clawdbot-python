---
summary: "Cron job scheduling in OpenClaw Python"
read_when:
  - Configuring automated scheduled agent tasks
  - Debugging cron job execution or timing
title: "Cron Jobs"
---

# Cron Jobs

OpenClaw Python supports scheduled agent tasks via a built-in **cron scheduler**.
Cron tasks run on a configurable schedule and inject a prompt into a specific agent
session.

## Configuration

```json5
{
  cron: {
    jobs: [
      {
        id: "daily-summary",
        schedule: "0 9 * * *",  // 9:00 AM every day (crontab syntax)
        agentId: "main",
        prompt: "Give me a brief summary of what you worked on yesterday and what's planned today.",
        sessionKey: "cron:daily-summary",
        timezone: "America/New_York",
      },
    ],
  },
}
```

## Crontab format

Uses standard 5-part crontab: `minute hour day month weekday`

Examples:
- `0 9 * * *` — 9:00 AM every day
- `*/30 * * * *` — every 30 minutes
- `0 9 * * 1-5` — 9:00 AM Monday–Friday
- `0 0 1 * *` — midnight on the 1st of each month

## Session handling

Each cron job runs in its own dedicated session (keyed by `cron:<job.id>`).
The session is isolated from direct-message sessions.

You can also set `sessionKey` to `null` to use the agent's main session.

## Outputs

Cron job outputs can be forwarded to a channel:

```json5
{
  cron: {
    jobs: [
      {
        id: "daily-summary",
        schedule: "0 9 * * *",
        agentId: "main",
        prompt: "...",
        output: {
          channel: "telegram",
          accountId: "default",
          conversationId: "+1234567890",
        },
      },
    ],
  },
}
```

## CLI management

```bash
openclaw cron list       # List all cron jobs
openclaw cron run <id>   # Run a cron job immediately
openclaw cron status     # Show scheduler status
```
