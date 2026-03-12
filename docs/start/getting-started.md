---
summary: "Get OpenClaw Python installed and run your first chat in minutes."
read_when:
  - First time setup from zero
  - You want the fastest path to a working chat
title: "Getting Started"
---

# Getting Started

Goal: go from zero to a first working chat with minimal setup.

> **Fastest chat:** install OpenClaw Python, run `openclaw start`, and chat via
> the Control UI at `http://127.0.0.1:18789/`.

## Prereqs

- Python 3.11 or newer

Check your Python version with `python --version` if you are unsure.

## Quick setup

### 1. Install OpenClaw Python

```bash
pip install openclaw-python
```

Or with pipx for isolated installs:

```bash
pipx install openclaw-python
```

### 2. Run the onboarding wizard

```bash
openclaw onboard
```

The wizard configures auth, gateway settings, and optional channels.
See [Onboarding Wizard](/start/wizard) for details.

### 3. Check the Gateway

If you installed the service, it should already be running:

```bash
openclaw gateway status
```

### 4. Open the Control UI

```bash
openclaw dashboard
```

If the Control UI loads, your Gateway is ready for use.

## Optional checks and extras

**Run the Gateway in the foreground** (useful for quick tests or troubleshooting):

```bash
openclaw gateway --port 18789
```

**Send a test message** (requires a configured channel):

```bash
openclaw message send --target +15555550123 --message "Hello from OpenClaw"
```

## Useful environment variables

If you run OpenClaw as a service account or want custom config/state locations:

- `OPENCLAW_HOME` sets the home directory used for internal path resolution.
- `OPENCLAW_STATE_DIR` overrides the state directory.
- `OPENCLAW_CONFIG_PATH` overrides the config file path.

## What you will have

- A running Gateway
- Auth configured
- Control UI access or a connected channel

## Next steps

- Connect more channels: [Channels](/channels)
- Set up automation: [Cron jobs](/automation/cron-jobs)
- Install plugins: [Plugins](/plugins/manifest)
- Advanced setup: [Setup](/start/setup)
