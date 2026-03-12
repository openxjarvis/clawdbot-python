---
summary: "CLI reference for `openclaw models` (status/list/set/scan)"
read_when:
  - You want to change default models or view provider auth status
title: "models"
---

# `openclaw models`

Model discovery, scanning, and configuration.

## Common commands

```bash
openclaw models list
openclaw models scan
openclaw models status
openclaw models set --model claude-3-5-sonnet
openclaw models auth --provider anthropic --key $ANTHROPIC_API_KEY
```

## Related docs

- [Providers](/providers/models)

## Python implementation

- `openclaw/cli/models_cmd.py`
