# OpenXJarvis (openclaw-python)

> A Python implementation of the OpenClaw AI assistant gateway — aligned with the TypeScript reference implementation

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MIT License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**OpenXJarvis** is a full-featured Python port of OpenClaw: a personal AI gateway that connects messaging channels (Telegram, Discord) with AI models (Claude, Gemini, GPT-4), manages sessions and memory, runs scheduled tasks (cron), and exposes a WebSocket API with a built-in Web Control UI.

---

## Preview

<img src="assets/telegram-preview.jpg" alt="Jarvis on Telegram" width="360" />

*Jarvis responding on Telegram — powered by OpenXJarvis*

---

## Dependencies: pi-mono-python

`openclaw-python` depends on **[pi-mono-python](https://github.com/openxjarvis/pi-mono-python)** — a companion repo that provides the core agent and LLM infrastructure as local packages:

| Package | Provides |
|---|---|
| `pi-ai` | Unified LLM streaming layer (Gemini, Anthropic, OpenAI, …) |
| `pi-agent` | Agent loop, tool execution, session state |
| `pi-coding-agent` | Coding agent with file/bash/search tools |
| `pi-tui` | Terminal UI rendering engine |

These packages are resolved by `uv` as **path dependencies** relative to the parent directory. Both repos must be cloned as siblings inside the same parent directory (the name of the parent directory does not matter):

```
my-workspace/              ← any name works
├── openclaw-python/       ← this repo
└── pi-mono-python/        ← required sibling
```

---

## Getting Started

### 1. Install

**Prerequisites:** Python 3.11+ and [uv](https://docs.astral.sh/uv/) package manager.

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create a workspace directory (any name) and clone both repos into it
mkdir my-workspace && cd my-workspace

git clone https://github.com/openxjarvis/pi-mono-python.git
git clone https://github.com/openxjarvis/openclaw-python.git

# Install (uv resolves pi-mono-python packages automatically)
cd openclaw-python
uv sync
```

### 2. Onboard

Run the interactive setup wizard:

```bash
uv run openclaw onboard
```

The wizard guides you through model selection, Telegram configuration, workspace initialization, and optional daemon installation. **It will prompt for API keys interactively and save them to `.env` automatically** — you do not need to create `.env` by hand first.

If you already have a `.env` with keys set, the wizard detects them and skips those prompts:

```bash
# Optional: pre-populate .env before onboarding
cp .env.example .env
# then edit .env with your keys, then run the wizard
```

Onboarding creates your `~/.openclaw/` workspace and config. **Run this once per new environment.**

---

## Starting the Gateway

The gateway is the core server. It manages the agent runtime, channels, sessions, cron, and serves the Web Control UI.

### Foreground (development)

```bash
uv run openclaw gateway run
```

Logs stream directly to the terminal. Press `Ctrl+C` to stop.

### Background daemon (recommended for production)

```bash
# Install as a system service (launchd on macOS, systemd on Linux)
uv run openclaw gateway install

# Start / stop / restart
uv run openclaw gateway start
uv run openclaw gateway stop
uv run openclaw gateway restart

# Check status and tail logs
uv run openclaw gateway status
uv run openclaw gateway logs
```

### Web Control UI

Once the gateway is running, open your browser at:

```
http://localhost:18789
```

The UI lets you chat with the agent, inspect sessions, manage cron jobs, and configure settings.

---

## Key Commands

| Command | Description |
|---|---|
| `uv run openclaw onboard` | Interactive setup wizard |
| `uv run openclaw gateway run` | Start gateway in foreground |
| `uv run openclaw gateway install` | Install as background daemon |
| `uv run openclaw gateway start/stop/restart` | Manage background daemon |
| `uv run openclaw gateway status` | Check daemon status |
| `uv run openclaw gateway logs` | Tail gateway logs |
| `uv run openclaw doctor` | Run system diagnostics |
| `uv run openclaw config show` | Show current configuration |
| `uv run openclaw cleanup` | Clean up processes, ports, and stale state |

### Cleanup

Use `cleanup` when the gateway is stuck, a port is already in use, or you want to reset to a clean state:

```bash
# Kill all openclaw processes
uv run openclaw cleanup --kill-all

# Free a specific port
uv run openclaw cleanup --ports 18789

# Remove stale lock/state files only (no process kill)
uv run openclaw cleanup --stale
```

Run `uv run openclaw cleanup --help` to see all available options.

---

## Telegram Setup

1. Message [@BotFather](https://t.me/botfather) on Telegram → `/newbot` → copy the token
2. Add `TELEGRAM_BOT_TOKEN=<your-token>` to `.env`
3. Start the gateway: `uv run openclaw gateway run`
4. Open your bot on Telegram and start chatting

**Access control:** By default, new users must be approved. Use `/pair` in the bot to request access, then approve from the CLI:

```bash
uv run openclaw pairing list telegram
uv run openclaw pairing approve telegram <code>
```

**Session commands (in Telegram chat):**

| Command | Action |
|---|---|
| `/reset` | Start a fresh conversation session |
| `/cron` | View and manage scheduled tasks |
| `/help` | Show available commands |

---

## Architecture Overview

```
openclaw-python/
├── openclaw/
│   ├── agents/              # Agent runtime, session management, context
│   │   ├── providers/       # LLM providers (Anthropic, Gemini, OpenAI)
│   │   ├── tools/           # 24+ built-in tools
│   │   └── skills/          # 56+ modular skills (loaded at runtime)
│   ├── channels/            # Messaging integrations
│   │   └── telegram/        # Telegram channel (fully operational)
│   ├── gateway/             # WebSocket gateway server
│   │   ├── api/             # RPC method handlers
│   │   └── protocol/        # WebSocket frame protocol
│   ├── cron/                # Cron scheduler (job store, timer, execution)
│   ├── infra/               # System events, in-memory queues
│   ├── config/              # Configuration loading and schema
│   ├── routing/             # Session key resolution and routing
│   └── cli/                 # Command-line interface
└── tests/                   # Unit and integration tests
```

**Data directory** (`~/.openclaw/`):

```
~/.openclaw/
├── openclaw.json            # Gateway configuration
├── workspace/               # Agent workspace (injected into system prompt)
│   ├── SOUL.md              # Personality and values
│   ├── AGENTS.md            # Operating instructions
│   ├── TOOLS.md             # Tool configurations
│   └── USER.md              # User profile
├── agents/main/sessions/    # Conversation sessions (UUID-based)
├── cron/                    # Cron job store and logs
└── logs/                    # Gateway and channel logs
```

---

## Cron (Scheduled Tasks)

The cron system lets you schedule one-shot or recurring tasks that fire agent turns automatically.

```bash
# List scheduled jobs
uv run openclaw cron list

# Add a one-shot job (via CLI)
uv run openclaw cron add --name "Daily check" --schedule "0 9 * * *"

# Force-run a job immediately
uv run openclaw cron run <job-id>
```

You can also manage cron jobs from the Web UI or Telegram via `/cron`.

Cron events are delivered to the active session and optionally forwarded to Telegram.

---

## Skills and Tools

Skills are markdown + optional Python files loaded from `~/.openclaw/workspace/skills/` or the built-in skills directory. They extend the agent's knowledge and capabilities without modifying core code.

Tools are Python callables available to the agent at runtime. Built-in tools include file operations, web search, code execution, system queries, memory management, and more.

---

## Access Control

Edit `~/.openclaw/openclaw.json` to configure the DM policy for Telegram:

```json
{
  "channels": {
    "telegram": {
      "dm_policy": "pairing"
    }
  }
}
```

Policies:

| Policy | Behavior |
|---|---|
| `pairing` (default) | New users must request and be approved |
| `allowlist` | Only pre-approved users can interact |
| `open` | Any user can interact (use with caution) |
| `disabled` | No DM access |

---

## Development

```bash
# Run test suite
uv run pytest

# Run specific tests
uv run pytest tests/integration/

# Lint and format
uv run ruff check .
uv run ruff format .

# Build Web UI (if modifying frontend)
cd openclaw/web/ui-src
npm install && npm run build
```

---

## Status

| Feature | Status |
|---|---|
| Telegram channel | ✅ Operational |
| WebSocket gateway | ✅ Operational |
| Web Control UI | ✅ Operational |
| Cron scheduler | ✅ Operational |
| Session management | ✅ Aligned with TS |
| Context compaction | ✅ Operational |
| Discord channel | 🔨 In progress |
| Voice integration | 🔨 Planned |

---

## Remote Repository

[https://github.com/openxjarvis/openclaw-python](https://github.com/openxjarvis/openclaw-python)

## License

MIT — see [LICENSE](LICENSE) for details.
