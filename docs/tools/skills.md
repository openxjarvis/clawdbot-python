---
summary: "Skills: managed vs workspace, gating rules, and config/env wiring"
read_when:
  - Adding or modifying skills
  - Changing skill gating or load rules
title: "Skills"
---

# Skills (OpenClaw Python)

OpenClaw Python uses **AgentSkills-compatible** skill folders to teach the agent
how to use tools. Each skill is a directory containing a `SKILL.md` with YAML
frontmatter and instructions.

## Locations and precedence

Skills are loaded from **three** places:

1. **Bundled skills**: shipped with the install
2. **Managed/local skills**: `~/.openclaw/skills`
3. **Workspace skills**: `<workspace>/skills`

Precedence: `<workspace>/skills` (highest) → `~/.openclaw/skills` → bundled (lowest)

## Per-agent vs shared skills

In **multi-agent** setups:

- **Per-agent skills** live in `<workspace>/skills` for that agent only.
- **Shared skills** live in `~/.openclaw/skills` (visible to **all agents**).
- Extra skill folders via `skills.load.extraDirs` (lowest precedence).

## Plugins + skills

Plugins can ship their own skills by listing `skills` directories in
`openclaw.plugin.json` (paths relative to the plugin root). Plugin skills load
when the plugin is enabled.

## Format (AgentSkills-compatible)

`SKILL.md` must include at least:

```markdown
---
name: my-skill
description: What this skill teaches the agent
---

Instructions for the agent about how to use this skill...
```

Optional frontmatter keys:

- `homepage` — URL surfaced in skill listings.
- `user-invocable` — `true|false` (default: `true`). When `true`, skill exposed as a slash command.
- `disable-model-invocation` — `true|false`. When `true`, skill excluded from model prompt.
- `command-dispatch` — `tool`. When set to `tool`, the slash command dispatches directly to a tool.
- `command-tool` — tool name to invoke when `command-dispatch: tool` is set.

## Gating (load-time filters)

Skills can be filtered at load time using `metadata` (single-line JSON):

```markdown
---
name: my-skill
description: A skill requiring a specific binary
metadata:
  {"openclaw": {"requires": {"bins": ["my-tool"], "env": ["MY_API_KEY"]}}}
---
```

Fields under `metadata.openclaw`:

- `always: true` — always include the skill (skip other gates).
- `os` — optional list of platforms (`darwin`, `linux`, `win32`).
- `requires.bins` — list; each must exist on `PATH`.
- `requires.anyBins` — list; at least one must exist on `PATH`.
- `requires.env` — list; env var must exist **or** be provided in config.
- `requires.config` — list of `openclaw.json` paths that must be truthy.
- `primaryEnv` — env var name associated with `skills.entries.<name>.apiKey`.

## Config overrides (`~/.openclaw/openclaw.json`)

```json5
{
  skills: {
    entries: {
      "my-skill": {
        enabled: true,
        apiKey: "API_KEY_HERE",
        env: {
          MY_API_KEY: "API_KEY_HERE",
        },
      },
      "some-bundled-skill": { enabled: false },
    },
  },
}
```

## Security notes

- Treat third-party skills as **untrusted code**. Read them before enabling.
- `skills.entries.*.env` and `skills.entries.*.apiKey` inject secrets into the
  **host** process for that agent turn.
