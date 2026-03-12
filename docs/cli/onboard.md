---
summary: "Interactive onboarding wizard for new installations"
read_when:
  - Setting up OpenClaw for the first time
title: "onboard"
---

# `openclaw onboard`

Run the interactive onboarding wizard for new installations.

```bash
openclaw onboard
```

Guides you through:

1. Provider selection and API key entry
2. Channel setup (WhatsApp/Telegram/Discord)
3. Gateway configuration and service installation
4. First agent run

## Python implementation

- `openclaw/cli/misc_cmd.py` — `onboard` command
