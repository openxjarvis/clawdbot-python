---
summary: "Heartbeat polling messages and notification rules"
read_when:
  - Adjusting heartbeat cadence or messaging
  - Deciding between heartbeat and cron for scheduled tasks
title: "Heartbeat"
---

# Heartbeat (Gateway)

> **Heartbeat vs Cron?** See [Cron vs Heartbeat](/automation/cron-vs-heartbeat) for guidance.

Heartbeat runs **periodic agent turns** in the main session so the model can surface anything that needs attention.

## Python implementation

- `openclaw/gateway/heartbeat.py` — `HeartbeatConfig`, `HeartbeatManager`, `HeartbeatVisibilityConfig`, `ActiveHoursConfig`
- `resolve_heartbeat_config(agent_cfg, defaults_cfg)` — builds config from nested agent/defaults dicts

## Key config fields (aligned with TS)

| Field | Default | Description |
|---|---|---|
| `every` | `"30m"` | Interval ("30m", "1h", "0m" = disabled) |
| `model` | None | Optional model override |
| `include_reasoning` | False | Deliver separate `Reasoning:` message |
| `target` | `"last"` | `"last"` \| `"none"` \| channel id |
| `to` | None | Recipient override |
| `account_id` | None | Multi-account channel id |
| `prompt` | Default prompt | Custom prompt body (verbatim) |
| `ack_max_chars` | 300 | Max chars after `HEARTBEAT_OK` to still ack |
| `session` | `"main"` | Session key for heartbeat runs |
| `active_hours` | None | `ActiveHoursConfig(start, end, timezone)` |
| `visibility` | Defaults | `HeartbeatVisibilityConfig(show_ok, show_alerts, use_indicator)` |

## HEARTBEAT_OK contract

- If the model returns only `HEARTBEAT_OK` (optionally with ≤ `ack_max_chars` chars), treat as quiet ack.
- If `HEARTBEAT_OK` appears **in the middle** of a reply, it is NOT treated specially.
- `strip_heartbeat_ok(text)` removes leading/trailing HEARTBEAT_OK tokens.

## Visibility controls

```python
from openclaw.gateway.heartbeat import HeartbeatVisibilityConfig

# Default: silent OKs, deliver alerts
vis = HeartbeatVisibilityConfig(show_ok=False, show_alerts=True, use_indicator=True)
```

If all three flags are False, the heartbeat run is skipped entirely.

## Active hours

```python
from openclaw.gateway.heartbeat import ActiveHoursConfig

active = ActiveHoursConfig(start="09:00", end="22:00", timezone="America/New_York")
```
