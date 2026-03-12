---
summary: "Audit what can spend money, which keys are used, and how to view usage"
read_when:
  - You want to understand which features may call paid APIs
  - You need to audit keys, costs, and usage visibility
title: "API Usage and Costs"
---

# API usage & costs

This doc lists **features that can invoke API keys** and where their costs show up.

## Where costs show up

**Per-session cost snapshot**

- `/status` shows the current session model, context usage, and last response tokens.
- If the model uses **API-key auth**, `/status` also shows **estimated cost** for the last reply.

**Per-message cost footer**

- `/usage full` appends a usage footer to every reply, including **estimated cost** (API-key only).
- `/usage tokens` shows tokens only; OAuth flows hide dollar cost.

**CLI usage windows (provider quotas)**

- `openclaw status --usage` shows provider **usage windows** (quota snapshots, not per-message costs).

## How keys are discovered

OpenClaw can pick up credentials from:

- **Auth profiles** (per-agent, stored in `auth-profiles.json`).
- **Environment variables** (e.g. `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`).
- **Config** (`models.providers.*.apiKey`, `tools.web.search.*`).

## Features that may call paid APIs

| Feature | Env var / config key | Notes |
|---------|---------------------|-------|
| LLM inference | `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc. | Every agent turn |
| Web search | `BRAVE_API_KEY` | Tool calls to `web_search` |
| Web fetch | `FIRECRAWL_API_KEY` | Tool calls to `web_fetch` |
| Memory indexing | `OPENAI_API_KEY` | Embedding calls |
| Image generation | `OPENAI_API_KEY` | Tool calls to `image_gen` |

## Usage visibility per provider

- **Anthropic**: `openclaw models auth --provider anthropic` shows usage window and quota.
- **OpenAI**: `openclaw models auth --provider openai` shows usage window.
- **Gemini**: `openclaw models auth --provider google` shows quota information.

## Python implementation

- `openclaw/agents/usage.py` — usage tracking and reporting
- `openclaw/agents/models_config.py` — `build_minimax_provider()`, `build_qianfan_provider()`, etc.
