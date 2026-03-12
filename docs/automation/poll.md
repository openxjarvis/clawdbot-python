---
summary: "Poll sending via gateway + CLI"
read_when:
  - Adding or modifying poll support
  - Debugging poll sends from the CLI or gateway
title: "Polls"
---

# Polls

## Supported channels

- Telegram
- Discord
- MS Teams (Adaptive Cards)

## CLI

```bash
# Telegram
openclaw message poll --channel telegram --target +15555550123 \
  --poll-question "Lunch today?" --poll-option "Yes" --poll-option "No" --poll-option "Maybe"
openclaw message poll --channel telegram --target 123456789 \
  --poll-question "Meeting time?" --poll-option "10am" --poll-option "2pm" --poll-option "4pm" --poll-multi

# Discord
openclaw message poll --channel discord --target channel:123456789 \
  --poll-question "Snack?" --poll-option "Pizza" --poll-option "Sushi"
openclaw message poll --channel discord --target channel:123456789 \
  --poll-question "Plan?" --poll-option "A" --poll-option "B" --poll-duration-hours 48

# MS Teams
openclaw message poll --channel msteams --target conversation:19:abc@thread.tacv2 \
  --poll-question "Lunch?" --poll-option "Pizza" --poll-option "Sushi"
```

Options:

- `--channel`: `telegram` (default), `discord`, or `msteams`
- `--poll-multi`: allow selecting multiple options
- `--poll-duration-hours`: Discord-only (defaults to 24 when omitted)

## Gateway RPC

Method: `poll`

Params:

- `to` (string, required)
- `question` (string, required)
- `options` (string[], required)
- `maxSelections` (number, optional)
- `durationHours` (number, optional)
- `channel` (string, optional, default: `telegram`)
- `idempotencyKey` (string, required)

## Channel differences

- Telegram: native poll with up to 10 options; `maxSelections > 1` enables multiple answers; `durationHours` is ignored.
- Discord: 2-10 options, `durationHours` clamped to 1-768 hours (default 24). `maxSelections > 1` enables multi-select; Discord does not support a strict selection count.
- MS Teams: Adaptive Card polls (OpenClaw-managed). No native poll API; `durationHours` is ignored.

## Agent tool (Message)

Use the `message` tool with `poll` action (`to`, `pollQuestion`, `pollOption`, optional `pollMulti`, `pollDurationHours`, `channel`).

Note: Discord has no "pick exactly N" mode; `pollMulti` maps to multi-select.
Teams polls are rendered as Adaptive Cards and require the gateway to stay online
to record votes in `~/.openclaw/msteams-polls.json`.
