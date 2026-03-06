# OpenClaw Python

> Python implementation of [OpenClaw](https://github.com/openclaw/openclaw) — a self-hosted personal AI assistant gateway.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## What it does

A self-hosted AI gateway that connects your messaging channels to LLMs:

- **Feishu (Lark)** — Full feature support: WebSocket real-time connection, streaming card output, media (image/file/voice), reactions, pairing, multi-account, Bitable, Wiki, Doc tools
- **Telegram** — Fully operational with robust polling (conflict-free restart logic, health monitor, update deduplication)
- **Other channels** — Discord, Slack, WhatsApp, Signal, IRC, Matrix (code complete)
- **LLM providers** — Gemini, Claude, GPT, DeepSeek, Grok, Ollama (local)
- **Web UI** — Chat, session management, config at `http://localhost:18789`
- **Cron scheduler** — Autonomous scheduled tasks
- **Sub-agents** — Spawn, registry, thread binding, Docker sandbox

---

## Quick Start

**Prerequisites:** Python 3.11+ · [uv](https://docs.astral.sh/uv/) · LLM API key

```bash
# Clone both repos as siblings (pi-mono-python is required)
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

**Update:** `git pull && uv sync` then restart.

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

Edit `~/.openclaw/openclaw.json`:

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

## Status

Continuously aligned with the TypeScript [OpenClaw](https://github.com/openclaw/openclaw) reference.

| Component | Status |
|-----------|--------|
| Telegram + Gemini | ✅ Production ready |
| Feishu + Gemini | ✅ Production ready |
| Ollama (local models) | ✅ Production ready |
| Discord / Slack / WhatsApp | 🔧 Runtime verification in progress |

---

## License

MIT
