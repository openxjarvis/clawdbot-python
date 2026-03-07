# OpenClaw Python

> Python implementation of [OpenClaw](https://github.com/badlogic/pi-mono) — a self-hosted personal AI assistant gateway.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Tested: Telegram + Gemini](https://img.shields.io/badge/Tested-Telegram%20%2B%20Gemini-green.svg)](#status)
[![Tested: Feishu + Gemini](https://img.shields.io/badge/Tested-Feishu%20%2B%20Gemini-green.svg)](#status)

---

> ⚠️ **Beta Notice** — This project is in active development and continuously aligned with the TypeScript OpenClaw reference. Bugs and rough edges exist; updates are frequent. Feedback and bug reports are welcome!
>
> ⚠️ **测试版声明** — 本项目持续对齐 TypeScript 版 OpenClaw，正在快速迭代中。欢迎反馈问题和需求！

---

## Preview

<img src="assets/telegram-preview.jpg" alt="Jarvis on Telegram" width="260" />&nbsp;<img src="assets/IMG_1511.jpg" alt="Jarvis on Feishu" width="260" />&nbsp;<img src="assets/IMG_1544.jpg" alt="Jarvis on Feishu" width="260" />

*Jarvis responding on Telegram and Feishu — powered by OpenClaw Python*

---

## What it does

A self-hosted AI gateway that connects your messaging channels to LLMs:

- **Feishu (Lark)** — Full feature support: WebSocket real-time connection, streaming card output, media (image/file/voice), reactions, pairing, multi-account, Bitable, Wiki, Doc tools
- **Telegram** — Fully operational with robust polling (conflict-free restart logic, health monitor, update deduplication)
- **Other channels** — Discord, Slack, WhatsApp, Signal, IRC (code complete, runtime verification in progress)
- **LLM providers** — Gemini, Claude, GPT, DeepSeek, Grok, Ollama (local)
- **Web UI** — Chat, session management, config at `http://localhost:18789`
- **Cron scheduler** — Autonomous scheduled tasks
- **Sub-agents** — Spawn, registry, thread binding, Docker sandbox

---

## Quick Start

**Prerequisites:** Python 3.11+ · [uv](https://docs.astral.sh/uv/) · LLM API key

```bash
# Clone both repos as siblings (pi-mono-python is required)
mkdir my-workspace && cd my-workspace
git clone https://github.com/openxjarvis/pi-mono-python.git
git clone https://github.com/openxjarvis/openclaw-python.git

cd openclaw-python
uv sync

# One-time setup wizard
uv run openclaw onboard

# Start
uv run openclaw start
```

Open **http://localhost:18789** for the Web UI, or message your Telegram/Feishu bot directly.

**Update:** `git pull && uv sync` in both repos, then restart.

---

## Dependencies: pi-mono-python

`openclaw-python` depends on **[pi-mono-python](https://github.com/openxjarvis/pi-mono-python)** — a companion repo that provides the core agent and LLM infrastructure as local packages:

| Package | Provides |
|---|---|
| `pi-ai` | Unified LLM streaming layer (Gemini, Anthropic, OpenAI, …) |
| `pi-agent` | Agent loop, tool execution, session state |
| `pi-coding-agent` | Coding agent with file/bash/search tools |
| `pi-tui` | Terminal UI rendering engine |

Both repos must be cloned as siblings inside the same parent directory (any name works):

```
my-workspace/
├── openclaw-python/       ← this repo
└── pi-mono-python/        ← required sibling
```

---

## Feishu (Lark) — Full Feature Support

飞书是目前功能最完整的渠道，支持所有功能：

| Feature | Status |
|---------|--------|
| WebSocket long-connection | ✅ |
| Streaming card output (实时流式卡片) | ✅ |
| Image / File / Voice message | ✅ |
| Message reactions (reaction ACK) | ✅ |
| Pairing / allowlist / DM policy | ✅ |
| Multi-account | ✅ |
| Bitable (多维表格) tools | ✅ |
| Wiki / Doc read & write | ✅ |
| Mention / group chat | ✅ |

---

## Telegram — Optimized

- Conflict-free polling (fixes self-inflicted 409 loop from dual-start bug)
- PTB internal retry loop handles transient conflicts automatically
- Health monitor with `get_me()` checks every 60s
- Update offset persistence across restarts
- Deduplication for all update types

---

## Configuration

Run the interactive setup wizard (once per environment):

```bash
uv run openclaw onboard
```

The wizard walks you through LLM provider selection, channel setup, gateway port, and workspace initialization. It saves keys to `.env` automatically.

Or edit `~/.openclaw/openclaw.json` directly:

```json
{
  "channels": {
    "telegram": {
      "enabled": true,
      "botToken": "YOUR_BOT_TOKEN"
    },
    "feishu": {
      "appId": "YOUR_APP_ID",
      "appSecret": "YOUR_APP_SECRET",
      "useWebSocket": true
    }
  }
}
```

---

## Access Control

Configure the DM policy for each channel in `~/.openclaw/openclaw.json`:

| Policy | Behavior |
|---|---|
| `pairing` (default) | New users must request and be approved |
| `allowlist` | Only pre-approved users can interact |
| `open` | Any user can interact (use with caution) |
| `disabled` | No DM access |

---

## Status

Continuously aligned with the TypeScript [OpenClaw](https://github.com/badlogic/pi-mono) reference.

### Channels

| Channel | Status | Notes |
|---------|--------|-------|
| **Telegram** | ✅ Production ready | Fully tested and operational |
| **Feishu (Lark)** | ✅ Production ready | Full feature support |
| **Ollama (local models)** | ✅ Production ready | Tested locally |
| Discord / Slack / WhatsApp / Signal / IRC | 🔧 Runtime verification in progress | Code complete |

### AI Providers

| Provider | Status | Models |
|----------|--------|--------|
| **Google Gemini** | ✅ Production | Gemini 2.5 Pro, Gemini 2.0 Flash, Gemini 1.5 Pro/Flash |
| **Anthropic Claude** | ✅ Implemented | Claude 3.5 Sonnet, Claude 3.5 Haiku, Claude 3 Opus |
| **OpenAI** | ✅ Implemented | GPT-4o, o1, o3-mini |
| **DeepSeek** | ✅ Implemented | DeepSeek-V3, DeepSeek-R1 |
| **Ollama** | ✅ Implemented | Llama 3.3, Mistral, Qwen, CodeLlama (local) |
| **AWS Bedrock** | ✅ Implemented | Claude 3.x, Llama 3.3, Mistral |
| xAI (Grok), Zhipu, Alibaba | 🚧 Planned | Q2–Q3 2026 |

### Core Infrastructure

| Component | Status |
|-----------|--------|
| Gateway server + Web UI | ✅ Production |
| Session management | ✅ Production |
| Tool system | ✅ Production |
| Skill system | ✅ Production |
| Cron scheduler | ✅ Production |
| Sub-agents (spawn, registry) | ✅ Production |
| Docker sandbox | ✅ Implemented |
| Context compaction | ✅ Production |

---

## Development

```bash
# Run tests
uv run pytest

# Lint
uv run ruff check .
uv run ruff format .

# Build Web UI (if modifying frontend)
cd openclaw/web/ui-src
npm install && npm run build
```

---

## Related Projects

- **OpenClaw TypeScript** — [github.com/badlogic/pi-mono](https://github.com/badlogic/pi-mono) — upstream reference implementation
- **pi-mono-python** — [github.com/openxjarvis/pi-mono-python](https://github.com/openxjarvis/pi-mono-python) — core agent infrastructure

---

## License

MIT — see [LICENSE](LICENSE) for details.
