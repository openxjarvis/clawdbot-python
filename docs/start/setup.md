---
summary: "Advanced setup and development workflows for OpenClaw Python"
read_when:
  - Setting up a new machine
  - You want to run from source or contribute
title: "Setup"
---

# Setup

> If you are setting up for the first time, start with [Getting Started](/start/getting-started).
> For wizard details, see [Onboarding Wizard](/start/wizard).

## TL;DR

- **Tailoring lives outside the repo:** `~/.openclaw/workspace` (workspace) + `~/.openclaw/openclaw.json` (config).
- **Stable workflow:** install from PyPI; run `openclaw start`.
- **Development workflow:** clone the repo, install in editable mode, run `openclaw gateway:watch` equivalent.

## Prereqs

- Python `>=3.11`
- `pip` or `pipx`
- (optional) Docker for containerized setup

## Tailoring strategy (so updates don't hurt)

If you want "100% tailored to me" _and_ easy updates, keep your customization in:

- **Config:** `~/.openclaw/openclaw.json` (JSON/JSON5-ish)
- **Workspace:** `~/.openclaw/workspace` (skills, prompts, memories; make it a private git repo)

Bootstrap once:

```bash
openclaw setup
```

## Install from PyPI (stable)

```bash
pip install openclaw-python
openclaw setup
openclaw onboard
```

## Install from source (development)

```bash
git clone https://github.com/openclaw/openclaw-python.git
cd openclaw-python
pip install -e ".[dev]"
openclaw setup
```

## Run the Gateway

```bash
openclaw start
```

Or in verbose mode:

```bash
openclaw gateway --port 18789 --verbose
```

## Credential storage map

Use this when debugging auth or deciding what to back up:

- **Telegram bot token**: config (`channels.telegram.token`) or env (`TELEGRAM_BOT_TOKEN`)
- **Discord bot token**: config (`channels.discord.token`) or env (`DISCORD_BOT_TOKEN`)
- **Anthropic API key**: config (`models.providers.anthropic.apiKey`) or env (`ANTHROPIC_API_KEY`)
- **OpenAI API key**: config (`models.providers.openai.apiKey`) or env (`OPENAI_API_KEY`)
- **Pairing allowlists**: `~/.openclaw/credentials/<channel>-allowFrom.json`
- **OAuth credentials**: `~/.openclaw/credentials/oauth.json`

## Updating (without wrecking your setup)

```bash
pip install --upgrade openclaw-python
```

Keep `~/.openclaw/workspace` and `~/.openclaw/` as "your stuff"; don't put personal prompts/config into the source repo.

## Linux (systemd user service)

Linux installs use a systemd **user** service. By default, systemd stops user
services on logout/idle, which kills the Gateway. Onboarding attempts to enable
lingering for you (may prompt for sudo). If it's still off, run:

```bash
sudo loginctl enable-linger $USER
```

For always-on or multi-user servers, consider a **system** service instead of a
user service (no lingering needed). See [Gateway runbook](/gateway) for the systemd notes.

## Related docs

- [Gateway runbook](/gateway) (flags, supervision, ports)
- [Gateway configuration](/gateway/configuration) (config schema + examples)
- [OpenClaw assistant setup](/start/openclaw)
