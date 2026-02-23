"""Agent defaults — mirrors TypeScript openclaw/src/agents/defaults.ts"""

# Default provider and model used when no config is present.
# Model id uses pi-ai's built-in Anthropic catalog.
DEFAULT_PROVIDER = "anthropic"
DEFAULT_MODEL = "claude-opus-4-6"

# Conservative fallback used when model metadata is unavailable.
DEFAULT_CONTEXT_TOKENS = 200_000
