---
summary: "Deep troubleshooting runbook for gateway, channels, and automation"
read_when:
  - Gateway is not responding
  - Channels are not receiving messages
  - You need a diagnostic command ladder
title: "Troubleshooting"
---

# Gateway troubleshooting

## Command ladder

Run these first, in this order:

```bash
openclaw status
openclaw gateway status
openclaw logs --follow
openclaw doctor
openclaw channels status --probe
```

Expected healthy signals:

- `openclaw gateway status` shows `Runtime: running`.
- `openclaw doctor` reports no blocking config/service issues.
- `openclaw channels status --probe` shows connected/ready channels.

## No replies

If channels are up but nothing answers, check routing and policy:

```bash
openclaw status
openclaw channels status --probe
openclaw config get channels
openclaw logs --follow
```

Common causes:

- Pairing pending for DM senders.
- Group mention gating (`requireMention`, `mentionPatterns`).
- Channel/group allowlist mismatches.

## Gateway not starting

```bash
openclaw doctor --deep
openclaw gateway run --port 4747
```

Check for:

- Port conflict (another process on port 4747).
- Missing config file — run `openclaw onboard`.
- State directory permissions — run `openclaw doctor --repair`.

## Gateway service not running (systemd / launchd)

```bash
openclaw gateway status
openclaw gateway start
openclaw logs --follow
```

Check the service log for errors:

```bash
openclaw logs --follow --level error
```

## Channel connectivity

```bash
openclaw channels status --probe
openclaw channels login
```

- `logged out` → relink with `openclaw channels logout && openclaw channels login`.

## Logs

```bash
openclaw logs --follow
openclaw logs --follow --level debug
```

Log file location: `/tmp/openclaw/openclaw-YYYY-MM-DD.log`

## Deep diagnostics

```bash
openclaw doctor --deep
openclaw gateway health
openclaw gateway probe
```

## Python implementation

- `openclaw/cli/main.py` — `doctor` command with deep checks
- `openclaw/cli/gateway_cmd.py` — `gateway status`, `probe`, `health` subcommands
- `openclaw/monitoring/health.py` — health check helpers

## Related docs

- [Health Checks](/gateway/health)
- [Doctor command](/gateway/doctor)
- [Configuration reference](/gateway/configuration-reference)
