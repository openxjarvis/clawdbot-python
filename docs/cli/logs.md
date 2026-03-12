---
summary: "CLI reference for `openclaw logs` (tail gateway logs)"
read_when:
  - You need to tail Gateway logs
  - You want JSON log lines for tooling
title: "logs"
---

# `openclaw logs`

Tail Gateway file logs.

## Examples

```bash
openclaw logs
openclaw logs --follow
openclaw logs --level debug
openclaw logs --json
```

## Python implementation

- `openclaw/cli/logs_cmd.py`
