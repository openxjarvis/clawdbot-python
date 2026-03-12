---
summary: "LLM provider configuration for OpenClaw Python"
read_when:
  - Configuring Anthropic, OpenAI, Gemini, Ollama, or other providers
  - Setting up API keys and model catalog
title: "Providers"
---

# Model Providers

OpenClaw Python supports multiple LLM providers. Configure them under `models.providers`
in `~/.openclaw/openclaw.json`.

## Anthropic (Claude)

```json5
{
  models: {
    providers: {
      anthropic: {
        apiKey: "sk-ant-...",
      },
    },
  },
  agents: {
    defaults: {
      model: "anthropic/claude-opus-4-5",
    },
  },
}
```

Available models: `claude-opus-4-5`, `claude-sonnet-4-5`, `claude-haiku-4-5`, etc.

## OpenAI (GPT-4o, GPT-4.1)

```json5
{
  models: {
    providers: {
      openai: {
        apiKey: "sk-proj-...",
      },
    },
  },
  agents: {
    defaults: {
      model: "openai/gpt-4o",
    },
  },
}
```

## Google Gemini

```json5
{
  models: {
    providers: {
      google: {
        apiKey: "AIza...",
      },
    },
  },
  agents: {
    defaults: {
      model: "google/gemini-2.0-flash",
    },
  },
}
```

## Ollama (local models)

```json5
{
  models: {
    providers: {
      ollama: {
        baseUrl: "http://localhost:11434",
      },
    },
  },
  agents: {
    defaults: {
      model: "ollama/llama3.3",
    },
  },
}
```

Pull models with: `ollama pull llama3.3`

## OpenRouter

```json5
{
  models: {
    providers: {
      openrouter: {
        apiKey: "sk-or-...",
      },
    },
  },
  agents: {
    defaults: {
      model: "openrouter/anthropic/claude-opus-4",
    },
  },
}
```

## AWS Bedrock

```json5
{
  models: {
    providers: {
      bedrock: {
        region: "us-east-1",
        // Uses AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY from environment
        // or IAM role if running on EC2/ECS
      },
    },
  },
  agents: {
    defaults: {
      model: "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0",
    },
  },
}
```

## Environment variables

API keys can be provided via environment variables instead of the config file:

| Provider | Environment Variable |
|----------|---------------------|
| Anthropic | `ANTHROPIC_API_KEY` |
| OpenAI | `OPENAI_API_KEY` |
| Google | `GOOGLE_API_KEY` |

## CLI model commands

```bash
openclaw models list               # List all configured models
openclaw models auth login         # Authenticate with a provider
openclaw models auth status        # Show auth status
```
