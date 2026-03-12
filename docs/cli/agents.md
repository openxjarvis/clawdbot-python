---
summary: "CLI reference for `openclaw agents` (list/add/delete/set identity)"
read_when:
  - You want multiple isolated agents (workspaces + routing + auth)
title: "agents"
---

# `openclaw agents`

Manage isolated agents (workspaces + auth + routing).

## Examples

```bash
openclaw agents list
openclaw agents add --id work --workspace ~/work
openclaw agents delete --id work
openclaw agents set-default --id work
```

## Python implementation

- `openclaw/cli/agent_cmd.py`
