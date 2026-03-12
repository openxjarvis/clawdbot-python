---
summary: "OpenClaw Python gateway architecture, WebSocket protocol, and client flows"
read_when:
  - Understanding how the Python gateway works
  - Modifying core gateway or protocol handling
title: "Architecture"
---

# Architecture

OpenClaw Python is a **self-hosted AI agent gateway** built in Python. It exposes a
WebSocket-based gateway that connects messaging channels (Telegram, Discord, Slack,
WhatsApp, etc.) to LLM providers (Anthropic, OpenAI, Gemini, Ollama, Bedrock).

## High-level diagram

```
Messaging Channels                Gateway (Python)           LLM Providers
─────────────────      ────────────────────────────────    ─────────────────
Telegram Bot     ───►  Channel Manager  ──► Agent Loop ──► Anthropic Claude
Discord Bot      ───►  (asyncio)        ──► Pi Runtime ──► OpenAI GPT
Slack App        ───►                   ──► Tools       ──► Gemini
WhatsApp         ───►  Plugin Registry  ──► Memory      ──► Ollama (local)
IRC              ───►                   ──► Cron        ──► Bedrock
                       WebSocket API    ──► Web UI
                       (FastAPI/uvicorn)
```

## Key components

### Gateway bootstrap (`openclaw/gateway/bootstrap.py`)

The gateway starts via `GatewayBootstrap.start()`, which:

1. Loads configuration from `~/.openclaw/openclaw.json`
2. Discovers and loads plugins (bundled + user extensions)
3. Initializes channel managers for each configured channel
4. Starts the WebSocket API server (FastAPI + uvicorn)
5. Starts the cron scheduler
6. Initializes the memory system
7. Starts background services registered by plugins

### Channel manager (`openclaw/gateway/channel_manager.py`)

Each channel plugin is wrapped in a channel manager that handles:
- Account lifecycle (connect/disconnect/reconnect)
- Inbound message routing to the agent queue
- Outbound message delivery
- Channel health monitoring

### Agent runtime (`openclaw/gateway/pi_runtime.py`)

The `PiAgentRuntime` handles:
- Session management (create/resume/reset)
- LLM provider selection and failover
- Tool execution with sandbox support
- Context compaction and pruning
- Memory search injection

### Plugin system (`openclaw/plugins/`)

Plugins extend the gateway with:
- Additional channels (`api.register_channel()`)
- Agent tools (`api.register_tool()`)
- Lifecycle hooks (`api.on()`)
- Gateway RPC methods (`api.register_gateway_method()`)
- Background services (`api.register_service()`)
- CLI commands (`api.register_cli()`)
- Auto-reply commands (`api.register_command()`)

### WebSocket API (`openclaw/gateway/api/`)

The gateway exposes a WebSocket endpoint for:
- Control UI connections (web dashboard)
- Remote gateway access
- CLI tool calls (`openclaw gateway call <method>`)

The protocol uses JSON-RPC style messages over WebSocket.

## Configuration

All configuration lives in `~/.openclaw/openclaw.json` (JSON5 format).
Key sections:

```json5
{
  agents: {
    defaults: {
      workspace: "~/.openclaw/workspace",
      model: "anthropic/claude-opus-4-5",
    }
  },
  channels: {
    telegram: { token: "...", allowFrom: ["+1..."] },
    discord: { token: "..." },
  },
  plugins: {
    entries: {
      "memory-lancedb": { enabled: true, config: { embedding: { apiKey: "sk-..." } } },
    },
  },
}
```

## Process model

OpenClaw Python runs as a single asyncio event loop:
- All channel bots run as asyncio tasks
- The agent loop is task-based with a per-session queue
- Background services run as asyncio tasks
- The FastAPI web server runs in the same event loop via uvicorn

## Deployment

See [install/](../install/) for Docker, systemd, and cloud deployment guides.
