---
summary: "Message queue modes: steer, followup, collect, and per-session overrides"
read_when:
  - You want to control how inbound messages interact with running agent turns
  - You are debugging message queuing behavior
title: "Queue"
---

# Message Queue

OpenClaw Python queues inbound messages to prevent overlapping agent runs for
the same session.

## Queue modes

- `steer`: inject immediately into the current run (cancels pending tool calls
  after the next tool boundary). Falls back to followup if not streaming.
- `followup`: enqueue for the next agent turn after the current run ends.
- `collect`: coalesce all queued messages into a **single** followup turn (default).
- `steer-backlog` (aka `steer+backlog`): steer now **and** preserve the message
  for a followup turn.

## Configuration

```json5
{
  messages: {
    queue: {
      mode: "collect",
      debounceMs: 1000,
      cap: 20,
      drop: "summarize",
      byChannel: { discord: "collect" },
    },
  },
}
```

## Queue options

- `debounceMs`: wait for quiet before starting a followup turn.
- `cap`: max queued messages per session.
- `drop`: overflow policy (`old`, `new`, `summarize`).

Defaults: `debounceMs: 1000`, `cap: 20`, `drop: summarize`.

## Per-session overrides

Send `/queue <mode>` as a standalone command to store the mode for the current session.

Options can be combined: `/queue collect debounce:2s cap:25 drop:summarize`

`/queue default` or `/queue reset` clears the session override.

## Guarantees

- Applies to auto-reply agent runs across all inbound channels.
- Per-session lanes guarantee that only one agent run touches a given session at a time.
- Default lane (`main`) is process-wide for inbound + main heartbeats.
