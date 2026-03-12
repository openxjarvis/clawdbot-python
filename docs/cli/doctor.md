---
summary: "CLI reference for `openclaw doctor` (health checks + guided repairs)"
read_when:
  - You have connectivity/auth issues and want guided fixes
  - You updated and want a sanity check
title: "doctor"
---

# `openclaw doctor`

Health checks + quick fixes for the gateway and channels.

## Examples

```bash
openclaw doctor
openclaw doctor --deep
openclaw doctor --repair
openclaw doctor --generate-gateway-token
openclaw doctor --json
```

## Checks performed

- Python version (>= 3.11 required)
- Config file existence and validity
- Workspace directory
- State directory permissions
- Legacy config key migrations
- Gateway port reachability (with `--deep`)
- Channel credentials (with `--deep`)
- Skills directory (with `--deep`)

## Related docs

- [Troubleshooting](/gateway/troubleshooting)

## Python implementation

- `openclaw/cli/main.py` — `doctor()` function
