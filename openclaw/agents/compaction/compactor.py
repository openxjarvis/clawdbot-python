"""Compaction helper used by Agent.compact().

Wraps the stage-based summarization pipeline from functions.py so that
Agent.compact() can call a single ``compact_messages()`` function.

Mirrors the TypeScript Agent.compact() implementation which calls
compactEmbeddedPiSession() under the hood.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from .functions import (
    build_compaction_summarization_instructions,
    estimate_messages_tokens,
    prune_history_for_context_share,
    resolve_context_window_tokens,
    summarize_in_stages,
)

logger = logging.getLogger(__name__)

_DEFAULT_MAX_HISTORY_SHARE = 0.5
_DEFAULT_RESERVE_TOKENS = 16_384
_DEFAULT_MAX_CHUNK_TOKENS = 20_000


async def compact_messages(
    messages: list[dict[str, Any]],
    provider: Any | None = None,
    model: Any | None = None,
    api_key: str | None = None,
    context_window: int | None = None,
    max_history_share: float = _DEFAULT_MAX_HISTORY_SHARE,
    reserve_tokens: int = _DEFAULT_RESERVE_TOKENS,
    max_chunk_tokens: int = _DEFAULT_MAX_CHUNK_TOKENS,
    custom_instructions: str | None = None,
    identifier_policy: str | None = None,
    identifier_instructions: str | None = None,
) -> list[dict[str, Any]]:
    """Compact a message list by summarizing dropped context.

    Used by ``Agent.compact()`` for manual compaction and by the overflow
    compaction path in the gateway pi_runtime.

    Steps:
    1. Prune history (drop oldest ~50% by token share)
    2. Summarize dropped messages via LLM (multi-stage)
    3. Return [summary_message] + kept_messages

    Args:
        messages: Full conversation history.
        provider: LLM provider instance (used to extract api_key/model if needed).
        model: Model info dict or model object.
        api_key: API key override (falls back to env vars).
        context_window: Context window token count; auto-resolved if None.
        max_history_share: Fraction of context window to budget for history.
        reserve_tokens: Tokens reserved for system prompt overhead.
        max_chunk_tokens: Max tokens per summary chunk.
        custom_instructions: Extra instructions injected into summarization prompt.
        identifier_policy: "strict" | "off" | "custom" — controls identifier preservation.
            Mirrors TS CompactionConfig.identifierPolicy.
        identifier_instructions: Custom identifier instructions used when policy="custom".
            Mirrors TS CompactionConfig.identifierInstructions.

    Returns:
        New message list: [compaction_summary_message] + kept_messages,
        or the original messages if nothing was dropped.
    """
    if not messages:
        return messages

    # Resolve context window
    if context_window is None:
        model_dict: dict[str, Any] = {}
        if isinstance(model, dict):
            model_dict = model
        elif model is not None:
            model_dict = {
                "model": getattr(model, "id", str(model)),
                "contextWindow": getattr(model, "context_window", None),
            }
        context_window = resolve_context_window_tokens(model_dict)

    # Step 1: prune
    prune_result = prune_history_for_context_share(
        messages=messages,
        max_context_tokens=context_window,
        max_history_share=max_history_share,
    )
    dropped = prune_result["dropped_messages_list"]
    kept = prune_result["messages"]

    if not dropped:
        logger.debug("compact_messages: nothing to drop — messages already fit budget")
        return messages

    logger.info(
        "compact_messages: dropped %d messages (%d tokens), kept %d (%d tokens)",
        len(dropped),
        prune_result["dropped_tokens"],
        len(kept),
        prune_result["kept_tokens"],
    )

    # Step 2: resolve API key
    resolved_key = api_key or ""
    if not resolved_key and provider is not None:
        resolved_key = (
            getattr(provider, "api_key", None)
            or getattr(provider, "_api_key", None)
            or ""
        )
    if not resolved_key:
        for env_var in (
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "GOOGLE_API_KEY",
            "GEMINI_API_KEY",
        ):
            resolved_key = os.environ.get(env_var, "")
            if resolved_key:
                break

    # Step 3: build model info dict
    model_info: dict[str, Any] = {}
    if isinstance(model, dict):
        model_info = model
    elif model is not None:
        model_info = {
            "provider": getattr(model, "provider", "openai"),
            "model": getattr(model, "id", str(model)),
            "contextWindow": context_window,
        }
    model_info.setdefault("contextWindow", context_window)

    # Build combined instructions using identifier policy — mirrors TS buildCompactionSummarizationInstructions()
    effective_instructions = build_compaction_summarization_instructions(
        custom_instructions=custom_instructions,
        identifier_policy=identifier_policy,
        identifier_instructions=identifier_instructions,
    )

    # Step 4: summarize
    if resolved_key:
        try:
            summary = await summarize_in_stages(
                messages=dropped,
                model=model_info,
                api_key=resolved_key,
                signal=None,
                reserve_tokens=reserve_tokens,
                max_chunk_tokens=max_chunk_tokens,
                context_window=context_window,
                custom_instructions=effective_instructions,
            )
        except Exception as exc:
            logger.warning("compact_messages summarization failed: %s", exc)
            summary = (
                f"[Compaction fallback] {len(dropped)} messages dropped "
                f"({prune_result['dropped_tokens']} tokens). "
                "Summary unavailable."
            )
    else:
        logger.warning("compact_messages: no API key available — using fallback summary")
        summary = (
            f"[Compaction] {len(dropped)} messages summarized "
            f"({prune_result['dropped_tokens']} tokens dropped)."
        )

    # Step 5: build compaction message
    compaction_message: dict[str, Any] = {
        "role": "user",
        "content": f"[Conversation history summary]\n{summary}",
    }

    return [compaction_message] + kept
