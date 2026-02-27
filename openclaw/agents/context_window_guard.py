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


def resolve_context_window_info(
    cfg: dict[str, Any] | None,
    provider: str,
    model_id: str,
    model_context_window: int | None,
    default_tokens: int,
) -> ContextWindowInfo:
    """
    Resolve context window size from multiple sources with priority.
    
    Mirrors TypeScript resolveContextWindowInfo().
    
    Priority order:
    1. cfg.models.providers.{provider}.models[].contextWindow
    2. model_context_window (from model metadata)
    3. cfg.agents.defaults.contextTokens (as upper limit)
    4. default_tokens
    
    Args:
        cfg: OpenClaw configuration dict
        provider: Model provider name (e.g., "google", "anthropic")
        model_id: Model identifier
        model_context_window: Context window from model metadata
        default_tokens: Default fallback value
        
    Returns:
        ContextWindowInfo with tokens and source
    """
    # Priority 1: Check cfg.models.providers.{provider}.models[].contextWindow
    if cfg:
        models_config = cfg.get("models") or {}
        if not isinstance(models_config, dict):
            models_config = {}
        providers_config = models_config.get("providers") or {}
        if not isinstance(providers_config, dict):
            providers_config = {}
        provider_config = providers_config.get(provider) or {}
        if not isinstance(provider_config, dict):
            provider_config = {}
        models_list = provider_config.get("models") or []
        if not isinstance(models_list, list):
            models_list = []
        
        for model_entry in models_list:
            if not isinstance(model_entry, dict):
                continue
            
            # Match by id or idPattern
            entry_id = model_entry.get("id")
            entry_pattern = model_entry.get("idPattern")
            
            is_match = False
            if entry_id and entry_id == model_id:
                is_match = True
            elif entry_pattern:
                # Simple pattern matching (could use regex if needed)
                import re
                try:
                    if re.search(entry_pattern, model_id):
                        is_match = True
                except Exception:
                    pass
            
            if is_match:
                ctx_window = model_entry.get("contextWindow")
                if isinstance(ctx_window, int) and ctx_window > 0:
                    return ContextWindowInfo(
                        tokens=ctx_window,
                        source="modelsConfig"
                    )
    
    # Priority 2: Use model_context_window from model metadata
    if model_context_window and isinstance(model_context_window, int) and model_context_window > 0:
        return ContextWindowInfo(
            tokens=model_context_window,
            source="model"
        )
    
    # Priority 3: Check cfg.agents.defaults.contextTokens (as upper limit)
    if cfg:
        agents_config = cfg.get("agents", {})
        defaults = agents_config.get("defaults", {})
        context_tokens = defaults.get("contextTokens")
        
        if isinstance(context_tokens, int) and context_tokens > 0:
            return ContextWindowInfo(
                tokens=context_tokens,
                source="agentContextTokens"
            )
    
    # Priority 4: Use default_tokens
    return ContextWindowInfo(
        tokens=default_tokens,
        source="default"
    )


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
    should_block = info.tokens < hard_min_tokens
    should_warn = info.tokens < warn_below_tokens
    
    return ContextWindowGuardResult(
        tokens=info.tokens,
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
