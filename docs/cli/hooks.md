---
summary: "CLI reference for `openclaw hooks` (agent hooks)"
read_when:
  - You want to manage agent lifecycle hooks
title: "hooks"
---

# `openclaw hooks`

Manage agent hooks (event-driven automations for commands and gateway lifecycle events).

## Commands

```bash
openclaw hooks list
openclaw hooks info <id>
openclaw hooks check [--eligible]
openclaw hooks enable <id>
openclaw hooks disable <id>
openclaw hooks install [--dir <path>]
openclaw hooks update [--dir <path>]
openclaw hooks test <name>
```

## Related docs

- [Hooks](/automation/hooks)

## Python implementation

- `openclaw/cli/hooks_cmd.py`
