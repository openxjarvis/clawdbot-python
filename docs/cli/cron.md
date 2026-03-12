---
summary: "CLI reference for `openclaw cron` (schedule and run background jobs)"
read_when:
  - You want scheduled jobs and wakeups
title: "cron"
---

# `openclaw cron`

Manage cron jobs for the Gateway scheduler.

## Commands

```bash
openclaw cron list
openclaw cron add --at "0 9 * * *" "Send daily summary"
openclaw cron edit <id> --at "0 10 * * *"
openclaw cron delete <id>
openclaw cron run <id>
openclaw cron status
openclaw cron enable <name>
openclaw cron disable <name>
```

## Related docs

- [Cron jobs](/automation/cron-jobs)

## Python implementation

- `openclaw/cli/cron_cmd.py`
