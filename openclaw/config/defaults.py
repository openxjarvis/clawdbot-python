"""
Config runtime defaults — matches openclaw/src/config/defaults.ts

Applies sensible defaults to loaded config objects before use.
"""
from __future__ import annotations

import copy
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (match TS DEFAULT_MODEL_ALIASES etc.)
# ---------------------------------------------------------------------------

DEFAULT_CONTEXT_TOKENS = 8192
DEFAULT_MODEL_MAX_TOKENS = 8192
DEFAULT_AGENT_MAX_CONCURRENT = 1
DEFAULT_SUBAGENT_MAX_CONCURRENT = 10

DEFAULT_MODEL_ALIASES: Dict[str, str] = {
    # Anthropic
    "opus": "anthropic/claude-opus-4-6",
    "sonnet": "anthropic/claude-sonnet-4-6",
    # OpenAI
    "gpt": "openai/gpt-5.2",
    "gpt-mini": "openai/gpt-5-mini",
    # Google Gemini
    "gemini": "google/gemini-3-pro-preview",
    "gemini-flash": "google/gemini-3-flash-preview",
}

DEFAULT_MODEL_COST: Dict[str, float] = {
    "input": 0.0,
    "output": 0.0,
    "cacheRead": 0.0,
    "cacheWrite": 0.0,
}

DEFAULT_MODEL_INPUT = ["text"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_positive_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def _get(obj: Any, *keys: str, default: Any = None) -> Any:
    """Drill into nested dict/attr object, returning default if missing."""
    current = obj
    for key in keys:
        if current is None:
            return default
        if isinstance(current, dict):
            current = current.get(key)
        else:
            current = getattr(current, key, None)
    return current if current is not None else default


def _set(obj: Any, key: str, value: Any) -> None:
    """Set a key on a dict or object attribute."""
    if isinstance(obj, dict):
        obj[key] = value
    else:
        setattr(obj, key, value)


def _setdefault(obj: Any, key: str, value: Any) -> None:
    """Set key only if it is not already set (not None)."""
    current = obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)
    if current is None:
        _set(obj, key, value)


# ---------------------------------------------------------------------------
# Individual default appliers
# ---------------------------------------------------------------------------

def apply_model_defaults(cfg: Any) -> Any:
    """
    Apply defaults to models configuration.

    - Adds model aliases if not already present.
    - Fills missing cost/input/contextWindow/maxTokens/reasoning fields.

    Matches TS applyModelDefaults().
    """
    models_cfg = _get(cfg, "models")
    if models_cfg is None:
        return cfg

    # Apply aliases (only if not already defined)
    definitions = _get(models_cfg, "definitions")
    if isinstance(definitions, dict):
        for alias, target in DEFAULT_MODEL_ALIASES.items():
            if alias not in definitions:
                definitions[alias] = {"id": alias, "name": alias, "aliasFor": target}

    # Apply per-model-definition defaults
    if isinstance(definitions, dict):
        for model_id, model_def in definitions.items():
            if not isinstance(model_def, dict):
                continue
            _setdefault(model_def, "reasoning", False)
            _setdefault(model_def, "input", list(DEFAULT_MODEL_INPUT))
            if model_def.get("cost") is None:
                model_def["cost"] = dict(DEFAULT_MODEL_COST)
            else:
                cost = model_def["cost"]
                if isinstance(cost, dict):
                    for k, v in DEFAULT_MODEL_COST.items():
                        cost.setdefault(k, v)
            ctx = model_def.get("contextWindow")
            if not _is_positive_number(ctx):
                model_def["contextWindow"] = DEFAULT_CONTEXT_TOKENS
            max_tokens = model_def.get("maxTokens")
            if not _is_positive_number(max_tokens):
                model_def["maxTokens"] = min(DEFAULT_MODEL_MAX_TOKENS, model_def["contextWindow"])

    return cfg


def apply_agent_defaults(cfg: Any) -> Any:
    """
    Apply defaults to agents configuration.

    - maxConcurrent → DEFAULT_AGENT_MAX_CONCURRENT
    - subagents.maxConcurrent → DEFAULT_SUBAGENT_MAX_CONCURRENT

    Matches TS applyAgentDefaults().
    """
    agents_cfg = _get(cfg, "agents")
    if agents_cfg is None:
        return cfg

    # Global agent concurrent limit
    if isinstance(agents_cfg, dict):
        if agents_cfg.get("maxConcurrent") is None:
            agents_cfg["maxConcurrent"] = DEFAULT_AGENT_MAX_CONCURRENT
        subagents = agents_cfg.get("subagents")
        if isinstance(subagents, dict):
            subagents.setdefault("maxConcurrent", DEFAULT_SUBAGENT_MAX_CONCURRENT)
    else:
        if getattr(agents_cfg, "maxConcurrent", None) is None:
            setattr(agents_cfg, "maxConcurrent", DEFAULT_AGENT_MAX_CONCURRENT)

    return cfg


