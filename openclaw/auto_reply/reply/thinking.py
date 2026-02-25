"""Thinking level utilities

Fully aligned with TypeScript openclaw/src/auto-reply/thinking.ts

This module provides utilities for thinking levels, which control
how much internal reasoning models perform before responding.
"""
from __future__ import annotations

from typing import Literal

ThinkLevel = Literal["off", "minimal", "low", "medium", "high", "xhigh"]

# XHigh models (matches TS XHIGH_MODEL_REFS from thinking.ts lines 24-32)
XHIGH_MODEL_REFS = [
    "openai/gpt-5.2",
    "openai-codex/gpt-5.3-codex",
    "openai-codex/gpt-5.3-codex-spark",
    "openai-codex/gpt-5.2-codex",
    "openai-codex/gpt-5.1-codex",
    "github-copilot/gpt-5.2-codex",
    "github-copilot/gpt-5.2",
]

XHIGH_MODEL_SET = {ref.lower() for ref in XHIGH_MODEL_REFS}
XHIGH_MODEL_IDS = {
    ref.split("/")[1].lower()
    for ref in XHIGH_MODEL_REFS
    if "/" in ref
}


def normalize_provider_id(provider: str | None) -> str:
    """Normalize provider ID (matches TS normalizeProviderId lines 9-18)"""
    if not provider:
        return ""
    
    normalized = provider.strip().lower()
    if normalized in ("z.ai", "z-ai"):
        return "zai"
    return normalized


def is_binary_thinking_provider(provider: str | None) -> bool:
    """Check if provider uses binary thinking (on/off only)"""
    return normalize_provider_id(provider) == "zai"


def normalize_think_level(raw: str | None) -> ThinkLevel | None:
    """
    Normalize user-provided thinking level strings to canonical enum.
    
    Mirrors TS normalizeThinkLevel from thinking.ts lines 42-75
    
    Examples:
        "think-hard" -> "low"
        "think-harder" -> "medium"
        "ultra" -> "high"
        "xhigh" -> "xhigh"
        "off" -> "off"
    """
    if not raw:
        return None
    
    key = raw.strip().lower()
    collapsed = key.replace(" ", "").replace("_", "").replace("-", "")
    
    if collapsed in ("xhigh", "extrahigh"):
        return "xhigh"
    
    if key in ("off",):
        return "off"
    
    if key in ("on", "enable", "enabled"):
        return "low"
    
    if key in ("min", "minimal"):
        return "minimal"
    
    if key in ("low", "thinkhard", "think-hard", "think_hard"):
        return "low"
    
    if key in ("mid", "med", "medium", "thinkharder", "think-harder", "harder"):
        return "medium"
    
    if key in ("high", "ultra", "ultrathink", "think-hard", "thinkhardest", "highest", "max"):
        return "high"
    
    if key in ("think",):
        return "minimal"
    
    return None


def supports_xhigh_thinking(provider: str | None, model: str | None) -> bool:
    """
    Check if provider/model supports xhigh thinking.
    
    Mirrors TS supportsXHighThinking from thinking.ts lines 77-87
    """
    model_key = (model or "").strip().lower()
    if not model_key:
        return False
    
    provider_key = (provider or "").strip().lower()
    if provider_key:
        return f"{provider_key}/{model_key}" in XHIGH_MODEL_SET
    
    return model_key in XHIGH_MODEL_IDS


def list_thinking_levels(provider: str | None, model: str | None) -> list[ThinkLevel]:
    """
    List available thinking levels for provider/model.
    
    Mirrors TS listThinkingLevels from thinking.ts lines 89-95
    """
    levels: list[ThinkLevel] = ["off", "minimal", "low", "medium", "high"]
    if supports_xhigh_thinking(provider, model):
        levels.append("xhigh")
    return levels


def list_thinking_level_labels(provider: str | None, model: str | None) -> list[str]:
    """
    List thinking level labels for display.
    
    Binary providers (like zai) use "off"/"on" instead of granular levels.
    
    Mirrors TS listThinkingLevelLabels from thinking.ts lines 97-102
    """
    if is_binary_thinking_provider(provider):
        return ["off", "on"]
    return list(list_thinking_levels(provider, model))


def format_thinking_levels(
    provider: str | None,
    model: str | None,
    separator: str = ", ",
) -> str:
    """
    Format thinking levels as a string for error messages.
    
    Mirrors TS formatThinkingLevels from thinking.ts lines 104-110
    
    Examples:
        format_thinking_levels("openai", "gpt-4") -> "off, minimal, low, medium, high"
        format_thinking_levels("openai", "gpt-5.2") -> "off, minimal, low, medium, high, xhigh"
        format_thinking_levels("zai", "zai-1") -> "off, on"
    """
    return separator.join(list_thinking_level_labels(provider, model))


def format_xhigh_model_hint() -> str:
    """
    Format hint for xhigh-capable models.
    
    Mirrors TS formatXHighModelHint from thinking.ts lines 112-124
    """
    refs = list(XHIGH_MODEL_REFS)
    if len(refs) == 0:
        return "unknown model"
    if len(refs) == 1:
        return refs[0]
    if len(refs) == 2:
        return f"{refs[0]} or {refs[1]}"
    return f"{', '.join(refs[:-1])} or {refs[-1]}"
