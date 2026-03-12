---
summary: "Deep dive: session store + transcripts, lifecycle, and (auto)compaction internals"
read_when:
  - You need to debug session ids, transcript JSONL, or sessions.json fields
  - You are changing auto-compaction behavior
  - You want to implement memory flushes or silent system turns
title: "Session Management Deep Dive"
---

# Session Management & Compaction (Deep Dive)

This document explains how OpenClaw manages sessions end-to-end:

- **Session routing** (how inbound messages map to a `sessionKey`)
- **Session store** (`sessions.json`) and what it tracks
- **Transcript persistence** (`*.jsonl`) and its structure
- **Transcript hygiene** (provider-specific fixups before runs)
- **Context limits** (context window vs tracked tokens)
- **Compaction** (manual + auto-compaction)
- **Silent housekeeping** (e.g. memory writes)

For a higher-level overview first, see:

- [/concepts/session](/concepts/session)
- [/concepts/compaction](/concepts/compaction)
- [/reference/transcript-hygiene](/reference/transcript-hygiene)

---

## Two persistence layers

OpenClaw persists sessions in two layers:

1. **Session store (`sessions.json`)**
   - Key/value map: `sessionKey -> SessionEntry`
   - Small, mutable, safe to edit (or delete entries)
   - Tracks session metadata (current session id, last activity, toggles, token counters)

2. **Transcript (`<sessionId>.jsonl`)**
   - Append-only transcript with tree structure (entries have `id` + `parentId`)
   - Provider-agnostic format; content blocks may be base64-encoded images

---

## Session routing

A `sessionKey` is determined from:
- Channel + sender address for inbound messages (e.g. `telegram:user123`)
- Session ID for explicit targeting

---

## Compaction

Compaction reduces the transcript size when the context window is nearly full.

### `cache-ttl` mode

When `session.compaction.mode = "cache-ttl"`:

1. Messages older than `cache.ttl` are soft-trimmed (replaced with summaries).
2. If still over limit, hard-clear removes all but the last N messages.

### Auto-compaction

Triggered automatically when:
- Remaining context tokens < `session.compaction.triggerAtTokensRemaining`
- Or immediately before sending if context is full

### Manual compaction

```bash
openclaw sessions compact <sessionKey>
```

---

## Silent housekeeping

Some turns (e.g. memory flush, skill indexing) should not produce user-visible output.
Mark these as `role: "system"` with `silent: true` in the session transcript.

---

## Python implementation

- `openclaw/agents/session_store.py` — `SessionStore`, `SessionEntry`
- `openclaw/agents/compaction.py` — `compact_session()`, `auto_compact()`
- `openclaw/agents/history_utils.py` — `sanitize_session_history()`, `TranscriptPolicy`
