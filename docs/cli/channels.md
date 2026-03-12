---
summary: "CLI reference for `openclaw channels` (accounts, status, login/logout)"
read_when:
  - You want to add/remove channel accounts
  - You want to check channel status
title: "channels"
---

# `openclaw channels`

Manage chat channel accounts and their runtime status on the Gateway.

## Common commands

```bash
openclaw channels list
openclaw channels status
openclaw channels status --probe
openclaw channels login
openclaw channels logout
openclaw channels login --verbose
```

## Related docs

- [Channels](/channels/index)

## Python implementation

- `openclaw/cli/channels_cmd.py`
