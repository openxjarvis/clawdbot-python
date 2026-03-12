---
summary: "CLI reference for `openclaw agent` (send one agent turn via the Gateway)"
read_when:
  - You want to run one agent turn from scripts
title: "agent"
---

# `openclaw agent`

Run an agent turn via the Gateway. Use `--agent <id>` to target a configured agent.

## Examples

```bash
openclaw agent --to +15555550123 --message "status update" --deliver
openclaw agent --agent work --message "summarize today's tasks"
```

## Options

| Option | Description |
|--------|-------------|
| `--agent <id>` | Target agent ID |
| `--message <text>` | Message to send |
| `--to <recipient>` | Recipient address |
| `--deliver` | Deliver reply to recipient |
| `--json` | Output JSON |

## Python implementation

- `openclaw/cli/agent_cmd.py`
