"""
TS-aligned compaction functions — mirrors TypeScript openclaw/src/agents/compaction.ts.

Provides:
- estimate_messages_tokens
- split_messages_by_token_share
- chunk_messages_by_max_tokens
- compute_adaptive_chunk_ratio
- is_oversized_for_summary
- summarize_with_fallback
- summarize_in_stages
- prune_history_for_context_share
- resolve_context_window_tokens
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable, TypeVar

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — match TS values exactly
# ---------------------------------------------------------------------------
BASE_CHUNK_RATIO = 0.4
MIN_CHUNK_RATIO = 0.15
SAFETY_MARGIN = 1.2  # 20% buffer for estimate_tokens inaccuracy

_DEFAULT_SUMMARY_FALLBACK = "No prior history."
_DEFAULT_PARTS = 2
_MERGE_SUMMARIES_INSTRUCTIONS = (
    "Merge these partial summaries into a single cohesive summary. Preserve decisions,"
    " TODOs, open questions, and any constraints."
)


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

def _estimate_single_message_tokens(msg: dict[str, Any]) -> int:
    """Estimate tokens for a single message using char-count heuristic."""
    # 4 token overhead per message (matches pi-mono)
    total = 4
    content = msg.get("content", "")
    if isinstance(content, str):
        total += max(1, int(len(content) / 3.5 * 1.1))
    elif isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                text = block.get("text") or block.get("content") or ""
                total += max(0, int(len(str(text)) / 3.5 * 1.1))
    return total


def _strip_tool_result_details(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove `details` field from toolResult messages (security: never feed to LLM)."""
    touched = False
    out: list[dict[str, Any]] = []
    for msg in messages:
        if isinstance(msg, dict) and msg.get("role") == "toolResult" and "details" in msg:
            msg = {k: v for k, v in msg.items() if k != "details"}
            touched = True
        out.append(msg)
    return out if touched else messages


