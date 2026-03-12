---
summary: "Complete reference for CLI onboarding flow, auth/model setup, outputs, and internals"
read_when:
  - You need detailed behavior for openclaw onboard
  - You are debugging onboarding results or integrating onboarding clients
title: "CLI Onboarding Reference"
sidebarTitle: "CLI reference"
---

# CLI Onboarding Reference

This page is the full reference for `openclaw onboard`.
For the short guide, see [Onboarding Wizard (CLI)](/start/wizard).

## What the wizard does

Local mode (default) walks you through:

- Model and auth setup (Anthropic API key, OpenAI API key, Gemini, Moonshot, Cloudflare AI Gateway, and custom provider options)
- Workspace location and bootstrap files
- Gateway settings (port, bind, auth, tailscale)
- Channels and providers (Telegram, Discord, Slack, Signal, Matrix)
- Daemon install (LaunchAgent or systemd user unit)
- Health check
- Skills setup

Remote mode configures this machine to connect to a gateway elsewhere.
It does not install or modify anything on the remote host.

## Local flow details

### Step 1: Existing config detection

- If `~/.openclaw/openclaw.json` exists, choose Keep, Modify, or Reset.
- Re-running the wizard does not wipe anything unless you explicitly choose Reset (or pass `--reset`).
- If config is invalid or contains legacy keys, the wizard stops and asks you to run `openclaw doctor` before continuing.
- Reset uses `trash` and offers scopes:
  - Config only
  - Config + credentials + sessions
  - Full reset (also removes workspace)

### Step 2: Model and auth

See [Auth and model options](#auth-and-model-options) below.

### Step 3: Workspace

- Default `~/.openclaw/workspace` (configurable).
- Seeds workspace files needed for first-run bootstrap ritual.
- Workspace layout: [Agent workspace](/concepts/agent-workspace).

### Step 4: Gateway

- Prompts for port, bind, auth mode, and tailscale exposure.
- Recommended: keep token auth enabled even for loopback so local WS clients must authenticate.
- Disable auth only if you fully trust every local process.
- Non-loopback binds still require auth.

### Step 5: Channels

- [Telegram](/channels/telegram): bot token
- [Discord](/channels/discord): bot token
- [Slack](/channels/slack): bot token + app credentials
- [Signal](/channels/signal): optional `signal-cli` install + account config
- [Matrix](/channels/matrix): homeserver URL + credentials
- DM security: default is pairing. First DM sends a code; approve via
  `openclaw pairing approve <channel> <code>` or use allowlists.

### Step 6: Daemon install

- macOS: LaunchAgent
  - Requires logged-in user session; for headless, use a custom LaunchDaemon (not shipped).
- Linux and Windows via WSL2: systemd user unit
  - Wizard attempts `loginctl enable-linger <user>` so gateway stays up after logout.
  - May prompt for sudo (writes `/var/lib/systemd/linger`); it tries without sudo first.

### Step 7: Health check

- Starts gateway (if needed) and runs `openclaw health`.
- `openclaw status --deep` adds gateway health probes to status output.

### Step 8: Skills

- Reads available skills and checks requirements.
- Installs optional dependencies (some use Homebrew on macOS).

### Step 9: Finish

- Summary and next steps.

## Remote mode details

Remote mode configures this machine to connect to a gateway elsewhere.

> Remote mode does not install or modify anything on the remote host.

What you set:

- Remote gateway URL (`ws://...`)
- Token if remote gateway auth is required (recommended)

> If gateway is loopback-only, use SSH tunneling or a tailnet.

## Auth and model options

### Anthropic API key (recommended)

Uses `ANTHROPIC_API_KEY` if present or prompts for a key, then saves it for daemon use.

### Anthropic OAuth (Claude Code CLI)

- macOS: checks Keychain item "Claude Code-credentials"
- Linux and Windows: reuses `~/.claude/.credentials.json` if present

On macOS, choose "Always Allow" so launchd starts do not block.

### OpenAI API key

Uses `OPENAI_API_KEY` if present or prompts for a key, then saves it to
`~/.openclaw/.env` so launchd can read it.

### Gemini API key

Prompts for `GEMINI_API_KEY` and configures Gemini as a model provider.

### xAI (Grok) API key

Prompts for `XAI_API_KEY` and configures xAI as a model provider.

### Cloudflare AI Gateway

Prompts for account ID, gateway ID, and `CLOUDFLARE_AI_GATEWAY_API_KEY`.

### Moonshot and Kimi Coding

Moonshot (Kimi K2) and Kimi Coding configs are auto-written.

### Custom provider

Works with OpenAI-compatible and Anthropic-compatible endpoints.

Non-interactive flags:
- `--auth-choice custom-api-key`
- `--custom-base-url`
- `--custom-model-id`
- `--custom-api-key` (optional; falls back to `CUSTOM_API_KEY`)
- `--custom-provider-id` (optional)
- `--custom-compatibility <openai|anthropic>` (optional; default `openai`)

### Skip

Leaves auth unconfigured.

## Outputs and internals

Typical fields in `~/.openclaw/openclaw.json`:

- `agents.defaults.workspace`
- `agents.defaults.model`
- `gateway.*` (mode, bind, auth, tailscale)
- `channels.telegram.token`, `channels.discord.token`, `channels.slack.*`, `channels.signal.*`
- Channel allowlists when you opt in during prompts
- `wizard.lastRunAt`
- `wizard.lastRunVersion`
- `wizard.lastRunCommand`
- `wizard.lastRunMode`

`openclaw agents add` writes `agents.list[]` and optional `bindings`.

Sessions are stored under `~/.openclaw/agents/<agentId>/sessions/`.

> Some channels are delivered as plugins. When selected during onboarding, the wizard
> prompts to install the plugin (pip or local path) before channel configuration.

## Related docs

- Onboarding hub: [Onboarding Wizard (CLI)](/start/wizard)
- Automation and scripts: [CLI Automation](/start/wizard-cli-automation)
