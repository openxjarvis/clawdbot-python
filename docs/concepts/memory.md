---
title: "Memory"
summary: "How OpenClaw Python memory works (workspace files + automatic memory flush)"
read_when:
  - You want the memory file layout and workflow
  - You want to tune the automatic pre-compaction memory flush
---

# Memory

OpenClaw Python memory is **plain Markdown in the agent workspace**. The files are
the source of truth; the model only "remembers" what gets written to disk.

Memory search tools are provided by the active memory plugin (default: `memory-core`).
Disable memory plugins with `plugins.slots.memory = "none"`.

## Memory files (Markdown)

The default workspace layout uses two memory layers:

- `memory/YYYY-MM-DD.md`
  - Daily log (append-only).
  - Read today + yesterday at session start.
- `MEMORY.md` (optional)
  - Curated long-term memory.
  - **Only load in the main, private session** (never in group contexts).

These files live under the workspace (`agents.defaults.workspace`, default
`~/.openclaw/workspace`).

## When to write memory

- Decisions, preferences, and durable facts go to `MEMORY.md`.
- Day-to-day notes and running context go to `memory/YYYY-MM-DD.md`.
- If someone says "remember this," write it down (do not keep it in RAM).

## Automatic memory flush (pre-compaction ping)

When a session is **close to auto-compaction**, OpenClaw triggers a **silent,
agentic turn** that reminds the model to write durable memory **before** the
context is compacted.

```json5
{
  agents: {
    defaults: {
      compaction: {
        reserveTokensFloor: 20000,
        memoryFlush: {
          enabled: true,
          softThresholdTokens: 4000,
          systemPrompt: "Session nearing compaction. Store durable memories now.",
          prompt: "Write any lasting notes to memory/YYYY-MM-DD.md; reply with NO_REPLY if nothing to store.",
        },
      },
    },
  },
}
```

## Vector memory search (memory-lancedb plugin)

The `memory-lancedb` plugin provides vector search over memory files using
LanceDB. Enable it with:

```json5
{
  plugins: {
    slots: { memory: "memory-lancedb" },
    entries: {
      "memory-lancedb": {
        enabled: true,
        config: {
          embedding: {
            apiKey: "sk-proj-...",
            model: "text-embedding-3-small",
          },
          autoCapture: true,
          autoRecall: true,
        },
      },
    },
  },
}
```

## Memory tools

- `memory_search` — semantically searches Markdown chunks from `MEMORY.md` + `memory/**/*.md`.
- `memory_get` — reads a specific memory Markdown file by path.

Both tools are enabled only when a memory plugin is active.

## Index storage

The memory index is stored at `~/.openclaw/memory/<agentId>.lancedb` (or similar,
depending on the active memory plugin).
