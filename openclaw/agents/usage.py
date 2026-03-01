"""Token usage normalization across LLM providers.

Mirrors TypeScript ``src/agents/usage.ts``.

Different providers report token usage with different field names and
conventions.  This module normalises them into a consistent ``NormalizedUsage``
dict so that billing visibility and diagnostics work regardless of provider.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Normalised usage keys — mirrors TS UsageData interface
NormalizedUsage = dict[str, int | None]

# Provider name fragments used for routing logic
_ANTHROPIC = "anthropic"
_OPENAI = "openai"
_GOOGLE = "google"
_OPENROUTER = "openrouter"


def derive_prompt_tokens(
    input_tokens: int | None,
    cache_read_tokens: int | None,
    cache_creation_tokens: int | None,
) -> int | None:
    """Derive total prompt tokens including cached tokens.

    Mirrors TS ``derivePromptTokens``.

    For Anthropic prompt-caching, ``input_tokens`` does NOT include the
    cached portion; we need to add ``cache_read_input_tokens`` and
    ``cache_creation_input_tokens`` to get the full prompt size.
    """
    if input_tokens is None:
        return None
    total = input_tokens
    if cache_read_tokens:
        total += cache_read_tokens
    if cache_creation_tokens:
        total += cache_creation_tokens
    return total


def normalize_usage(raw: Any, provider: str = "") -> NormalizedUsage:
    """Normalise raw token-usage data from any provider.

    Mirrors TS ``normalizeUsage(usage, provider)``.

    Args:
        raw:      Raw usage object/dict from the LLM SDK.  Accepts dict,
                  objects with attributes, or None.
        provider: Provider string hint (e.g. ``"anthropic"``, ``"google"``,
                  ``"openai"``, ``"openrouter"``).  Used to apply
                  provider-specific field mappings.

    Returns:
        ``NormalizedUsage`` with keys:
        - ``input_tokens``   — tokens in the prompt (excl. cache)
        - ``output_tokens``  — tokens generated
        - ``total_tokens``   — input + output (may differ from provider total
                               when caching is active)
        - ``cache_read_tokens``    — Anthropic cache-read tokens (or None)
        - ``cache_creation_tokens`` — Anthropic cache-creation tokens (or None)
        - ``prompt_tokens``  — full prompt size (input + cache portions)
    """
    if raw is None:
        return _empty_usage()

    def _get(key: str, *alt_keys: str) -> int | None:
        for k in (key, *alt_keys):
            if isinstance(raw, dict):
                v = raw.get(k)
            else:
                v = getattr(raw, k, None)
            if isinstance(v, int):
                return v
        return None

    prov = provider.lower()

    # Input / prompt tokens
    input_tokens = _get(
        "input_tokens",
        "prompt_tokens",
        "promptTokenCount",
        "prompt_token_count",
    )

    # Output / completion tokens
    output_tokens = _get(
        "output_tokens",
        "completion_tokens",
        "candidatesTokenCount",
        "candidates_token_count",
    )

    # Total tokens (provider-reported)
    total_tokens_raw = _get(
        "total_tokens",
        "totalTokenCount",
        "total_token_count",
    )

    # Anthropic-specific: cache token breakdown
    cache_read_tokens = None
    cache_creation_tokens = None
    if _ANTHROPIC in prov or "claude" in prov:
        cache_read_tokens = _get(
            "cache_read_input_tokens",
            "cache_read_tokens",
        )
        cache_creation_tokens = _get(
            "cache_creation_input_tokens",
            "cache_creation_tokens",
        )

    # Derive full prompt size (input + cache portions)
    prompt_tokens = derive_prompt_tokens(input_tokens, cache_read_tokens, cache_creation_tokens)

    # Compute total if provider did not report it
    if total_tokens_raw is None and input_tokens is not None and output_tokens is not None:
        total_tokens_raw = input_tokens + output_tokens

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens_raw,
        "cache_read_tokens": cache_read_tokens,
        "cache_creation_tokens": cache_creation_tokens,
        "prompt_tokens": prompt_tokens,
    }


def _empty_usage() -> NormalizedUsage:
    return {
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
        "cache_read_tokens": None,
        "cache_creation_tokens": None,
        "prompt_tokens": None,
    }


def persist_run_session_usage(
    session_id: str,
    usage: NormalizedUsage,
    session_manager: Any = None,
) -> None:
    """Persist normalised usage counters to the session entry.

    Mirrors TS ``persistRunSessionUsage`` — called after every completed turn
    so that billing and diagnostics data is stored on the session record.

    Args:
        session_id:      Session identifier.
        usage:           Normalised usage dict from ``normalize_usage``.
        session_manager: Optional session manager with ``update_session``
                         or ``get_session_entry`` method.
    """
    if not session_manager:
        return

    input_t = usage.get("input_tokens") or 0
    output_t = usage.get("output_tokens") or 0
    total_t = usage.get("total_tokens") or (input_t + output_t)

    try:
        if hasattr(session_manager, "update_session"):
            session_manager.update_session(session_id, {
                "inputTokens": input_t,
                "outputTokens": output_t,
                "totalTokens": total_t,
            })
        elif hasattr(session_manager, "get_session_entry"):
            entry = session_manager.get_session_entry(session_id)
            if isinstance(entry, dict):
                entry["inputTokens"] = (entry.get("inputTokens") or 0) + input_t
                entry["outputTokens"] = (entry.get("outputTokens") or 0) + output_t
                entry["totalTokens"] = (entry.get("totalTokens") or 0) + total_t
    except Exception as exc:
        logger.debug("persist_run_session_usage: %s", exc)


__all__ = [
    "NormalizedUsage",
    "normalize_usage",
    "derive_prompt_tokens",
    "persist_run_session_usage",
]
