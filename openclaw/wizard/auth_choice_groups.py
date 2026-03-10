"""Auth choice groups and options - aligned with TypeScript auth-choice-options.ts

Defines provider groups, options, labels, and hints.
Mirrors openclaw/src/commands/auth-choice-options.ts
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .auth_choice_types import AuthChoice, AuthChoiceGroupId


@dataclass
class AuthChoiceOption:
    """Single authentication choice option"""
    value: "AuthChoice"
    label: str
    hint: str | None = None


@dataclass
class AuthChoiceGroup:
    """Provider group with multiple auth choices"""
    value: "AuthChoiceGroupId"
    label: str
    hint: str | None
    choices: list["AuthChoice"]


# Provider group definitions (aligned with TS AUTH_CHOICE_GROUP_DEFS)
AUTH_CHOICE_GROUP_DEFS: list[AuthChoiceGroup] = [
    AuthChoiceGroup(
        value="openai",
        label="OpenAI",
        hint="Codex OAuth + API key",
        choices=["openai-codex", "openai-api-key"]
    ),
    AuthChoiceGroup(
        value="anthropic",
        label="Anthropic",
        hint="setup-token + API key",
        choices=["token", "apiKey"]
    ),
    AuthChoiceGroup(
        value="chutes",
        label="Chutes",
        hint="OAuth",
        choices=["chutes"]
    ),
    AuthChoiceGroup(
        value="vllm",
        label="vLLM",
        hint="Local/self-hosted OpenAI-compatible",
        choices=["vllm"]
    ),
    AuthChoiceGroup(
        value="minimax",
        label="MiniMax",
        hint="M2.5 (recommended)",
        choices=["minimax-portal", "minimax-api", "minimax-api-key-cn", "minimax-api-lightning"]
    ),
    AuthChoiceGroup(
        value="moonshot",
        label="Moonshot AI (Kimi K2.5)",
        hint="Kimi K2.5 + Kimi Coding",
        choices=["moonshot-api-key", "moonshot-api-key-cn", "kimi-code-api-key"]
    ),
    AuthChoiceGroup(
        value="google",
        label="Google",
        hint="Gemini API key + OAuth",
        choices=["gemini-api-key", "google-gemini-cli"]
    ),
    AuthChoiceGroup(
        value="xai",
        label="xAI (Grok)",
        hint="API key",
        choices=["xai-api-key"]
    ),
    AuthChoiceGroup(
        value="mistral",
        label="Mistral AI",
        hint="API key",
        choices=["mistral-api-key"]
    ),
    AuthChoiceGroup(
        value="volcengine",
        label="Volcano Engine",
        hint="API key",
        choices=["volcengine-api-key"]
    ),
    AuthChoiceGroup(
        value="byteplus",
        label="BytePlus",
        hint="API key",
        choices=["byteplus-api-key"]
    ),
    AuthChoiceGroup(
        value="openrouter",
        label="OpenRouter",
        hint="API key",
        choices=["openrouter-api-key"]
    ),
    AuthChoiceGroup(
        value="kilocode",
        label="Kilo Gateway",
        hint="API key (OpenRouter-compatible)",
        choices=["kilocode-api-key"]
    ),
    AuthChoiceGroup(
        value="qwen",
        label="Qwen",
        hint="OAuth",
        choices=["qwen-portal"]
    ),
    AuthChoiceGroup(
        value="zai",
        label="Z.AI",
        hint="GLM Coding Plan / Global / CN",
        choices=["zai-coding-global", "zai-coding-cn", "zai-global", "zai-cn"]
    ),
    AuthChoiceGroup(
        value="qianfan",
        label="Qianfan",
        hint="API key",
        choices=["qianfan-api-key"]
    ),
    AuthChoiceGroup(
        value="copilot",
        label="Copilot",
        hint="GitHub + local proxy",
        choices=["github-copilot", "copilot-proxy"]
    ),
    AuthChoiceGroup(
        value="ai-gateway",
        label="Vercel AI Gateway",
        hint="API key",
        choices=["ai-gateway-api-key"]
    ),
    AuthChoiceGroup(
        value="opencode-zen",
        label="OpenCode Zen",
        hint="API key",
        choices=["opencode-zen"]
    ),
    AuthChoiceGroup(
        value="xiaomi",
        label="Xiaomi",
        hint="API key",
        choices=["xiaomi-api-key"]
    ),
    AuthChoiceGroup(
        value="synthetic",
        label="Synthetic",
        hint="Anthropic-compatible (multi-model)",
        choices=["synthetic-api-key"]
    ),
    AuthChoiceGroup(
        value="together",
        label="Together AI",
        hint="API key",
        choices=["together-api-key"]
    ),
    AuthChoiceGroup(
        value="huggingface",
        label="Hugging Face",
        hint="Inference API (HF token)",
        choices=["huggingface-api-key"]
    ),
    AuthChoiceGroup(
        value="venice",
        label="Venice AI",
        hint="Privacy-focused (uncensored models)",
        choices=["venice-api-key"]
    ),
    AuthChoiceGroup(
        value="litellm",
        label="LiteLLM",
        hint="Unified LLM gateway (100+ providers)",
        choices=["litellm-api-key"]
    ),
    AuthChoiceGroup(
        value="cloudflare-ai-gateway",
        label="Cloudflare AI Gateway",
        hint="Account ID + Gateway ID + API key",
        choices=["cloudflare-ai-gateway-api-key"]
    ),
    AuthChoiceGroup(
        value="custom",
        label="Custom Provider",
        hint="Any OpenAI or Anthropic compatible endpoint",
        choices=["custom-api-key"]
    ),
]


# Special labels for specific auth choices (aligned with TS PROVIDER_AUTH_CHOICE_OPTION_LABELS)
PROVIDER_AUTH_CHOICE_OPTION_LABELS: dict["AuthChoice", str] = {
    "moonshot-api-key": "Kimi API key (.ai)",
    "moonshot-api-key-cn": "Kimi API key (.cn)",
    "kimi-code-api-key": "Kimi Code API key (subscription)",
    "cloudflare-ai-gateway-api-key": "Cloudflare AI Gateway",
}


# Special hints for specific auth choices (aligned with TS PROVIDER_AUTH_CHOICE_OPTION_HINTS)
PROVIDER_AUTH_CHOICE_OPTION_HINTS: dict["AuthChoice", str] = {
    "litellm-api-key": "Unified gateway for 100+ LLM providers",
    "cloudflare-ai-gateway-api-key": "Account ID + Gateway ID + API key",
    "venice-api-key": "Privacy-focused inference (uncensored models)",
    "together-api-key": "Access to Llama, DeepSeek, Qwen, and more open models",
    "huggingface-api-key": "Inference Providers — OpenAI-compatible chat",
}


def build_auth_choice_groups(include_skip: bool = True) -> tuple[list[AuthChoiceGroup], AuthChoiceOption | None]:
    """Build auth choice groups and optional skip option
    
    Args:
        include_skip: Whether to include skip option
        
    Returns:
        Tuple of (groups, skip_option)
    """
    groups = AUTH_CHOICE_GROUP_DEFS.copy()
    
    skip_option = None
    if include_skip:
        skip_option = AuthChoiceOption(
            value="skip",
            label="Skip for now",
            hint=None
        )
    
    return groups, skip_option


def build_auth_choice_options(group: AuthChoiceGroup) -> list[AuthChoiceOption]:
    """Build auth choice options for a specific group
    
    Args:
        group: Provider group
        
    Returns:
        List of auth choice options
    """
    options: list[AuthChoiceOption] = []
    
    for choice in group.choices:
        label = PROVIDER_AUTH_CHOICE_OPTION_LABELS.get(choice, choice)
        hint = PROVIDER_AUTH_CHOICE_OPTION_HINTS.get(choice)
        
        options.append(AuthChoiceOption(
            value=choice,
            label=label,
            hint=hint
        ))
    
    return options
