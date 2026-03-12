---
summary: "Run multiple OpenClaw Gateways on one host (isolation, ports, and profiles)"
read_when:
  - Running more than one Gateway on the same machine
  - You need isolated config/state/ports per Gateway
title: "Multiple Gateways"
---

# Multiple Gateways (same host)

Most setups should use one Gateway because a single Gateway can handle multiple messaging
connections and agents. If you need stronger isolation or redundancy (e.g., a rescue bot),
run separate Gateways with isolated profiles/ports.

## Isolation checklist (required)

- `OPENCLAW_CONFIG_PATH` — per-instance config file
- `OPENCLAW_STATE_DIR` — per-instance sessions, creds, caches
- `agents.defaults.workspace` — per-instance workspace root
- `gateway.port` (or `--port`) — unique per instance

If these are shared, you will hit config races and port conflicts.

## Recommended: profiles (`--profile`)

Profiles auto-scope `OPENCLAW_STATE_DIR` + `OPENCLAW_CONFIG_PATH` and suffix service names.

```bash
# main
openclaw --profile main gateway run --port 4747

# rescue
openclaw --profile rescue gateway run --port 4767
```

Per-profile services (launchd / systemd):

```bash
openclaw --profile main gateway install
openclaw --profile rescue gateway install
```

## Manual env example

```bash
OPENCLAW_CONFIG_PATH=~/.openclaw/main.json \
OPENCLAW_STATE_DIR=~/.openclaw-main \
openclaw gateway run --port 4747

OPENCLAW_CONFIG_PATH=~/.openclaw/rescue.json \
OPENCLAW_STATE_DIR=~/.openclaw-rescue \
openclaw gateway run --port 4767
```

## Quick status checks

```bash
openclaw --profile main status
openclaw --profile rescue status
```

## Port spacing

Leave at least 20 ports between base ports so derived ports (browser, canvas) never collide.

## Python implementation

- `OPENCLAW_STATE_DIR` env var scopes the state directory.
- `OPENCLAW_CONFIG_PATH` env var scopes the config file.
- `openclaw/config/paths.py` — `resolve_config_path()`, `resolve_state_dir()`

## Related docs

- [Network model](/gateway/network-model)
- [Configuration reference](/gateway/configuration-reference)
