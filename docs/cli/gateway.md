---
summary: "OpenClaw Gateway CLI (`openclaw gateway`) — run, query, and manage gateways"
read_when:
  - Running the Gateway from the CLI
  - Debugging Gateway connectivity
title: "gateway"
---

# Gateway CLI

The Gateway is OpenClaw's HTTP/WebSocket server (channels, agents, sessions, hooks).

## Subcommands

```bash
openclaw gateway run                   # Start the Gateway
openclaw gateway status                # Check Gateway status
openclaw gateway probe                 # Ping HTTP endpoint
openclaw gateway discover              # Browse mDNS for gateways
openclaw gateway health                # Health check via HTTP
openclaw gateway install               # Install as system service
openclaw gateway uninstall             # Uninstall service
openclaw gateway start                 # Start service
openclaw gateway stop                  # Stop service
openclaw gateway restart               # Restart service
openclaw gateway call <method>         # RPC call
```

## Related docs

- [Network model](/gateway/network-model)
- [Configuration](/gateway/configuration)
- [Bonjour](/gateway/bonjour)

## Python implementation

- `openclaw/cli/gateway_cmd.py`
