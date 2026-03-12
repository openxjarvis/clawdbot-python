---
summary: "Session management rules, keys, and persistence for chats"
read_when:
  - Modifying session handling or storage
title: "Session Management"
---

# Session Management

OpenClaw Python treats **one direct-chat session per agent** as primary. Direct chats
collapse to `agent:<agentId>:<mainKey>` (default `main`), while group/channel chats
get their own keys. `session.mainKey` is honored.

Use `session.dmScope` to control how **direct messages** are grouped:

- `main` (default): all DMs share the main session for continuity.
- `per-peer`: isolate by sender id across channels.
- `per-channel-peer`: isolate by channel + sender (recommended for multi-user inboxes).
- `per-account-channel-peer`: isolate by account + channel + sender.

## Secure DM mode (recommended for multi-user setups)

> **Security Warning:** If your agent can receive DMs from **multiple people**, you
> should strongly consider enabling secure DM mode. Without it, all users share the
> same conversation context, which can leak private information between users.

```json5
// ~/.openclaw/openclaw.json
{
  session: {
    dmScope: "per-channel-peer",
  },
}
```

## Gateway is the source of truth

All session state is **owned by the gateway** (the OpenClaw Python process).

- Store file: `~/.openclaw/agents/<agentId>/sessions/sessions.json`
- Transcripts: `~/.openclaw/agents/<agentId>/sessions/<SessionId>.jsonl`

## Session keys

- Direct chats follow `session.dmScope` (default `main`):
  - `main`: `agent:<agentId>:<mainKey>`
  - `per-peer`: `agent:<agentId>:dm:<peerId>`
  - `per-channel-peer`: `agent:<agentId>:<channel>:dm:<peerId>`
  - `per-account-channel-peer`: `agent:<agentId>:<channel>:<accountId>:dm:<peerId>`
- Group chats: `agent:<agentId>:<channel>:group:<id>`
- Cron jobs: `cron:<job.id>`
- Webhooks: `hook:<uuid>`

## Lifecycle

- Reset policy: sessions are reused until they expire.
- Daily reset: defaults to **4:00 AM local time on the gateway host**.
- Idle reset (optional): `idleMinutes` adds a sliding idle window.
- Reset triggers: `/new` or `/reset` start a fresh session id.
- Manual reset: delete specific keys from the store or remove the JSONL transcript.

## Configuration example

```json5
// ~/.openclaw/openclaw.json
{
  session: {
    dmScope: "main",
    identityLinks: {
      alice: ["telegram:123456789", "discord:987654321012345678"],
    },
    reset: {
      mode: "daily",
      atHour: 4,
      idleMinutes: 120,
    },
    resetTriggers: ["/new", "/reset"],
    mainKey: "main",
  },
}
```

## Inspecting

- `openclaw status` — shows store path and recent sessions.
- `openclaw sessions --json` — dumps every entry.
- Send `/status` as a standalone message in chat to see agent state and context usage.
- Send `/context list` or `/context detail` to see what's in the system prompt.
- Send `/stop` to abort the current run.
- Send `/compact` (optional instructions) to summarize older context.

## Session pruning

OpenClaw trims **old tool results** from the in-memory context right before LLM calls.
This does **not** rewrite JSONL history. See [Session Pruning](session-pruning.md).

## Pre-compaction memory flush

When a session nears auto-compaction, OpenClaw can run a **silent memory flush**
turn that reminds the model to write durable notes to disk. See [Memory](memory.md).
