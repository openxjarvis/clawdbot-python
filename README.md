# OpenXJarvis (openclaw-python)

> **Jarvis lives here.** A pure Python clone of OpenClaw — the most powerful personal AI gateway you can run.
 A Python implementation of the OpenClaw AI assistant  — aligned with the TypeScript reference implementation


[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MIT License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Tested: Telegram + Gemini](https://img.shields.io/badge/Tested-Telegram%20%2B%20Gemini-green.svg)](#tested-configurations)

## What is This?

**OpenXJarvis** is a complete Python implementation of [OpenClaw](https://github.com/openclaw/openclaw) — continuously aligned with the TypeScript reference. Think of it as your personal AI operating system: connect messaging channels (Telegram, WhatsApp, Discord, Slack, IRC, Signal, Google Chat, iMessage), plug in cutting-edge models (GPT-5.2, Claude Opus 4.6, Gemini 3.1 Pro, Grok 4, DeepSeek V3.2, GLM-5, Qwen 3.5), manage persistent memory, schedule autonomous tasks, and control everything through a beautiful Web UI or CLI.

**Why "Jarvis"?** Because this isn't just another chatbot framework. This is your digital companion — always learning, always improving, evolving in lockstep with OpenClaw's rapid development. Every feature, every alignment improvement, every new capability lands here.

**This project stays synchronized with OpenClaw.** We track upstream changes and continuously merge improvements. You're not choosing between Python and TypeScript — you're choosing the same powerful platform in your preferred language.

---

## Tested Configurations

| Component | Status | Notes |
|-----------|--------|-------|
| **Telegram + Gemini ** | ✅ **Production Ready** | Fully tested and operational |
| WhatsApp | 🧪 Verification in progress | QR link integration complete |
| Discord | 🧪 Verification in progress | Bot API integration complete |
| Slack | 🧪 Verification in progress | Socket Mode integration complete |
| IRC | 🧪 Verification in progress | Classic IRC networks support |
| GPT-5.2 Pro | 🧪 Verification in progress | OpenAI API integration complete |
| Claude Opus 4.6 | 🧪 Verification in progress | Anthropic API integration complete |
| Gemini 3.1 Pro | 🧪 Verification in progress | Google API integration complete |
| Grok 4 | 🧪 Verification in progress | xAI API integration complete |
| DeepSeek V3.2 | 🧪 Verification in progress | DeepSeek API integration complete |
| Web UI | ✅ **Production Ready** | Full feature parity with TypeScript |
| Cron Scheduler | ✅ **Production Ready** | Autonomous task execution working |

**Latest test:** Telegram bot + Gemini 2.5 Pro Preview running complex multi-tool workflows (web search, file operations, reasoning) — rock solid. 🚀

**Model Updates (Feb 2026):** Support for latest frontier models including GPT-5.2, Claude Opus 4.6, Gemini 3.1 Pro (Feb 19), GLM-5 (Feb 2026 🆕), Grok 4, DeepSeek V3.2, and Qwen 3.5.

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

Run the interactive setup wizard (once per environment):

```bash
uv run openclaw onboard
```

The wizard walks you through:
- LLM provider and model selection (Anthropic, OpenAI, Gemini, Ollama)
- Optional fallback models for resilience
- Telegram bot setup
- Gateway port and authentication
- Workspace and personality initialization

**It prompts for API keys interactively and saves them to `.env` automatically** — no need to create `.env` by hand first.

If you already have keys in `.env`, the wizard detects and reuses them:

```bash
# Optional: pre-populate before onboarding
cp .env.example .env
# edit .env with your keys, then run the wizard
```

Onboarding creates `~/.openclaw/` with your config and workspace. **Run this once per new environment.**

### 3. Start

```bash
uv run openclaw start
```

That's it. The gateway and all configured channels start in the foreground. Open `http://localhost:18789` to access the Web UI.

---

## Starting the Gateway

The gateway is the core server. It manages the agent runtime, channels, sessions, cron, and serves the Web Control UI.

> **Quick summary:** Use `uv run openclaw start` for the simplest one-command startup.
> Use `uv run openclaw gateway install` if you want it to run automatically as a system service.

### Option A — One-command start (simplest)

```bash
uv run openclaw start
```

Starts everything (gateway + Telegram channel) in the foreground. Logs print to the terminal. Press `Ctrl+C` to stop.
This is the easiest way to get running. Use it for development or quick local use.

### Option B — Foreground gateway only

```bash
uv run openclaw gateway run
```

Same as above but starts only the gateway server (no channels). Useful when you want to control channels separately.

### Option C — Background daemon (recommended for always-on use)

If you want the gateway to start automatically and keep running in the background (even after a reboot), install it as a system service first:

```bash
# 1. Install as a system service (runs once — launchd on macOS, systemd on Linux)
uv run openclaw gateway install

# 2. Then manage it with:
uv run openclaw gateway start       # start the daemon
uv run openclaw gateway stop        # stop it
uv run openclaw gateway restart     # restart
uv run openclaw gateway status      # check if it's running
uv run openclaw gateway logs        # tail the log file
```

> **Important:** `uv run openclaw gateway install` and `uv run openclaw start` are **not interchangeable**:
>
> | Command | What it does |
> |---|---|
> | `uv run openclaw start` | Runs directly in the terminal (foreground). Stops when you close the terminal. |
> | `uv run openclaw gateway install` | Registers a background system service. Survives terminal close and reboots. Requires running `gateway start` after install. |
>
> A common mistake is running `gateway install` and then also `start` at the same time — this would launch **two instances** that both try to bind to the same port. Pick one approach and stick with it.

### Web Control UI

Once the gateway is running, open your browser at:

```
http://localhost:18789
```

The UI lets you chat with the agent, inspect sessions, manage cron jobs, and configure settings.

---

## CLI Commands

### Core Commands

| Command | Description |
|---|---|
| `uv run openclaw start` | Start gateway + channels in the foreground |
| `uv run openclaw onboard` | Interactive setup wizard (run once) |
| `uv run openclaw doctor` | Run system diagnostics |
| `uv run openclaw version` | Show OpenClaw version |
| `uv run openclaw tui` | Launch Terminal UI |

### Gateway Management

| Command | Description |
|---|---|
| `uv run openclaw gateway run` | Start gateway only in the foreground |
| `uv run openclaw gateway install` | Install as a background system service (one-time setup) |
| `uv run openclaw gateway start` | Start the installed background service |
| `uv run openclaw gateway stop` | Stop the background service |
| `uv run openclaw gateway restart` | Restart the background service |
| `uv run openclaw gateway status` | Check background service status |
| `uv run openclaw gateway logs` | Tail gateway log file |
| `uv run openclaw gateway uninstall` | Remove the background service |

### Configuration

| Command | Description |
|---|---|
| `uv run openclaw config show` | Show current configuration |
| `uv run openclaw config get <key>` | Get a config value |
| `uv run openclaw config set <key> <value>` | Set a config value |
| `uv run openclaw config unset <key>` | Remove a config value |
| `uv run openclaw directory` | Show OpenClaw directories |

### Models

| Command | Description |
|---|---|
| `uv run openclaw models status` | Show configured model and fallbacks |
| `uv run openclaw models set <model>` | Set the default model |
| `uv run openclaw models fallbacks list` | List fallback models |
| `uv run openclaw models fallbacks add <model>` | Add a fallback model |
| `uv run openclaw models fallbacks remove <model>` | Remove a fallback model |

### Channels & Pairing

| Command | Description |
|---|---|
| `uv run openclaw channels list` | List configured channels |
| `uv run openclaw channels status` | Show channel status |
| `uv run openclaw pairing list <channel>` | List pending pairing requests |
| `uv run openclaw pairing approve <channel> <code>` | Approve a pairing request |
| `uv run openclaw pairing deny <channel> <code>` | Deny a pairing request |
| `uv run openclaw pairing clear <channel>` | Clear all pending pairing requests |
| `uv run openclaw pairing allowlist <channel>` | Show allowFrom list for a channel |

### Cron (Scheduled Tasks)

| Command | Description |
|---|---|
| `uv run openclaw cron list` | List scheduled jobs |
| `uv run openclaw cron add` | Add a new cron job (interactive) |
| `uv run openclaw cron run <job-id>` | Force-run a job immediately |
| `uv run openclaw cron remove <job-id>` | Remove a cron job |
| `uv run openclaw cron enable <job-id>` | Enable a cron job |
| `uv run openclaw cron disable <job-id>` | Disable a cron job |

### Agent & Sessions

| Command | Description |
|---|---|
| `uv run openclaw agent run` | Run an agent turn via the Gateway |
| `uv run openclaw agent agents` | Manage isolated agents |
| `uv run openclaw message send <channel> <target>` | Send a message to a channel |
| `uv run openclaw memory search <query>` | Search memory index |
| `uv run openclaw memory rebuild` | Rebuild memory index |

### Skills & Tools

| Command | Description |
|---|---|
| `uv run openclaw skills list` | List available skills |
| `uv run openclaw skills show <name>` | Show skill details |
| `uv run openclaw skills refresh` | Refresh skills cache |
| `uv run openclaw tools list` | List available tools |
| `uv run openclaw tools show <name>` | Show tool details |

### Cleanup & Maintenance

| Command | Description |
|---|---|
| `uv run openclaw cleanup` | Clean up processes, ports, and stale state |
| `uv run openclaw cleanup --kill-all` | Kill all openclaw processes |
| `uv run openclaw cleanup --ports 18789` | Free a specific port |
| `uv run openclaw cleanup --stale` | Remove stale lock/state files only |
| `uv run openclaw logs tail` | Tail gateway log file |
| `uv run openclaw logs clear` | Clear log files |

### Advanced

| Command | Description |
|---|---|
| `uv run openclaw approvals list` | List pending approvals |
| `uv run openclaw acp` | Launch Approvals Control Panel |
| `uv run openclaw hooks list` | List lifecycle hooks |
| `uv run openclaw plugins list` | List loaded plugins |
| `uv run openclaw security permissions` | Show security permissions |
| `uv run openclaw system heartbeat` | Trigger system heartbeat |
| `uv run openclaw browser launch` | Launch OpenClaw dedicated browser |

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

## Development Status

### Core Infrastructure
| Component | Status | TypeScript Alignment |
|-----------|--------|---------------------|
| Gateway server | ✅ Production | 100% |
| Session management | ✅ Production | 100% |
| Context compaction | ✅ Production | 100% |
| Tool system (24+ tools) | ✅ Production | 100% |
| Skill system (56+ skills) | ✅ Production | 100% |
| Cron scheduler | ✅ Production | 100% |
| Memory indexing | ✅ Production | 100% |
| Web Control UI | ✅ Production | 100% |

### Channels
| Channel | Status | Verification |
|---------|--------|-------------|
| Telegram | ✅ Production | ✅ Battle-tested |
| Discord | ✅ Implemented | 🧪 In verification |
| Slack | ✅ Implemented | 🧪 In verification |
| WhatsApp | ✅ Implemented | 🧪 In verification |
| IRC | ✅ Implemented | 🧪 In verification |

### AI Models
| Provider | Status | Verification |
|----------|--------|-------------|
| Google Gemini | ✅ Production | ✅ Battle-tested |
| Anthropic Claude | ✅ Implemented | 🧪 In verification |
| OpenAI GPT | ✅ Implemented | 🧪 In verification |
| Local LLMs (Ollama) | ✅ Implemented | 🧪 In verification |

### Roadmap
- 🎯 **Next:** Complete verification of all channels and models
- 🎯 **Q2 2026:** Voice integration
- 🎯 **Continuous:** Maintain 100% alignment with OpenClaw TypeScript

---

## Mission

**We're building the future of personal AI — in Python.**

OpenClaw showed the world what's possible: a personal AI that doesn't just chat, but *operates*. It schedules tasks, manages memory, coordinates across channels, and grows with you. Now we're bringing that power to the Python ecosystem.

This isn't a fork that will drift. This isn't a "spiritual successor." This is a **living clone** — continuously synchronized, feature-for-feature, with OpenClaw's evolution. Every breakthrough, every optimization, every new capability: we bring it here.

**Why does this matter?**
- Python's ML/AI ecosystem is unmatched
- Easier deployment for data scientists and ML engineers  
- Same powerful architecture, Python-native performance
- Your agent's capabilities grow as OpenClaw grows

**Join us.** Whether you're building your own Jarvis, experimenting with autonomous agents, or just want a badass AI assistant — this is your platform.

---

## OpenClaw TypeScript Feature Parity

This Python implementation tracks [OpenClaw TypeScript](https://github.com/openclaw/openclaw) feature-for-feature. Below is the complete list of channels and AI providers supported by OpenClaw TS — our roadmap for full parity.

### Messaging Channels (TS Support)

| Channel | Status in Python | Notes |
|---------|------------------|-------|
| **Telegram** | ✅ **Production** | Bot API — fully tested |
| **WhatsApp** | ✅ Implemented | QR link — verification in progress |
| **Discord** | ✅ Implemented | Bot API — verification in progress |
| **Slack** | ✅ Implemented | Socket Mode — verification in progress |
| **IRC** | ✅ Implemented | Classic IRC networks with pairing |
| **Google Chat** | 📋 Planned | Google Workspace Chat app |
| **Signal** | 📋 Planned | signal-cli linked device |
| **iMessage** | 📋 Planned | macOS-only, work in progress in TS |

### AI Model Providers (TS Support)

| Provider | Status in Python | Latest Models (Feb 2026) |
|----------|------------------|--------------------------|
| **OpenAI** | ✅ Implemented | **GPT-5.2 Pro** (#1 overall), GPT-5.2 Codex, GPT-4.5, o3, o4-mini |
| **Anthropic Claude** | ✅ Implemented | **Claude Opus 4.6** (strongest coding), Claude Opus 4.5, Claude Sonnet 4.5 |
| **Google Gemini** | ✅ **Production** | **Gemini 3.1 Pro** (Feb 19, 2026 🆕), Gemini 2.5 Pro, Gemini 2.0 Flash |
| **xAI Grok** | ✅ Implemented | **Grok 4 Heavy**, Grok 3, Grok 3 mini |
| **DeepSeek** | ✅ Implemented | **DeepSeek V3.2-Speciale** (best cost/perf), DeepSeek-R1 |
| **Zhipu AI** | ✅ Implemented | **GLM-5** (745B MoE, Feb 2026 🆕), GLM-4.7 |
| **Alibaba Qwen** | ✅ Implemented | **Qwen 3.5** (397B open-weight) |
| **Ollama** | ✅ Implemented | Local LLMs (Llama 4, Mistral, Qwen, etc.) |
| **Together AI** | ✅ Implemented | 100+ open-source models |
| **Hugging Face** | ✅ Implemented | Inference API models |
| **Replicate** | ✅ Implemented | Cloud-hosted models |
| **Groq** | ✅ Implemented | Ultra-fast inference |
| **MiniMax** | 📋 Planned | MiniMax-M2.1, MiniMax-VL-01 |
| **Moonshot** | 📋 Planned | Moonshot AI models |
| **Venice AI** | 📋 Planned | Privacy-focused AI |
| **Xiaomi** | 📋 Planned | Mimo-v2 models |
| **Qianfan** | 📋 Planned | Baidu AI Cloud (DeepSeek V3.2) |
| **NVIDIA NIM** | 📋 Planned | NVIDIA optimized models |
| **Cloudflare AI Gateway** | 📋 Planned | Gateway proxy support |
| **vLLM** | 📋 Planned | Self-hosted LLM serving |

**Performance Leaders (Feb 2026):**
- 🏆 **Best Overall:** GPT-5.2 Pro (93.2% GPQA Diamond)
- 💻 **Best Coding:** Claude Opus 4.6 (72.5% SWE-Bench) / DeepSeek V3.2 (77.8%)
- 💰 **Best Value:** Gemini 3.1 Pro ($2/$12 per MT), DeepSeek V3.2 (~1/30th cost of GPT-5)
- 🧠 **Best Reasoning:** Grok 4 Heavy (50% Humanity's Last Exam)
- 📚 **Longest Context:** Llama 4 Scout (10M tokens)

### API Formats Supported

- ✅ **OpenAI Completions API** (ChatGPT, compatible endpoints)
- ✅ **Anthropic Messages API** (Claude, compatible endpoints)
- ✅ **Google Generative AI** (Gemini native)
- ✅ **Ollama Native API**
- 📋 **OpenAI Responses API** (Realtime/streaming)

### Voice & Media (TS Support)

| Feature | Status in Python | Notes |
|---------|------------------|-------|
| Voice input (STT) | 📋 Planned | OpenAI Whisper, Google STT |
| Voice output (TTS) | 📋 Planned | OpenAI TTS, Google TTS, ElevenLabs |
| Image understanding | ✅ Implemented | Via vision models (GPT-4V, Gemini Vision, Claude) |
| Video understanding | 📋 Planned | Gemini video analysis |
| Audio transcription | 📋 Planned | Whisper integration |

---

## Remote Repository

[https://github.com/openxjarvis/openclaw-python](https://github.com/openxjarvis/openclaw-python)

**Upstream:** [https://github.com/openclaw/openclaw](https://github.com/openclaw/openclaw) (TypeScript reference)

## License

MIT — see [LICENSE](LICENSE) for details.
