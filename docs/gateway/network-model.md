---
summary: "How the Gateway, nodes, and canvas host connect."
read_when:
  - You want a concise view of the Gateway networking model
title: "Network model"
---

# Network model

Most operations flow through the Gateway (`openclaw gateway run`), a single long-running
process that owns channel connections and the WebSocket control plane.

## Core rules

- **One Gateway per host** is recommended. It is the only process allowed to own channel sessions.
  For rescue bots or strict isolation, run multiple gateways with isolated profiles and ports.
  See [Multiple gateways](/gateway/multiple-gateways).

- **Loopback first**: the Gateway HTTP/WS defaults to `http://127.0.0.1:4747`.
  The wizard generates a gateway token by default, even for loopback.
  For LAN/tailnet access, run `openclaw gateway run --bind lan` because tokens are required
  for non-loopback binds.

- **Nodes** connect to the Gateway WS over LAN, tailnet, or SSH as needed.

- **Canvas host** is served by the Gateway HTTP server on the **same port** as the Gateway
  (default `4747`):
  - `/__openclaw__/canvas/`
  - `/__openclaw__/a2ui/`

  When `gateway.auth` is configured and the Gateway binds beyond loopback, these routes are
  protected by Gateway auth (loopback requests are exempt).

- **Remote use** is typically SSH tunnel or tailnet VPN. See [Discovery](/gateway/discovery).

## Bind modes

| Mode | Address | Notes |
|------|---------|-------|
| `loopback` (default) | `127.0.0.1` | Secure; only local processes can connect |
| `lan` | `0.0.0.0` | All network interfaces; requires gateway auth token |
| `tailnet` | Tailscale IP | Tailnet-only; requires Tailscale running |

## Python implementation

- `openclaw/gateway/server.py` — `GatewayServer`, bind mode resolution
- `openclaw/gateway/http/` — HTTP endpoint handlers
- `openclaw/gateway/discovery.py` — Bonjour/mDNS beacon

## Related docs

- [Configuration reference](/gateway/configuration-reference)
- [Discovery](/gateway/discovery)
- [Multiple gateways](/gateway/multiple-gateways)
