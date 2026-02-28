"""
LLM Provider implementations
"""

from .anthropic_provider import AnthropicProvider
from .base import LLMMessage, LLMProvider, LLMResponse
from .bedrock_provider import BedrockProvider
from .gemini_provider import GeminiProvider
from .ollama_provider import OllamaProvider
from .openai_provider import OpenAIProvider


def create_provider(provider_id: str, config: dict | None = None) -> "LLMProvider":
    """
    Factory function to create an LLM provider by ID.

    Matches TypeScript createProvider() — resolves provider type and
    returns an initialized provider instance.
    """
    cfg = config or {}
    provider_map: dict[str, type] = {
        "anthropic": AnthropicProvider,
        "openai": OpenAIProvider,
        "gemini": GeminiProvider,
        "google": GeminiProvider,
        "bedrock": BedrockProvider,
        "ollama": OllamaProvider,
    }
    cls = provider_map.get(provider_id.lower())
    if cls is None:
        raise ValueError(f"Unknown provider: {provider_id!r}")
    return cls(**cfg)


__all__ = [
    "LLMProvider",
    "LLMResponse",
    "LLMMessage",
    "AnthropicProvider",
    "OpenAIProvider",
    "GeminiProvider",
    "BedrockProvider",
    "OllamaProvider",
    "create_provider",
]
