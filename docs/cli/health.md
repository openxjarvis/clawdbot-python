---
summary: "CLI reference for `openclaw health` (full health snapshot)"
read_when:
  - You want a health snapshot from the running Gateway
title: "health"
---

# `openclaw health`

Asks the running Gateway for its health snapshot.

```bash
openclaw health
openclaw health --json
openclaw health --timeout 5000
```

Exits non-zero if the Gateway is unreachable or the probe fails.

## Related docs

- [Health Checks](/gateway/health)
