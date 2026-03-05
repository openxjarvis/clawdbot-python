# OpenClaw Python — User Guide

> Version 0.8.2

## Table of Contents

1. [Installation](#installation)
2. [Telegram Setup](#telegram-setup)
3. [Feishu Setup](#feishu-setup)
4. [Agent Workspace](#agent-workspace)
5. [CLI Reference](#cli-reference)

---

## Installation

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager

### Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Clone and install

```bash
git clone <repo-url> openclaw-python
cd openclaw-python
uv sync
```

### First-time setup (onboarding wizard)

```bash
uv run openclaw onboard
```

The wizard will guide you through:
- Setting your OpenRouter API key (or other LLM provider)
- Choosing a default model
- Configuring your workspace directory (`~/.openclaw/workspace/`)
- Setting up channels (Telegram / Feishu)

### Start the server

```bash
uv run openclaw start
```

This starts the gateway HTTP+WebSocket server (default port 3000) along with all configured channels.

### Verify everything is running

```bash
uv run openclaw status
uv run openclaw channels status
```

---

## Telegram Setup

### 1. Create a Telegram Bot

1. Open Telegram and message `@BotFather`
2. Send `/newbot` and follow the prompts
3. Copy the bot token (format: `123456789:ABCdef...`)

### 2. Configure the token

```bash
uv run openclaw config set channels.telegram.botToken "YOUR_BOT_TOKEN"
```

### 3. (Optional) Set allowed users

To restrict who can talk to the bot:

```bash
uv run openclaw config set channels.telegram.allowFrom '["@yourusername"]'
```

### 4. Restart and verify

```bash
uv run openclaw start
uv run openclaw channels status
```

You should see the Telegram channel listed as connected. Message your bot in Telegram to test.

### Pairing (for additional trust)

```bash
uv run openclaw pairing start telegram
```

---

## Feishu Setup

### 1. Create a Feishu Open Platform App

1. Go to [open.feishu.cn](https://open.feishu.cn/) → "Create App" → "Enterprise Self-built App"
2. Note your **App ID** and **App Secret**

### 2. Configure permissions (scopes)

In the app's "Permissions & Scopes" panel, enable:

| Scope | Purpose |
|---|---|
| `im:message` | Read messages |
| `im:message:send_as_bot` | Send messages |
| `im:message.reaction:write` | Typing indicator (emoji reactions) |
| `im:chat` | Chat management |
| `contact:user.id:readonly` | Resolve user IDs |

For advanced tools (calendar, bitable, docs, etc.), also enable:
- `calendar:calendar`, `calendar:calendar.event`
- `bitable:app`, `drive:drive`
- `docx:document`, `wiki:wiki`
- `task:task`

### 3. Enable Event Subscription (WebSocket mode)

In "Event Subscription":
- Use **Long Connection** (WebSocket) mode — no public webhook URL needed
- Subscribe to: `im.message.receive_v1`

### 4. Set bot behavior

In "Bot" → enable the bot feature.

### 5. Configure in OpenClaw

```bash
uv run openclaw config set channels.feishu.appId "cli_XXXXXXXX"
uv run openclaw config set channels.feishu.appSecret "YOUR_APP_SECRET"
```

### 6. Restart and verify

```bash
uv run openclaw start
uv run openclaw channels status
```

Send a message to your Feishu bot to test. You should see a `Typing` emoji reaction appear while the agent is processing.

### Available Feishu Tools (via the Feishu plugin)

The Feishu plugin (`extensions/feishu/`) provides agents with these tools:

| Tool | Description |
|---|---|
| `feishu_doc_*` | Create/read/update Feishu Docs |
| `feishu_wiki_*` | Search and manage Wiki spaces |
| `feishu_drive_*` | List and manage Drive files |
| `feishu_bitable_*` | 11 granular Bitable operations (tables, fields, records, views, forms) |
| `feishu_task_*` | Create and manage Tasks (v2 API) |
| `feishu_calendar_*` | List calendars and events |
| `feishu_urgent` | Send urgent messages |
| `feishu_chat_*` | Chat group operations |
| `feishu_reactions` | Add/remove message reactions |
| `feishu_perm_*` | Document permissions |

---

## Agent Workspace

All files the agent creates are stored in `~/.openclaw/workspace/` — a flat, git-initialized shared directory. This is intentional: it works like a user's home folder for the agent.

**Key rules:**
- Agent-generated files (scripts, CSVs, documents) go to `~/.openclaw/workspace/`, never into the project source directory
- The agent's working directory (`cwd`) should always be `~/.openclaw/workspace/`, not the project root
- `~/.openclaw/workspace/` is gitignored and never committed

### Directory structure overview

```
~/.openclaw/
├── openclaw.json           # Main config (edit via `openclaw config set`)
├── agents/main/
│   ├── agent/              # API key profiles (mode 0600)
│   └── sessions/           # Session transcripts (.jsonl)
├── credentials/            # OAuth tokens, channel pairing state
├── cron/                   # Scheduled job definitions and run history
├── delivery-queue/         # Write-ahead log for outbound messages
├── feishu/dedup/           # Feishu message deduplication store
├── identity/               # Device identity and auth tokens
├── logs/                   # Gateway logs and config audit log
├── media/                  # Media pipeline storage + remote-cache
├── sandboxes/              # Per-session Docker sandbox workspaces (future)
├── telegram/               # Telegram polling offset and sticker cache
└── workspace/              # Agent working directory (flat, shared)
    ├── .git/
    ├── AGENTS.md           # Agent instruction boundary file
    ├── SOUL.md             # Agent personality
    └── (agent files...)
```

To see your actual paths:

```bash
uv run openclaw directory
```

---

## CLI Reference

Run `uv run openclaw <command> --help` for full options on any command.

### Core

| Command | Description |
|---|---|
| `openclaw start` | Start gateway + all channels |
| `openclaw stop` | Stop all services |
| `openclaw restart` | Restart services |
| `openclaw status` | Show service health |
| `openclaw version` | Show version |
| `openclaw doctor` | Run diagnostics |

### Setup & Configuration

| Command | Description |
|---|---|
| `openclaw onboard` | Interactive first-time setup wizard |
| `openclaw setup` | Re-run setup wizard |
| `openclaw configure` | Re-run configuration wizard |
| `openclaw config get <path>` | Get a config value (e.g. `agents.defaults.model`) |
| `openclaw config set <path> <value>` | Set a config value |
| `openclaw config unset <path>` | Remove a config value |
| `openclaw config show` | Show full configuration |
| `openclaw config path` | Show config file path |
| `openclaw directory` | Show all state directory paths |

### Models

| Command | Description |
|---|---|
| `openclaw models list` | List configured models |
| `openclaw models set <model-id>` | Set default model |
| `openclaw models set-image <model-id>` | Set image model |
| `openclaw models scan` | Scan OpenRouter for available models |
| `openclaw models status` | Show model configuration |
| `openclaw models aliases` | Manage model aliases |
| `openclaw models auth` | Manage provider auth profiles |

**Example — switch to Gemini:**
```bash
uv run openclaw models set gemini-2.5-pro-preview
# or set API key for a specific provider:
uv run openclaw config set agents.defaults.apiKey "YOUR_GEMINI_KEY"
uv run openclaw config set agents.defaults.model "gemini-2.5-pro-preview"
```

### Channels

| Command | Description |
|---|---|
| `openclaw channels list` | List configured channels |
| `openclaw channels status` | Show connection status |
| `openclaw channels add <type>` | Add/update a channel account |
| `openclaw channels remove <account>` | Remove a channel account |
| `openclaw channels login <account>` | Trigger login flow |
| `openclaw channels logs <account>` | Show recent channel logs |
| `openclaw channels capabilities` | Show provider capabilities |

### Pairing

| Command | Description |
|---|---|
| `openclaw pairing start <channel>` | Start pairing flow |
| `openclaw pairing status` | Show pairing state |
| `openclaw pairing list` | List paired devices/accounts |

### Agent

| Command | Description |
|---|---|
| `openclaw agent run <task>` | Run agent with a task |
| `openclaw agent status` | Show agent status |
| `openclaw agent sessions` | List sessions |

### Cron (Scheduled Tasks)

| Command | Description |
|---|---|
| `openclaw cron list` | List all cron jobs |
| `openclaw cron add --at "<schedule>" --message "<task>"` | Add a cron job |
| `openclaw cron edit <job-id>` | Edit a cron job |
| `openclaw cron delete <job-id>` | Delete a cron job |
| `openclaw cron status [job-id]` | Show job execution history |

**Example — daily reminder:**
```bash
uv run openclaw cron add --at "0 9 * * *" --message "Send me a morning briefing"
```

### Memory

| Command | Description |
|---|---|
| `openclaw memory search <query>` | Search agent memory |
| `openclaw memory list` | List memory entries |

### Gateway & Daemon

| Command | Description |
|---|---|
| `openclaw gateway start` | Start gateway only |
| `openclaw gateway stop` | Stop gateway |
| `openclaw gateway status` | Show gateway status |
| `openclaw daemon install` | Install as system service (launchd/systemd) |
| `openclaw daemon uninstall` | Remove system service |
| `openclaw daemon start` | Start daemon |
| `openclaw daemon stop` | Stop daemon |
| `openclaw daemon status` | Show daemon status |

### Tools & Plugins

| Command | Description |
|---|---|
| `openclaw tools list` | List all registered agent tools |
| `openclaw plugins list` | List installed plugins |
| `openclaw plugins install <name>` | Install a plugin from npm |
| `openclaw skills list` | List available agent skills |

### Utilities

| Command | Description |
|---|---|
| `openclaw logs` | Show gateway logs |
| `openclaw message send <channel> <text>` | Send a message |
| `openclaw hooks list` | List lifecycle hooks |
| `openclaw security audit` | Security audit |
| `openclaw nodes list` | List connected nodes |
| `openclaw devices list` | List paired devices |
| `openclaw dns setup` | Configure mDNS/Bonjour |
| `openclaw completion install` | Install shell completion |
| `openclaw cleanup` | Clean up ports and zombie processes |
| `openclaw tui` | Launch terminal UI (interactive) |
