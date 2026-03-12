---
summary: "End-to-end guide for running OpenClaw Python as a personal assistant with safety cautions"
read_when:
  - Onboarding a new assistant instance
  - Reviewing safety/permission implications
title: "Personal Assistant Setup"
---

# Building a personal assistant with OpenClaw Python

OpenClaw Python is a Telegram + Discord + Slack + Signal gateway for **AI agents**. Plugins add Matrix, Zalo Personal, and more. This guide is the "personal assistant" setup: one dedicated Telegram bot that behaves like your always-on agent.

## Safety first

You're putting an agent in a position to:

- run commands on your machine (depending on your tool setup)
- read/write files in your workspace
- send messages back out via Telegram/Discord/Slack and other channels

Start conservative:

- Always set `channels.telegram.allowFrom` (never run open-to-the-world on your personal machine).
- Use a dedicated bot account for the assistant.
- Heartbeats now default to every 30 minutes. Disable until you trust the setup by setting `agents.defaults.heartbeat.every: "0m"`.

## Prerequisites

- OpenClaw Python installed and onboarded — see [Getting Started](/start/getting-started) if you haven't done this yet
- A Telegram bot token (from [@BotFather](https://t.me/botfather))

## 5-minute quick start

1. Configure a minimal `~/.openclaw/openclaw.json`:

```json5
{
  agents: {
    defaults: {
      model: "anthropic/claude-opus-4-5",
      workspace: "~/.openclaw/workspace",
    },
  },
  models: {
    providers: {
      anthropic: { apiKey: "sk-ant-..." },
    },
  },
  channels: {
    telegram: {
      token: "1234567890:YOUR_BOT_TOKEN",
      allowFrom: ["+15555550123"],
    },
  },
}
```

2. Start the Gateway:

```bash
openclaw start
```

3. Message the bot from your allowlisted account.

## Give the agent a workspace (AGENTS)

OpenClaw Python reads operating instructions and "memory" from its workspace directory.

By default, OpenClaw Python uses `~/.openclaw/workspace` as the agent workspace, and will create it (plus starter `AGENTS.md`, `SOUL.md`, `TOOLS.md`, `IDENTITY.md`, `USER.md`, `HEARTBEAT.md`) automatically on setup/first agent run.

Treat this folder like your agent's "memory" and make it a git repo (ideally private) so your `AGENTS.md` + memory files are backed up.

```bash
openclaw setup
```

Optional: choose a different workspace with `agents.defaults.workspace` (supports `~`).

```json5
{
  agents: {
    defaults: {
      workspace: "~/.openclaw/workspace",
    },
  },
}
```

## The config that turns it into "an assistant"

OpenClaw Python defaults to a good assistant setup, but you'll usually want to tune:

- persona/instructions in `SOUL.md`
- thinking defaults (if desired)
- heartbeats (once you trust it)

Example:

```json5
{
  logging: { level: "info" },
  agents: {
    defaults: {
      model: "anthropic/claude-opus-4-5",
      workspace: "~/.openclaw/workspace",
      heartbeat: { every: "0m" }, // Start with 0; enable later.
    },
  },
  channels: {
    telegram: {
      token: "YOUR_BOT_TOKEN",
      allowFrom: ["+15555550123"],
    },
  },
  session: {
    scope: "per-sender",
    resetTriggers: ["/new", "/reset"],
    reset: {
      mode: "daily",
      atHour: 4,
      idleMinutes: 10080,
    },
  },
}
```

## Sessions and memory

- Session files: `~/.openclaw/agents/<agentId>/sessions/{{SessionId}}.jsonl`
- `/new` or `/reset` starts a fresh session for that chat (configurable via `resetTriggers`).
- `/compact [instructions]` compacts the session context and reports the remaining context budget.

## Heartbeats (proactive mode)

By default, OpenClaw Python runs a heartbeat every 30 minutes with the prompt:
`Read HEARTBEAT.md if it exists (workspace context). Follow it strictly. Do not infer or repeat old tasks from prior chats. If nothing needs attention, reply HEARTBEAT_OK.`
Set `agents.defaults.heartbeat.every: "0m"` to disable.

- If `HEARTBEAT.md` exists but is effectively empty, OpenClaw Python skips the heartbeat run to save API calls.
- If the agent replies with `HEARTBEAT_OK`, OpenClaw Python suppresses outbound delivery for that heartbeat.
- Heartbeats run full agent turns — shorter intervals burn more tokens.

```json5
{
  agents: {
    defaults: {
      heartbeat: { every: "30m" },
    },
  },
}
```

## Operations checklist

```bash
openclaw status          # local status (creds, sessions, queued events)
openclaw status --all    # full diagnosis (read-only, pasteable)
openclaw health --json   # gateway health snapshot
```

Logs live under `/tmp/openclaw/` (default: `openclaw-YYYY-MM-DD.log`).

## Next steps

- Gateway ops: [Gateway runbook](/gateway)
- Cron + wakeups: [Cron jobs](/automation/cron-jobs)
- More channels: [Channels](/channels)
- Security: [Security](/gateway/security)
