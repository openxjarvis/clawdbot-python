---
summary: "Block streaming and chunk coalescing for real-time chat replies"
read_when:
  - Enabling or tuning block streaming for a channel
  - Debugging streaming reply behavior
title: "Streaming"
---

# Streaming + Chunking

OpenClaw Python supports **block streaming** — sending partial agent responses
as soon as assistant blocks finish, rather than waiting for the full reply.

## Block streaming

Block streaming sends completed assistant blocks as soon as they finish.

- Off by default (`agents.defaults.blockStreamingDefault: "off"`).
- Non-Telegram channels require explicit `*.blockStreaming: true` to enable.
- Tune the boundary via `agents.defaults.blockStreamingBreak` (`text_end` vs
  `message_end`; defaults to `text_end`).
- Control soft block chunking with `agents.defaults.blockStreamingChunk`
  (defaults to 800–1200 chars; prefers paragraph breaks, then newlines).
- Coalesce streamed chunks with `agents.defaults.blockStreamingCoalesce` to
  reduce single-line spam (idle-based merging before send).

## Per-channel configuration

```json5
{
  channels: {
    telegram: {
      blockStreaming: true,
    },
    discord: {
      blockStreaming: false,
    },
  },
  agents: {
    defaults: {
      blockStreamingDefault: "off",
      blockStreamingBreak: "text_end",
      blockStreamingChunk: { minChars: 800, maxChars: 1200 },
    },
  },
}
```

## Typing indicators

Typing indicators fire immediately on enqueue (when supported by the channel)
so user experience is unchanged while we wait for the agent to start.