def _repair_tool_use_result_pairing(
    messages: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Drop orphaned toolResult messages (those without a preceding matching toolCall).
    Returns {"messages": ..., "dropped_orphan_count": int}.
    Simplified Python version of TS repairToolUseResultPairing — enough for compaction.
    """
    out: list[dict[str, Any]] = []
    dropped_orphan_count = 0

    # Build set of tool-call ids emitted by assistant messages
    pending_ids: set[str] = set()

    for msg in messages:
        if not isinstance(msg, dict):
            out.append(msg)
            continue

        role = msg.get("role")
        if role == "assistant":
            content = msg.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        btype = block.get("type", "")
                        if btype in ("toolCall", "toolUse", "functionCall"):
                            tool_id = block.get("id", "")
                            if tool_id:
                                pending_ids.add(tool_id)
            out.append(msg)
        elif role == "toolResult":
            tool_id = msg.get("toolCallId") or msg.get("tool_call_id") or ""
            if tool_id and tool_id in pending_ids:
                pending_ids.discard(tool_id)
                out.append(msg)
            else:
                dropped_orphan_count += 1
        else:
            out.append(msg)

    return {"messages": out, "dropped_orphan_count": dropped_orphan_count}


# ---------------------------------------------------------------------------
# Public API — mirrors TS compaction.ts exports
# ---------------------------------------------------------------------------

def estimate_messages_tokens(messages: list[dict[str, Any]]) -> int:
    """
    Estimate total token count for a list of messages.
    Strips toolResult.details before counting (security boundary).
    Mirrors TS estimateMessagesTokens().
    """
    safe = _strip_tool_result_details(messages)
    return sum(_estimate_single_message_tokens(msg) for msg in safe)


def _normalize_parts(parts: float | int, message_count: int) -> int:
    if not (isinstance(parts, (int, float)) and parts > 1):
        return 1
    return min(max(1, int(parts)), max(1, message_count))


def split_messages_by_token_share(
    messages: list[dict[str, Any]],
    parts: int = _DEFAULT_PARTS,
) -> list[list[dict[str, Any]]]:
    """
    Split messages into `parts` roughly equal-token chunks.
    Mirrors TS splitMessagesByTokenShare().
    """
    if not messages:
        return []
    normalized_parts = _normalize_parts(parts, len(messages))
    if normalized_parts <= 1:
        return [messages]

    total_tokens = estimate_messages_tokens(messages)
    target_tokens = total_tokens / normalized_parts
    chunks: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_tokens = 0

    for msg in messages:
        msg_tokens = _estimate_single_message_tokens(msg)
        if (
            len(chunks) < normalized_parts - 1
            and current
            and current_tokens + msg_tokens > target_tokens
        ):
            chunks.append(current)
            current = []
            current_tokens = 0
        current.append(msg)
        current_tokens += msg_tokens

    if current:
        chunks.append(current)

    return chunks


def chunk_messages_by_max_tokens(
    messages: list[dict[str, Any]],
    max_tokens: int,
) -> list[list[dict[str, Any]]]:
    """
    Split messages into chunks each <= max_tokens.
    Mirrors TS chunkMessagesByMaxTokens().
    """
    if not messages:
        return []

    chunks: list[list[dict[str, Any]]] = []
    current_chunk: list[dict[str, Any]] = []
    current_tokens = 0

    for msg in messages:
        msg_tokens = _estimate_single_message_tokens(msg)
        if current_chunk and current_tokens + msg_tokens > max_tokens:
            chunks.append(current_chunk)
            current_chunk = []
            current_tokens = 0
        current_chunk.append(msg)
        current_tokens += msg_tokens
        if msg_tokens > max_tokens:
            # Oversized single message — flush immediately
            chunks.append(current_chunk)
            current_chunk = []
            current_tokens = 0

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def compute_adaptive_chunk_ratio(
    messages: list[dict[str, Any]],
    context_window: int,
) -> float:
    """
    Compute chunk ratio based on average message size.
    Returns float in [MIN_CHUNK_RATIO, BASE_CHUNK_RATIO].
    Mirrors TS computeAdaptiveChunkRatio().
    """
    if not messages:
        return BASE_CHUNK_RATIO

    total_tokens = estimate_messages_tokens(messages)
    avg_tokens = total_tokens / len(messages)
    safe_avg_tokens = avg_tokens * SAFETY_MARGIN
    avg_ratio = safe_avg_tokens / context_window

    if avg_ratio > 0.1:
        reduction = min(avg_ratio * 2, BASE_CHUNK_RATIO - MIN_CHUNK_RATIO)
        return max(MIN_CHUNK_RATIO, BASE_CHUNK_RATIO - reduction)

    return BASE_CHUNK_RATIO


def is_oversized_for_summary(msg: dict[str, Any], context_window: int) -> bool:
    """
    Return True if a single message is > 50% of the context window.
    Mirrors TS isOversizedForSummary().
    """
    tokens = _estimate_single_message_tokens(msg) * SAFETY_MARGIN
    return tokens > context_window * 0.5


async def _retry_async(
    fn: Callable[[], Awaitable[str]],
    attempts: int = 3,
    min_delay_ms: float = 500,
    max_delay_ms: float = 5000,
) -> str:
    """Simple async retry helper mirroring TS retryAsync()."""
    last_exc: Exception = RuntimeError("no attempts")
    delay = min_delay_ms / 1000
    for attempt in range(attempts):
        try:
            return await fn()
        except Exception as exc:
            if "AbortError" in type(exc).__name__:
                raise
            last_exc = exc
            if attempt < attempts - 1:
                await asyncio.sleep(min(delay, max_delay_ms / 1000))
                delay = min(delay * 2, max_delay_ms / 1000)
    raise last_exc


async def _generate_summary_via_llm(
    messages: list[dict[str, Any]],
    model: dict[str, Any],
    reserve_tokens: int,
    api_key: str,
    signal: Any,
    custom_instructions: str | None,
    previous_summary: str | None,
) -> str:
    """
    Call an LLM to summarise messages — Python equivalent of TS generateSummary().
    Falls back to a text-based digest when no LLM is available.
    """
    prompt_parts: list[str] = []

    if previous_summary:
        prompt_parts.append(f"Previous summary:\n{previous_summary}\n")

    if custom_instructions:
        prompt_parts.append(f"Instructions:\n{custom_instructions}\n")

    prompt_parts.append("Messages to summarise:")
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if isinstance(content, list):
            text = " ".join(
                b.get("text", "") if isinstance(b, dict) else str(b)
                for b in content
                if isinstance(b, dict) and "text" in b
            )
        else:
            text = str(content)
        prompt_parts.append(f"[{role}]: {text[:500]}")

    system_prompt = (
        "You are a concise summariser. Produce a clear, factual summary of the conversation "
        "history preserving all key decisions, TODOs, open questions, and constraints."
    )
    user_prompt = "\n".join(prompt_parts)

    try:
        provider = model.get("provider", "anthropic")
        model_id = model.get("model", "claude-opus-4-6")

        if provider == "anthropic":
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=api_key)
            response = await client.messages.create(
                model=model_id,
                max_tokens=reserve_tokens or 1024,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return response.content[0].text if response.content else _DEFAULT_SUMMARY_FALLBACK

        if provider in ("google", "gemini"):
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            gmodel = genai.GenerativeModel(model_id, system_instruction=system_prompt)
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: gmodel.generate_content(user_prompt),
            )
            return result.text or _DEFAULT_SUMMARY_FALLBACK

        if provider == "openai":
            import openai
            client = openai.AsyncOpenAI(api_key=api_key)
            resp = await client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=reserve_tokens or 1024,
            )
            return resp.choices[0].message.content or _DEFAULT_SUMMARY_FALLBACK

    except Exception as exc:
        logger.warning("LLM summarisation failed: %s", exc)

    # Text-based fallback digest
    lines = [f"[{m.get('role','?')}]: {str(m.get('content',''))[:200]}" for m in messages[:20]]
    return f"Summary of {len(messages)} messages:\n" + "\n".join(lines)


async def _summarize_chunks(
    messages: list[dict[str, Any]],
    model: dict[str, Any],
    api_key: str,
    signal: Any,
    reserve_tokens: int,
    max_chunk_tokens: int,
    custom_instructions: str | None = None,
    previous_summary: str | None = None,
) -> str:
    if not messages:
        return previous_summary or _DEFAULT_SUMMARY_FALLBACK

    safe_messages = _strip_tool_result_details(messages)
    chunks = chunk_messages_by_max_tokens(safe_messages, max_chunk_tokens)
    summary = previous_summary

    for chunk in chunks:
        captured_summary = summary
        captured_chunk = chunk

        async def _do_summarize() -> str:
            return await _generate_summary_via_llm(
                captured_chunk,
                model,
                reserve_tokens,
                api_key,
                signal,
                custom_instructions,
                captured_summary,
            )

        summary = await _retry_async(_do_summarize, attempts=3)

    return summary or _DEFAULT_SUMMARY_FALLBACK


async def summarize_with_fallback(
    messages: list[dict[str, Any]],
    model: dict[str, Any],
    api_key: str,
    signal: Any,
    reserve_tokens: int,
    max_chunk_tokens: int,
    context_window: int,
    custom_instructions: str | None = None,
    previous_summary: str | None = None,
) -> str:
    """
    Summarise with progressive fallback for oversized messages.
    Mirrors TS summarizeWithFallback().
    """
    if not messages:
        return previous_summary or _DEFAULT_SUMMARY_FALLBACK

    # Try full summarisation first
    try:
        return await _summarize_chunks(
            messages, model, api_key, signal, reserve_tokens, max_chunk_tokens,
            custom_instructions, previous_summary,
        )
    except Exception as full_err:
        logger.warning("Full summarisation failed, trying partial: %s", full_err)

    # Fallback 1: Summarise only small messages, note oversized ones
    small_messages: list[dict[str, Any]] = []
    oversized_notes: list[str] = []

    for msg in messages:
        if is_oversized_for_summary(msg, context_window):
            role = msg.get("role", "message")
            tokens = _estimate_single_message_tokens(msg)
            oversized_notes.append(
                f"[Large {role} (~{round(tokens / 1000)}K tokens) omitted from summary]"
            )
        else:
            small_messages.append(msg)

    if small_messages:
        try:
            partial_summary = await _summarize_chunks(
                small_messages, model, api_key, signal, reserve_tokens, max_chunk_tokens,
                custom_instructions, previous_summary,
            )
            notes = ("\n\n" + "\n".join(oversized_notes)) if oversized_notes else ""
            return partial_summary + notes
        except Exception as partial_err:
            logger.warning("Partial summarisation also failed: %s", partial_err)

    # Final fallback: digest
    return (
        f"Context contained {len(messages)} messages "
        f"({len(oversized_notes)} oversized). "
        f"Summary unavailable due to size limits."
    )


async def summarize_in_stages(
    messages: list[dict[str, Any]],
    model: dict[str, Any],
    api_key: str,
    signal: Any,
    reserve_tokens: int,
    max_chunk_tokens: int,
    context_window: int,
    custom_instructions: str | None = None,
    previous_summary: str | None = None,
    parts: int = _DEFAULT_PARTS,
    min_messages_for_split: int = 4,
) -> str:
    """
    Multi-stage summarisation with partial summary merging.
    Mirrors TS summarizeInStages().
    """
    if not messages:
        return previous_summary or _DEFAULT_SUMMARY_FALLBACK

    min_for_split = max(2, min_messages_for_split)
    normalized_parts = _normalize_parts(parts, len(messages))
    total_tokens = estimate_messages_tokens(messages)

    if (
        normalized_parts <= 1
        or len(messages) < min_for_split
        or total_tokens <= max_chunk_tokens
    ):
        return await summarize_with_fallback(
            messages, model, api_key, signal, reserve_tokens, max_chunk_tokens,
            context_window, custom_instructions, previous_summary,
        )

    splits = [
        chunk
        for chunk in split_messages_by_token_share(messages, normalized_parts)
        if chunk
    ]

    if len(splits) <= 1:
        return await summarize_with_fallback(
            messages, model, api_key, signal, reserve_tokens, max_chunk_tokens,
            context_window, custom_instructions, previous_summary,
        )

    partial_summaries: list[str] = []
    for chunk in splits:
        partial = await summarize_with_fallback(
            chunk, model, api_key, signal, reserve_tokens, max_chunk_tokens,
            context_window, custom_instructions, previous_summary=None,
        )
        partial_summaries.append(partial)

    if len(partial_summaries) == 1:
        return partial_summaries[0]

    summary_messages = [
        {"role": "user", "content": s, "timestamp": int(time.time() * 1000)}
        for s in partial_summaries
    ]

    merge_instructions = (
        f"{_MERGE_SUMMARIES_INSTRUCTIONS}\n\nAdditional focus:\n{custom_instructions}"
        if custom_instructions
        else _MERGE_SUMMARIES_INSTRUCTIONS
    )

    return await summarize_with_fallback(
        summary_messages, model, api_key, signal, reserve_tokens, max_chunk_tokens,
        context_window, merge_instructions, previous_summary=None,
    )


def prune_history_for_context_share(
    messages: list[dict[str, Any]],
    max_context_tokens: int,
    max_history_share: float = 0.5,
    parts: int = _DEFAULT_PARTS,
) -> dict[str, Any]:
    """
    Drop oldest chunk(s) until message history fits within the token budget.
    Mirrors TS pruneHistoryForContextShare().

    Returns dict with: messages, dropped_messages_list, dropped_chunks,
    dropped_messages, dropped_tokens, kept_tokens, budget_tokens.
    """
    budget_tokens = max(1, int(max_context_tokens * max_history_share))
    kept_messages = list(messages)
    all_dropped: list[dict[str, Any]] = []
    dropped_chunks = 0
    dropped_messages = 0
    dropped_tokens = 0

    normalized_parts = _normalize_parts(parts, len(kept_messages))

    while kept_messages and estimate_messages_tokens(kept_messages) > budget_tokens:
        chunks = split_messages_by_token_share(kept_messages, normalized_parts)
        if len(chunks) <= 1:
            break
        dropped_chunk, *rest = chunks
        flat_rest = [msg for chunk in rest for msg in chunk]

        repair = _repair_tool_use_result_pairing(flat_rest)
        repaired_kept = repair["messages"]
        orphaned_count = repair["dropped_orphan_count"]

        dropped_chunks += 1
        dropped_messages += len(dropped_chunk) + orphaned_count
        dropped_tokens += estimate_messages_tokens(dropped_chunk)
        all_dropped.extend(dropped_chunk)
        kept_messages = repaired_kept

    return {
        "messages": kept_messages,
        "dropped_messages_list": all_dropped,
        "dropped_chunks": dropped_chunks,
        "dropped_messages": dropped_messages,
        "dropped_tokens": dropped_tokens,
        "kept_tokens": estimate_messages_tokens(kept_messages),
        "budget_tokens": budget_tokens,
    }


def resolve_context_window_tokens(model: dict[str, Any] | None = None) -> int:
    """
    Return context window size for a model, defaulting to DEFAULT_CONTEXT_TOKENS.
    Mirrors TS resolveContextWindowTokens().
    """
    from ..defaults import DEFAULT_CONTEXT_TOKENS
    if isinstance(model, dict):
        cw = model.get("contextWindow") or model.get("context_window")
        if isinstance(cw, (int, float)) and cw > 0:
            return max(1, int(cw))
    return DEFAULT_CONTEXT_TOKENS
