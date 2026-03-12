---
summary: "Health check steps for Gateway and channel connectivity"
read_when:
  - Diagnosing Gateway or channel health
title: "Health Checks"
---

# Health Checks (CLI)

Short guide to verify Gateway and channel connectivity.

## Quick checks

```bash
openclaw status                        # local summary
openclaw status --all                  # full local diagnosis
openclaw status --deep                 # probes the running Gateway
openclaw health --json                 # full health snapshot (WS)
openclaw gateway health                # HTTP health endpoint probe
openclaw doctor                        # configuration diagnostics
```

## Gateway health endpoint

The Gateway exposes a `GET /health` HTTP endpoint that returns a JSON object:

```json
{
  "status": "ok",
  "channels": { ... },
  "agents": { ... },
  "sessions": { ... },
  "heartbeat": { ... }
}
```

## Deep diagnostics

```bash
openclaw channels status --probe
openclaw logs --follow
openclaw doctor --deep
```

## When something fails

- `logged out` → relink with `openclaw channels logout && openclaw channels login`.
- Gateway unreachable → start it: `openclaw gateway run`.
- No inbound messages → confirm linked phone is online and the sender is allowed.

## `openclaw health` command

`openclaw health --json` asks the running Gateway for its health snapshot via the
HTTP `/health` endpoint. It reports:

- Per-channel status and probe summaries
- Session-store summary
- Agent statuses
- Heartbeat status

Exits non-zero if the Gateway is unreachable or the probe fails. Use `--timeout <ms>`
to override the 10s default.

## `openclaw gateway health` subcommand

`openclaw gateway health` pings `GET /health` on the Gateway HTTP endpoint and prints
a structured summary. Use `--host` and `--port` to override the target address.

## Python implementation

- `openclaw/monitoring/health.py` — `HealthChecker`, `HealthSummary`
- `openclaw/gateway/handlers.py` — `/health` HTTP route
- `openclaw/cli/gateway_cmd.py` — `health` subcommand

## Related docs

- [Troubleshooting](/gateway/troubleshooting)
- [Configuration](/gateway/configuration)
