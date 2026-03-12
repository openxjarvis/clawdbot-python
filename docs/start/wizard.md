---
summary: "CLI onboarding wizard: guided setup for gateway, workspace, channels, and skills"
read_when:
  - Running or configuring the onboarding wizard
  - Setting up a new machine
title: "Onboarding Wizard (CLI)"
sidebarTitle: "Onboarding: CLI"
---

# Onboarding Wizard (CLI)

The onboarding wizard is the **recommended** way to set up OpenClaw Python on macOS,
Linux, or Windows (via WSL2; strongly recommended).
It configures a local Gateway or a remote Gateway connection, plus channels, skills,
and workspace defaults in one guided flow.

```bash
openclaw onboard
```

> **Fastest first chat:** install OpenClaw Python, run `openclaw start`, and open
> `http://127.0.0.1:18789/` to chat in the browser.

To reconfigure later:

```bash
openclaw configure
openclaw agents add <name>
```

> `--json` does not imply non-interactive mode. For scripts, use `--non-interactive`.

## QuickStart vs Advanced

The wizard starts with **QuickStart** (defaults) vs **Advanced** (full control).

**QuickStart (defaults)**:

- Local gateway (loopback)
- Workspace default (or existing workspace)
- Gateway port **18789**
- Gateway auth **Token** (auto-generated, even on loopback)
- Tailscale exposure **Off**
- Telegram DMs default to **allowlist** (you'll be prompted for your phone number)

**Advanced (full control)**:

- Exposes every step (mode, workspace, gateway, channels, daemon, skills).

## What the wizard configures

**Local mode (default)** walks you through these steps:

1. **Model/Auth** — Anthropic API key (recommended), OpenAI, Gemini, or Custom Provider
   (OpenAI-compatible, Anthropic-compatible, or Unknown auto-detect). Pick a default model.
2. **Workspace** — Location for agent files (default `~/.openclaw/workspace`). Seeds bootstrap files.
3. **Gateway** — Port, bind address, auth mode, Tailscale exposure.
4. **Channels** — Telegram, Discord, Slack, Signal, Matrix.
5. **Daemon** — Installs a LaunchAgent (macOS) or systemd user unit (Linux/WSL2).
6. **Health check** — Starts the Gateway and verifies it's running.
7. **Skills** — Installs recommended skills and optional dependencies.

> Re-running the wizard does **not** wipe anything unless you explicitly choose **Reset** (or pass `--reset`).
> If the config is invalid or contains legacy keys, the wizard asks you to run `openclaw doctor` first.

**Remote mode** only configures the local client to connect to a Gateway elsewhere.
It does **not** install or change anything on the remote host.

## Add another agent

Use `openclaw agents add <name>` to create a separate agent with its own workspace,
sessions, and auth profiles. Running without `--workspace` launches the wizard.

What it sets:

- `agents.list[].name`
- `agents.list[].workspace`
- `agents.list[].agentDir`

Notes:

- Default workspaces follow `~/.openclaw/workspace-<agentId>`.
- Add `bindings` to route inbound messages (the wizard can do this).
- Non-interactive flags: `--model`, `--agent-dir`, `--bind`, `--non-interactive`.

## Full reference

For detailed step-by-step breakdowns, non-interactive scripting, and a full list of
config fields the wizard writes, see the
[CLI Onboarding Reference](/start/wizard-cli-reference).

## Related docs

- CLI automation and scripts: [CLI Automation](/start/wizard-cli-automation)
- Onboarding overview: [Onboarding Overview](/start/onboarding-overview)
- Agent first-run ritual: [Agent Bootstrapping](/start/bootstrapping)
