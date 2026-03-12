---
summary: "First-run onboarding flow for OpenClaw Python"
read_when:
  - Setting up OpenClaw Python for the first time
  - Implementing auth or identity setup
title: "Onboarding"
sidebarTitle: "Onboarding"
---

# Onboarding

This doc describes the **current** first-run onboarding flow for OpenClaw Python.
The goal is a smooth "day 0" experience: install, configure auth, run the
wizard, and let the agent bootstrap itself.
For a general overview of onboarding paths, see [Onboarding Overview](/start/onboarding-overview).

## Step 1: Install

```bash
pip install openclaw-python
```

## Step 2: Run the wizard

```bash
openclaw onboard
```

The wizard walks you through:

1. **Model/Auth** — Anthropic API key (recommended), OpenAI, or Custom Provider.
2. **Workspace** — Location for agent files (default `~/.openclaw/workspace`). Seeds bootstrap files.
3. **Gateway** — Port, bind address, auth mode.
4. **Channels** — Telegram, Discord, Slack, Signal, Matrix, or others.
5. **Daemon** — Installs a LaunchAgent (macOS) or systemd user unit (Linux/WSL2).
6. **Health check** — Starts the Gateway and verifies it's running.
7. **Skills** — Installs recommended skills and optional dependencies.

> Re-running the wizard does **not** wipe anything unless you explicitly choose **Reset** (or pass `--reset`).
> If the config is invalid or contains legacy keys, the wizard asks you to run `openclaw doctor` first.

## Step 3: Local vs Remote Gateway

Where does the **Gateway** run?

- **This machine (Local):** onboarding can run OAuth flows and write credentials
  locally.
- **Remote (over SSH/Tailnet):** onboarding does **not** run OAuth locally;
  credentials must exist on the gateway host.

## Step 4: Channels

Configure at least one channel to receive messages:

- [Telegram](/channels/telegram): bot token
- [Discord](/channels/discord): bot token
- [Slack](/channels/slack): bot token + app credentials
- [Signal](/channels/signal): optional `signal-cli` install + account config
- [Matrix (plugin)](/channels/matrix): homeserver URL + credentials

DM security default is **pairing**. First DM sends a pairing code; approve via
`openclaw pairing approve <channel> <code>` or configure allowlists.

## Step 5: Onboarding chat

After setup, you can send a message to your configured channel. The agent introduces
itself and guides next steps. See [Bootstrapping](/start/bootstrapping) for
what happens on the gateway host during the first agent run.

## Related docs

- [Onboarding Overview](/start/onboarding-overview)
- [CLI Wizard reference](/start/wizard)
- [CLI Automation](/start/wizard-cli-automation)
- [Bootstrapping](/start/bootstrapping)
