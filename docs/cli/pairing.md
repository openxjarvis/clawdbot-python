---
summary: "CLI reference for `openclaw pairing` (manage pairing approvals for channels)"
read_when:
  - You want to approve or reject senders
title: "pairing"
---

# `openclaw pairing`

Manage channel pairing (approve/reject senders for channels).

```bash
openclaw pairing list
openclaw pairing list telegram
openclaw pairing approve <id>
openclaw pairing reject <id>
openclaw pairing status
```

## Python implementation

- `openclaw/cli/pairing_cmd.py`
