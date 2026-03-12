---
summary: "Agent runtime (embedded pi-mono-python), workspace contract, and session bootstrap"
read_when:
  - Changing agent runtime, workspace bootstrap, or session behavior
title: "Agent Runtime"
---

# Agent Runtime

OpenClaw Python runs a single embedded agent runtime derived from **pi-mono-python**.

## Workspace (required)

OpenClaw uses a single agent workspace directory (`agents.defaults.workspace`) as the agent's
**only** working directory (`cwd`) for tools and context.

Recommended: use `openclaw setup` to create `~/.openclaw/openclaw.json` if missing and
initialize the workspace files.

## Bootstrap files (injected)

Inside `agents.defaults.workspace`, OpenClaw expects these user-editable files:

- `AGENTS.md` — operating instructions + "memory"
- `SOUL.md` — persona, boundaries, tone
- `TOOLS.md` — user-maintained tool notes (e.g. conventions)
- `BOOTSTRAP.md` — one-time first-run ritual (deleted after completion)
- `IDENTITY.md` — agent name/vibe/emoji
- `USER.md` — user profile + preferred address

On the first turn of a new session, OpenClaw injects the contents of these files
directly into the agent context.

Blank files are skipped. Large files are trimmed and truncated with a marker so
prompts stay lean.

If a file is missing, OpenClaw injects a single "missing file" marker line (and
`openclaw setup` will create a safe default template).

`BOOTSTRAP.md` is only created for a **brand new workspace** (no other bootstrap files
present). If you delete it after completing the ritual, it should not be recreated.

To disable bootstrap file creation entirely (for pre-seeded workspaces), set:

```json5
{ agent: { skipBootstrap: true } }
```

## Built-in tools

Core tools (read/exec/edit/write and related system tools) are always available,
subject to tool policy. `TOOLS.md` does **not** control which tools exist; it's
guidance for how _you_ want them used.

## Skills

OpenClaw loads skills from three locations (workspace wins on name conflict):

- Bundled (shipped with the install)
- Managed/local: `~/.openclaw/skills`
- Workspace: `<workspace>/skills`

Skills can be gated by config/env (see `skills` in gateway configuration).

## pi-mono-python integration

OpenClaw Python reuses pieces of the pi-mono-python codebase (models/tools), but
**session management, discovery, and tool wiring are OpenClaw-owned**.

- No pi-coding agent runtime.
- No `~/.pi/agent` or `<workspace>/.pi` settings are consulted.

## Sessions

Session transcripts are stored as JSONL at:

- `~/.openclaw/agents/<agentId>/sessions/<SessionId>.jsonl`

The session ID is stable and chosen by OpenClaw.

## Steering while streaming

When queue mode is `steer`, inbound messages are injected into the current run.
The queue is checked **after each tool call**.

When queue mode is `followup` or `collect`, inbound messages are held until the
current turn ends, then a new agent turn starts with the queued payloads. See
[Queue](queue.md) for mode + debounce/cap behavior.

## Model refs

Model refs in config (for example `agents.defaults.model`) are parsed by splitting
on the **first** `/`:

- Use `provider/model` when configuring models.
- Example: `anthropic/claude-opus-4-5`, `openai/gpt-4o`, `ollama/llama3.3`.

## Configuration (minimal)

At minimum, set:

- `agents.defaults.workspace`
- `channels.<channel>.allowFrom` (strongly recommended)

---

_Next: [Group Chats](../channels/group-messages.md)_
