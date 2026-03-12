---
summary: "CLI reference for `openclaw nodes` (list/approve/reject connected nodes)"
read_when:
  - You want to manage connected nodes (iOS, remote machines)
title: "nodes"
---

# `openclaw nodes`

Manage connected nodes (iOS app, remote machines).

```bash
openclaw nodes list
openclaw nodes pending
openclaw nodes approve <requestId>
openclaw nodes reject <requestId>
openclaw nodes status
openclaw nodes rename --node <id> --name "My iPad"
```

## Related docs

- [Pairing](/gateway/pairing)

## Python implementation

- `openclaw/cli/nodes_cmd.py`