def apply_session_defaults(cfg: Any) -> Any:
    """
    Apply defaults to session configuration.

    - session.mainKey is always normalized to "main" (warns if different).

    Matches TS applySessionDefaults().
    """
    session_cfg = _get(cfg, "session")
    if session_cfg is None:
        return cfg

    main_key = _get(session_cfg, "mainKey")
    if main_key is not None and main_key != "main":
        logger.warning(
            "[config] session.mainKey=%r is not supported; it will be overridden to 'main'",
            main_key,
        )
    _set(session_cfg if isinstance(session_cfg, dict) else session_cfg, "mainKey", "main")

    return cfg


def apply_message_defaults(cfg: Any) -> Any:
    """
    Apply defaults to message configuration.

    - message.ackReactionScope → "group-mentions"

    Matches TS applyMessageDefaults().
    """
    message_cfg = _get(cfg, "message")
    if isinstance(message_cfg, dict):
        message_cfg.setdefault("ackReactionScope", "group-mentions")
    return cfg


def apply_logging_defaults(cfg: Any) -> Any:
    """
    Apply defaults to logging configuration.

    - logging.redactSensitive → "tools"

    Matches TS applyLoggingDefaults().
    """
    logging_cfg = _get(cfg, "logging")
    if isinstance(logging_cfg, dict):
        logging_cfg.setdefault("redactSensitive", "tools")
    return cfg


def apply_context_pruning_defaults(cfg: Any) -> Any:
    """
    Apply defaults to context pruning configuration.

    - contextPruning.mode → "cache-ttl"
    - contextPruning.ttl → "1h"
    - heartbeat.every → "1h" (OAuth) / "30m" (API key)
    - cacheRetention → "short" for Anthropic API key

    Matches TS applyContextPruningDefaults().
    """
    pruning_cfg = _get(cfg, "contextPruning")
    if isinstance(pruning_cfg, dict):
        pruning_cfg.setdefault("mode", "cache-ttl")
        pruning_cfg.setdefault("ttl", "1h")

    heartbeat_cfg = _get(cfg, "heartbeat")
    if isinstance(heartbeat_cfg, dict):
        heartbeat_cfg.setdefault("every", "1h")

    return cfg


def apply_compaction_defaults(cfg: Any) -> Any:
    """
    Apply defaults to compaction configuration.

    - compaction.mode → "safeguard"

    Matches TS applyCompactionDefaults().
    """
    compaction_cfg = _get(cfg, "compaction")
    if isinstance(compaction_cfg, dict):
        compaction_cfg.setdefault("mode", "safeguard")
    return cfg


def apply_all_defaults(cfg: Any) -> Any:
    """
    Apply all runtime defaults in the correct order.

    Mirrors the sequence in TS loadConfig() after validation.
    """
    cfg = apply_model_defaults(cfg)
    cfg = apply_agent_defaults(cfg)
    cfg = apply_session_defaults(cfg)
    cfg = apply_message_defaults(cfg)
    cfg = apply_logging_defaults(cfg)
    cfg = apply_context_pruning_defaults(cfg)
    cfg = apply_compaction_defaults(cfg)
    return cfg


def reset_session_defaults_warning_for_tests() -> None:
    """Reset warning state for tests (matches TS resetSessionDefaultsWarningForTests)."""
    pass  # Python logging doesn't have dedup state; no-op


__all__ = [
    "DEFAULT_CONTEXT_TOKENS",
    "DEFAULT_MODEL_MAX_TOKENS",
    "DEFAULT_AGENT_MAX_CONCURRENT",
    "DEFAULT_SUBAGENT_MAX_CONCURRENT",
    "DEFAULT_MODEL_ALIASES",
    "DEFAULT_MODEL_COST",
    "DEFAULT_MODEL_INPUT",
    "apply_model_defaults",
    "apply_agent_defaults",
    "apply_session_defaults",
    "apply_message_defaults",
    "apply_logging_defaults",
    "apply_context_pruning_defaults",
    "apply_compaction_defaults",
    "apply_all_defaults",
    "reset_session_defaults_warning_for_tests",
]
