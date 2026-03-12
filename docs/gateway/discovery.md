---
summary: "Node discovery and transports (Bonjour, Tailscale, SSH) for finding the gateway"
read_when:
  - Implementing or changing Bonjour discovery/advertising
  - Adjusting remote connection modes (direct vs SSH)
  - Designing node discovery + pairing for remote nodes
title: "Discovery and Transports"
---

# Discovery & transports

OpenClaw has two distinct problems that look similar on the surface:

1. **Operator remote control**: the macOS menu bar app controlling a gateway running elsewhere.
2. **Node pairing**: iOS/Android (and future nodes) finding a gateway and pairing securely.

## Terms

- **Gateway**: a single long-running gateway process that owns state (sessions, pairing, node registry) and runs channels.
- **Gateway WS (control plane)**: the WebSocket endpoint on `127.0.0.1:18789` by default.
- **Direct WS transport**: a LAN/tailnet-facing Gateway WS endpoint.
- **SSH transport (fallback)**: remote control by forwarding `127.0.0.1:18789` over SSH.

## Discovery inputs

### 1) Bonjour / mDNS (LAN only)

The gateway advertises its WS endpoint via Bonjour (`_openclaw-gw._tcp`).

#### Service beacon details

- Service type: `_openclaw-gw._tcp`
- TXT keys (non-secret):
  - `role=gateway`
  - `lanHost=<hostname>.local`
  - `sshPort=22` (omitted in minimal mode)
  - `gatewayPort=18789`
  - `gatewayTls=1` (only when TLS is enabled)
  - `gatewayTlsSha256=<sha256>` (only when TLS and fingerprint are available)
  - `canvasPort=<port>` (optional)
  - `cliPath=<path>` (optional; omitted in minimal mode)
  - `tailnetDns=<magicdns>` (optional hint)

Security notes:

- Bonjour/mDNS TXT records are **unauthenticated** — treat as UX hints only.
- TLS pinning must never allow an advertised `gatewayTlsSha256` to override a previously stored pin.

Disable/override:

- `OPENCLAW_DISABLE_BONJOUR=1` disables advertising.
- `gateway.bind` controls the Gateway bind mode.
- `OPENCLAW_SSH_PORT` overrides the SSH port advertised in TXT (defaults to 22).

### 2) Tailnet (cross-network)

If the gateway detects Tailscale, it publishes `tailnetDns` as an optional hint.

### 3) Manual / SSH target

When there is no direct route, clients can connect via SSH by forwarding the loopback gateway port.

## Transport selection (client policy)

1. If a paired direct endpoint is configured and reachable, use it.
2. Else, if Bonjour finds a gateway on LAN, use it.
3. Else, if a tailnet DNS/IP is configured, try direct.
4. Else, fall back to SSH.

## Python implementation

- **`openclaw/gateway/discovery.py`** — `GatewayDiscovery` class, `GatewayBonjourOpts` dataclass, `_build_txt_records()`, `GATEWAY_BONJOUR_SERVICE_TYPE = "_openclaw-gw._tcp.local."`.
- Service type uses `_openclaw-gw._tcp` (previously incorrect `_openclaw._tcp`).
- All TXT keys from TS are supported: `role`, `lanHost`, `gatewayPort`, `sshPort`, `gatewayTls`, `gatewayTlsSha256`, `canvasPort`, `tailnetDns`, `cliPath`, `transport`, `displayName`.
- Minimal mode omits `sshPort` and `cliPath`.
