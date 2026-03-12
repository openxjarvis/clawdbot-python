---
summary: "Bonjour/mDNS discovery + debugging (Gateway beacons, clients, and common failure modes)"
read_when:
  - Debugging Bonjour discovery issues on macOS/iOS
  - Changing mDNS service types, TXT records, or discovery UX
title: "Bonjour Discovery"
---

# Bonjour / mDNS discovery

OpenClaw uses Bonjour (mDNS / DNS-SD) as a **LAN-only convenience** to discover
an active Gateway (WebSocket endpoint). It is best-effort and does **not** replace SSH or
Tailnet-based connectivity.

## Service type

- `_openclaw-gw._tcp` — gateway transport beacon

## TXT keys (non-secret hints)

The Gateway advertises small non-secret hints to make UI flows convenient:

- `role=gateway`
- `displayName=<friendly name>`
- `lanHost=<hostname>.local`
- `gatewayPort=<port>` (Gateway WS + HTTP)
- `gatewayTls=1` (only when TLS is enabled)
- `gatewayTlsSha256=<sha256>` (only when TLS is enabled and fingerprint is available)
- `canvasPort=<port>` (only when the canvas host is enabled)
- `sshPort=<port>` (defaults to 22)
- `transport=gateway`
- `cliPath=<path>` (optional; absolute path to a runnable `openclaw` entrypoint)
- `tailnetDns=<magicdns>` (optional hint when Tailnet is available)

Security notes:

- Bonjour/mDNS TXT records are **unauthenticated**. Clients must not treat TXT as authoritative routing.
- Clients should route using the resolved service endpoint (SRV + A/AAAA). Treat `lanHost`, `tailnetDns`, `gatewayPort`, and `gatewayTlsSha256` as hints only.

## Wide-area Bonjour (Unicast DNS-SD) over Tailscale

If the node and gateway are on different networks, multicast mDNS won't cross the
boundary. You can keep the same discovery UX by switching to **unicast DNS-SD**
("Wide-Area Bonjour") over Tailscale.

High-level steps:

1. Run a DNS server on the gateway host (reachable over Tailnet).
2. Publish DNS-SD records for `_openclaw-gw._tcp` under a dedicated zone
   (example: `openclaw.internal.`).
3. Configure Tailscale **split DNS** so your chosen domain resolves via that
   DNS server for clients.

### Gateway config (recommended)

```json
{
  "gateway": { "bind": "tailnet" },
  "discovery": { "wideArea": { "enabled": true } }
}
```

## Debugging

Useful built-in tools (macOS):

```bash
# Browse instances
dns-sd -B _openclaw-gw._tcp local.

# Resolve one instance
dns-sd -L "<instance>" _openclaw-gw._tcp local.
```

Gateway logs: look for `bonjour:` lines, especially:

- `bonjour: advertise failed ...`
- `bonjour: ... name conflict resolved`

## Common failure modes

- **Bonjour doesn't cross networks**: use Tailnet or SSH.
- **Multicast blocked**: some Wi-Fi networks disable mDNS.
- **Sleep / interface churn**: macOS may temporarily drop mDNS results; retry.

## Disabling / configuration

- `OPENCLAW_DISABLE_BONJOUR=1` disables advertising.
- `OPENCLAW_SSH_PORT` overrides the SSH port advertised in TXT.
- `OPENCLAW_TAILNET_DNS` publishes a MagicDNS hint in TXT.
- `OPENCLAW_CLI_PATH` overrides the advertised CLI path.

## Python implementation

- `openclaw/gateway/discovery.py` — `GatewayDiscovery`, `GatewayBonjourOpts`, `_build_txt_records()`
- `GATEWAY_BONJOUR_SERVICE_TYPE = "_openclaw-gw._tcp.local."`

## Related docs

- [Discovery](/gateway/discovery)
- [Multiple Gateways](/gateway/multiple-gateways)
