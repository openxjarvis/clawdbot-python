---
summary: "CLI reference for `openclaw sandbox` (explain/check sandbox settings)"
read_when:
  - Debugging sandbox mode for tool execution
title: "sandbox"
---

# `openclaw sandbox`

Inspect and explain the active sandbox settings.

```bash
openclaw sandbox explain
openclaw sandbox explain --agent work
openclaw sandbox explain --json
openclaw sandbox status
```

## Related docs

- [Sandbox vs Tool Policy vs Elevated](/gateway/sandbox-vs-tool-policy-vs-elevated)
- [Sandboxing](/gateway/sandboxing)

## Python implementation

- `openclaw/cli/sandbox_cmd.py`
