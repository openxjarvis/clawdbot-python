"""
Context Window Guard - mirrors TypeScript context-window-guard.ts

Provides intelligent context window resolution and validation with multiple
fallback sources to determine the actual context window size.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


# Constants aligned with TS
CONTEXT_WINDOW_HARD_MIN_TOKENS = 16_000
CONTEXT_WINDOW_WARN_BELOW_TOKENS = 32_000


@dataclass
class ContextWindowInfo:
    """Information about resolved context window."""
    tokens: int
    source: Literal["model", "modelsConfig", "agentContextTokens", "default"]


@dataclass
class ContextWindowGuardResult(ContextWindowInfo):
    """Result from context window guard evaluation."""
    should_warn: bool
    should_block: bool


def _normalize_positive_int(value: Any) -> int | None:
    """Return the floor of a positive finite number, or None."""
    if not isinstance(value, (int, float)):
        return None
    if value != value or value == float("inf") or value == float("-inf"):
        return None
    v = int(value)
    return v if v > 0 else None


def resolve_context_window_info(
    cfg: dict[str, Any] | None,
    provider: str,
    model_id: str,
    model_context_window: int | None,
    default_tokens: int,
) -> ContextWindowInfo:
    """Resolve context window size from multiple sources.

    Mirrors TypeScript resolveContextWindowInfo().

    Resolution order:
    1. ``cfg.models.providers.{provider}.models[].contextWindow``
    2. ``model_context_window`` (from model metadata)
    3. ``default_tokens`` (fallback)

    Then, ``cfg.agents.defaults.contextTokens`` is applied as a
    **post-resolution upper cap**: if it is lower than the resolved
    value, it replaces it.  This matches the TS behaviour where
    ``agentContextTokens`` is not a priority-3 fallback but a cap.

    Args:
        cfg: OpenClaw configuration dict
        provider: Model provider name (e.g., "google", "anthropic")
        model_id: Model identifier
        model_context_window: Context window from model metadata
        default_tokens: Default fallback value

    Returns:
        ContextWindowInfo with tokens and source
    """
    import re as _re

    # Priority 1: cfg.models.providers.{provider}.models[].contextWindow
    from_models_config: int | None = None
    if cfg:
        models_config = cfg.get("models") if isinstance(cfg, dict) else {}
        if not isinstance(models_config, dict):
            models_config = {}
        providers_config = models_config.get("providers") or {}
        if not isinstance(providers_config, dict):
            providers_config = {}
        provider_config = providers_config.get(provider) or {}
        if not isinstance(provider_config, dict):
            provider_config = {}
        models_list = provider_config.get("models") or []
        if isinstance(models_list, list):
            for model_entry in models_list:
                if not isinstance(model_entry, dict):
                    continue
                entry_id = model_entry.get("id")
                if entry_id == model_id:
                    from_models_config = _normalize_positive_int(model_entry.get("contextWindow"))
                    if from_models_config:
                        break

    # Priority 2: model_context_window
    from_model = _normalize_positive_int(model_context_window)

    # Determine base info (before cap)
    if from_models_config:
        base_info = ContextWindowInfo(tokens=from_models_config, source="modelsConfig")
    elif from_model:
        base_info = ContextWindowInfo(tokens=from_model, source="model")
    else:
        base_info = ContextWindowInfo(tokens=max(1, int(default_tokens)), source="default")

    # Post-resolution upper cap: cfg.agents.defaults.contextTokens
    cap_tokens: int | None = None
    if cfg:
        agents_config = cfg.get("agents", {}) if isinstance(cfg, dict) else {}
        if not isinstance(agents_config, dict):
            agents_config = {}
        defaults = agents_config.get("defaults", {}) if isinstance(agents_config, dict) else {}
        if not isinstance(defaults, dict):
            defaults = {}
        cap_tokens = _normalize_positive_int(defaults.get("contextTokens"))

    if cap_tokens and cap_tokens < base_info.tokens:
        return ContextWindowInfo(tokens=cap_tokens, source="agentContextTokens")

    return base_info


def evaluate_context_window_guard(
    info: ContextWindowInfo,
    warn_below_tokens: int = CONTEXT_WINDOW_WARN_BELOW_TOKENS,
    hard_min_tokens: int = CONTEXT_WINDOW_HARD_MIN_TOKENS,
) -> ContextWindowGuardResult:
    """
    Evaluate if context window needs warnings or blocking.
    
    Mirrors TypeScript evaluateContextWindowGuard().
    
    Args:
        info: Context window info to evaluate
        warn_below_tokens: Warning threshold (default 32K)
        hard_min_tokens: Hard minimum threshold (default 16K)
        
    Returns:
        ContextWindowGuardResult with evaluation flags
    """
    warn_below = max(1, int(warn_below_tokens))
    hard_min = max(1, int(hard_min_tokens))
    tokens = max(0, int(info.tokens))
    # tokens > 0 guard: mirrors TS behaviour — 0 means "unknown", not "blocked"
    should_block = tokens > 0 and tokens < hard_min
    should_warn = tokens > 0 and tokens < warn_below

    return ContextWindowGuardResult(
        tokens=tokens,
        source=info.source,
        should_warn=should_warn,
        should_block=should_block,
    )


def resolve_and_guard_context_window(
    cfg: dict[str, Any] | None,
    provider: str,
    model_id: str,
    model_context_window: int | None,
    default_tokens: int,
    warn_below_tokens: int = CONTEXT_WINDOW_WARN_BELOW_TOKENS,
    hard_min_tokens: int = CONTEXT_WINDOW_HARD_MIN_TOKENS,
) -> ContextWindowGuardResult:
    """
    Convenience function to resolve and evaluate in one step.
    
    Args:
        cfg: OpenClaw configuration dict
        provider: Model provider name
        model_id: Model identifier
        model_context_window: Context window from model metadata
        default_tokens: Default fallback value
        warn_below_tokens: Warning threshold
        hard_min_tokens: Hard minimum threshold
        
    Returns:
        ContextWindowGuardResult with tokens, source, and flags
    """
    info = resolve_context_window_info(
        cfg=cfg,
        provider=provider,
        model_id=model_id,
        model_context_window=model_context_window,
        default_tokens=default_tokens,
    )
    
    return evaluate_context_window_guard(
        info=info,
        warn_below_tokens=warn_below_tokens,
        hard_min_tokens=hard_min_tokens,
    )
