---
summary: "Model selection, provider configuration, and failover in OpenClaw Python"
read_when:
  - Configuring LLM providers and models
  - Debugging model selection or failover
title: "Models"
---

# Models

OpenClaw Python supports multiple LLM providers. Configure models under
`agents.defaults.model` or per-agent under `agents.list[].model`.

## Supported providers

| Provider | Config key | Notes |
|----------|-----------|-------|
| Anthropic | `anthropic` | Claude models |
| OpenAI | `openai` | GPT-4o, GPT-4.1, etc. |
| Google Gemini | `google` / `gemini` | Gemini 2.x models |
| Ollama | `ollama` | Local models |
| AWS Bedrock | `bedrock` | Requires AWS credentials |
| OpenRouter | `openrouter` | Multi-provider proxy |

## Model ref format

Model refs split on the **first** `/`:

```
provider/model-id
```

Examples:
- `anthropic/claude-opus-4-5`
- `openai/gpt-4o`
- `google/gemini-2.0-flash`
- `ollama/llama3.3`
- `openrouter/anthropic/claude-opus-4`

## Basic configuration

```json5
{
  agents: {
    defaults: {
      model: "anthropic/claude-opus-4-5",
    },
  },
  models: {
    providers: {
      anthropic: { apiKey: "sk-ant-..." },
      openai: { apiKey: "sk-proj-..." },
    },
  },
}
```

## Model failover

Configure fallback models if the primary model fails:

```json5
{
  agents: {
    defaults: {
      model: "anthropic/claude-opus-4-5",
      models: {
        failover: ["openai/gpt-4o", "google/gemini-2.0-flash"],
      },
    },
  },
}
```

## Ollama (local models)

```json5
{
  agents: {
    defaults: {
      model: "ollama/llama3.3",
    },
  },
  models: {
    providers: {
      ollama: { baseUrl: "http://localhost:11434" },
    },
  },
}
```

## Per-agent model override

```json5
{
  agents: {
    list: [
      {
        id: "main",
        model: "anthropic/claude-sonnet-4-5",
      },
      {
        id: "coder",
        model: "openai/gpt-4o",
      },
    ],
  },
}
```

## CLI model commands

```bash
openclaw models list          # List available models
openclaw models auth login    # Authenticate with a provider
```
