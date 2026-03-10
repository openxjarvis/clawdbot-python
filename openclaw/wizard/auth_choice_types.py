"""Auth choice types - aligned with TypeScript onboard-types.ts

Defines all authentication choice types and provider group IDs.
Mirrors openclaw/src/commands/onboard-types.ts
"""
from typing import Literal
from typing_extensions import TypeAlias

# All possible authentication choices (aligned with TS AuthChoice)
AuthChoice: TypeAlias = Literal[
    # Anthropic
    "oauth",          # Legacy alias for setup-token
    "setup-token",
    "token",
    "apiKey",
    # OpenAI
    "openai-codex",
    "openai-api-key",
    # Cloud/Aggregator Services
    "openrouter-api-key",
    "kilocode-api-key",
    "litellm-api-key",
    "ai-gateway-api-key",
    "cloudflare-ai-gateway-api-key",
    # MiniMax
    "minimax-cloud",
    "minimax",
    "minimax-api",
    "minimax-api-key-cn",
    "minimax-api-lightning",
    "minimax-portal",
    # Moonshot AI (Kimi)
    "moonshot-api-key",
    "moonshot-api-key-cn",
    "kimi-code-api-key",
    # Z.AI (GLM)
    "zai-api-key",
    "zai-coding-global",
    "zai-coding-cn",
    "zai-global",
    "zai-cn",
    # Google
    "gemini-api-key",
    "google-gemini-cli",
    # Domestic China Services
    "xiaomi-api-key",
    "qwen-portal",
    "qianfan-api-key",
    "volcengine-api-key",
    "byteplus-api-key",
    # Other Major Providers
    "xai-api-key",
    "mistral-api-key",
    "synthetic-api-key",
    "venice-api-key",
    "together-api-key",
    "huggingface-api-key",
    "opencode-zen",
    # GitHub Copilot
    "github-copilot",
    "copilot-proxy",
    # OAuth/Special
    "chutes",
    "vllm",
    # Legacy aliases
    "claude-cli",
    "codex-cli",
    # Custom
    "custom-api-key",
    # Skip
    "skip",
]

# Provider group IDs (aligned with TS AuthChoiceGroupId)
AuthChoiceGroupId: TypeAlias = Literal[
    "openai",
    "anthropic",
    "chutes",
    "vllm",
    "google",
    "copilot",
    "openrouter",
    "kilocode",
    "litellm",
    "ai-gateway",
    "cloudflare-ai-gateway",
    "moonshot",
    "zai",
    "xiaomi",
    "opencode-zen",
    "minimax",
    "synthetic",
    "venice",
    "mistral",
    "qwen",
    "together",
    "huggingface",
    "qianfan",
    "xai",
    "volcengine",
    "byteplus",
    "custom",
]
