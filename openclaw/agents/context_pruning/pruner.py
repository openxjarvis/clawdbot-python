"""
Context pruning module - mirrors TypeScript context-pruning/pruner.ts.

Provides soft trimming and hard clearing of tool results to save context tokens.
"""
from __future__ import annotations

from typing import Any

CHARS_PER_TOKEN_ESTIMATE = 4
IMAGE_CHAR_ESTIMATE = 8_000


def _as_text(text: str) -> dict[str, Any]:
    """Create a text content block."""
    return {"type": "text", "text": text}


def _collect_text_segments(content: list[dict[str, Any]]) -> list[str]:
    """Collect all text segments from content blocks."""
    parts: list[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text", "")
            if isinstance(text, str):
                parts.append(text)
    return parts


def _estimate_joined_text_length(parts: list[str]) -> int:
    """Estimate total length of text parts joined with newlines."""
    if not parts:
        return 0
    total_len = sum(len(p) for p in parts)
    total_len += max(0, len(parts) - 1)
    return total_len


def _take_head_from_joined_text(parts: list[str], max_chars: int) -> str:
    """Take first max_chars from joined text parts."""
    if max_chars <= 0 or not parts:
        return ""
    
    remaining = max_chars
    out = ""
    
    for i, p in enumerate(parts):
        if remaining <= 0:
            break
        
        if i > 0:
            out += "\n"
            remaining -= 1
            if remaining <= 0:
                break
        
        if len(p) <= remaining:
            out += p
            remaining -= len(p)
        else:
            out += p[:remaining]
            remaining = 0
    
    return out


def _take_tail_from_joined_text(parts: list[str], max_chars: int) -> str:
    """Take last max_chars from joined text parts."""
    if max_chars <= 0 or not parts:
        return ""
    
    remaining = max_chars
    out: list[str] = []
    
    for i in range(len(parts) - 1, -1, -1):
        if remaining <= 0:
            break
        
        p = parts[i]
        if len(p) <= remaining:
            out.append(p)
            remaining -= len(p)
        else:
            out.append(p[len(p) - remaining:])
            remaining = 0
            break
        
        if remaining > 0 and i > 0:
            out.append("\n")
            remaining -= 1
    
    out.reverse()
    return "".join(out)


def _has_image_blocks(content: list[dict[str, Any]]) -> bool:
    """Check if content contains any image blocks."""
    for block in content:
        if isinstance(block, dict) and block.get("type") == "image":
            return True
    return False


def estimate_message_chars(message: dict[str, Any]) -> int:
    """
    Estimate character count for a message.
    Mirrors TS estimateMessageChars().
    """
    role = message.get("role", "")
    
    if role == "user":
        content = message.get("content", "")
        if isinstance(content, str):
            return len(content)
        
        if isinstance(content, list):
            chars = 0
            for b in content:
                if isinstance(b, dict):
                    if b.get("type") == "text":
                        chars += len(b.get("text", ""))
                    elif b.get("type") == "image":
                        chars += IMAGE_CHAR_ESTIMATE
            return chars
        return 0
    
    if role == "assistant":
        content = message.get("content", [])
        if not isinstance(content, list):
            return 0
        
        chars = 0
        for b in content:
            if not isinstance(b, dict):
                continue
            
            if b.get("type") == "text":
                chars += len(b.get("text", ""))
            elif b.get("type") == "thinking":
                chars += len(b.get("thinking", ""))
            elif b.get("type") == "toolCall":
                try:
                    import json
                    chars += len(json.dumps(b.get("arguments", {})))
                except Exception:
                    chars += 128
        
        return chars
    
    if role == "toolResult":
        content = message.get("content", [])
        if not isinstance(content, list):
            return 0
        
        chars = 0
        for b in content:
            if not isinstance(b, dict):
                continue
            
            if b.get("type") == "text":
                chars += len(b.get("text", ""))
            elif b.get("type") == "image":
                chars += IMAGE_CHAR_ESTIMATE
        
        return chars
    
    return 256


def _estimate_context_chars(messages: list[dict[str, Any]]) -> int:
    """Estimate total character count for all messages."""
    return sum(estimate_message_chars(m) for m in messages)


def find_assistant_cutoff_index(
    messages: list[dict[str, Any]],
    keep_last_assistants: int,
) -> int | None:
    """
    Find the index before which messages can be pruned.
    Protects the last N assistant messages.
    Mirrors TS findAssistantCutoffIndex().
    """
    if keep_last_assistants <= 0:
        return len(messages)
    
    remaining = keep_last_assistants
    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        if not isinstance(msg, dict):
            continue
        
        if msg.get("role") == "assistant":
            remaining -= 1
            if remaining == 0:
                return i
    
    return None


def _find_first_user_index(messages: list[dict[str, Any]]) -> int | None:
    """Find the index of the first user message."""
    for i, msg in enumerate(messages):
        if isinstance(msg, dict) and msg.get("role") == "user":
            return i
    return None


def soft_trim_tool_result_message(
    msg: dict[str, Any],
    settings: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Soft-trim a tool result message by keeping head + tail.
    Returns trimmed message or None if no trimming needed.
    Mirrors TS softTrimToolResultMessage().
    """
    if msg.get("role") != "toolResult":
        return None
    
    content = msg.get("content", [])
    if not isinstance(content, list):
        return None
    
    if _has_image_blocks(content):
        return None
    
    soft_trim = settings.get("softTrim", {})
    max_chars = soft_trim.get("maxChars", 8000)
    head_chars = soft_trim.get("headChars", 2000)
    tail_chars = soft_trim.get("tailChars", 2000)
    
    parts = _collect_text_segments(content)
    raw_len = _estimate_joined_text_length(parts)
    
    if raw_len <= max_chars:
        return None
    
    head_chars = max(0, head_chars)
    tail_chars = max(0, tail_chars)
    
    if head_chars + tail_chars >= raw_len:
        return None
    
    head = _take_head_from_joined_text(parts, head_chars)
    tail = _take_tail_from_joined_text(parts, tail_chars)
    trimmed = f"{head}\n...\n{tail}"
    
    note = f"\n\n[Tool result trimmed: kept first {head_chars} chars and last {tail_chars} chars of {raw_len} chars.]"
    
    return {**msg, "content": [_as_text(trimmed + note)]}


def _make_tool_prunable_predicate(tools_config: dict[str, Any]) -> callable:
    """
    Create a predicate function to check if a tool is prunable.
    Mirrors TS makeToolPrunablePredicate().
    """
    prunable_list = tools_config.get("prunable", [])
    if not isinstance(prunable_list, list):
        prunable_list = []
    
    prunable_set = set(prunable_list)
    
    def is_prunable(tool_name: str) -> bool:
        return tool_name in prunable_set
    
    return is_prunable


def prune_context_messages(
    messages: list[dict[str, Any]],
    settings: dict[str, Any],
    ctx: dict[str, Any],
    is_tool_prunable: callable | None = None,
    context_window_tokens_override: int | None = None,
    last_cache_touch_at: int | None = None,
) -> list[dict[str, Any]]:
    """
    Prune context messages by soft-trimming and hard-clearing tool results.
    Mirrors TS pruneContextMessages().
    
    Args:
        messages: List of messages to prune
        settings: Pruning settings dict
        ctx: Context dict with model info
        is_tool_prunable: Optional predicate to check if tool is prunable
        context_window_tokens_override: Optional override for context window
        last_cache_touch_at: Last cache touch timestamp for TTL mode
    
    Returns:
        Pruned list of messages
    """
    # Check cache-ttl mode first (skip pruning if TTL not expired)
    mode = settings.get('mode', 'off')
    if mode == 'cache-ttl':
        ttl_str = settings.get('ttl', '5m')
        
        # Parse TTL duration
        from ...utils.duration import parse_duration_ms
        try:
            ttl_ms = parse_duration_ms(ttl_str, default_unit='m')
        except Exception:
            ttl_ms = 5 * 60 * 1000  # Default 5 minutes
        
        # If no last cache touch or TTL <= 0, skip pruning
        if not last_cache_touch_at or ttl_ms <= 0:
            return messages
        
        # Check if TTL has expired
        import time
        elapsed = int(time.time() * 1000) - last_cache_touch_at
        if elapsed < ttl_ms:
            # TTL not expired, skip pruning
            return messages
    
    model = ctx.get("model", {})
    
    if context_window_tokens_override is not None and context_window_tokens_override > 0:
        context_window_tokens = context_window_tokens_override
    else:
        context_window_tokens = model.get("contextWindow", 0)
    
    if not context_window_tokens or context_window_tokens <= 0:
        return messages
    
    char_window = context_window_tokens * CHARS_PER_TOKEN_ESTIMATE
    if char_window <= 0:
        return messages
    
    keep_last_assistants = settings.get("keepLastAssistants", 2)
    cutoff_index = find_assistant_cutoff_index(messages, keep_last_assistants)
    
    if cutoff_index is None:
        return messages
    
    first_user_index = _find_first_user_index(messages)
    prune_start_index = len(messages) if first_user_index is None else first_user_index
    
    if is_tool_prunable is None:
        tools_config = settings.get("tools", {})
        is_tool_prunable = _make_tool_prunable_predicate(tools_config)
    
    total_chars_before = _estimate_context_chars(messages)
    total_chars = total_chars_before
    
    soft_trim_ratio = settings.get("softTrimRatio", 0.8)
    ratio = total_chars / char_window
    
    if ratio < soft_trim_ratio:
        return messages
    
    prunable_tool_indexes: list[int] = []
    next_messages: list[dict[str, Any]] | None = None
    
    for i in range(prune_start_index, cutoff_index):
        if i >= len(messages):
            break
        
        msg = messages[i]
        if not isinstance(msg, dict):
            continue
        
        if msg.get("role") != "toolResult":
            continue
        
        tool_name = msg.get("toolName", "")
        if not is_tool_prunable(tool_name):
            continue
        
        content = msg.get("content", [])
        if isinstance(content, list) and _has_image_blocks(content):
            continue
        
        prunable_tool_indexes.append(i)
        
        updated = soft_trim_tool_result_message(msg, settings)
        if not updated:
            continue
        
        before_chars = estimate_message_chars(msg)
        after_chars = estimate_message_chars(updated)
        total_chars += after_chars - before_chars
        
        if next_messages is None:
            next_messages = messages[:]
        
        next_messages[i] = updated
    
    output_after_soft_trim = next_messages if next_messages else messages
    ratio = total_chars / char_window
    
    hard_clear_ratio = settings.get("hardClearRatio", 0.95)
    if ratio < hard_clear_ratio:
        return output_after_soft_trim
    
    hard_clear = settings.get("hardClear", {})
    if not hard_clear.get("enabled", True):
        return output_after_soft_trim
    
    prunable_tool_chars = 0
    for i in prunable_tool_indexes:
        if i >= len(output_after_soft_trim):
            continue
        msg = output_after_soft_trim[i]
        if not isinstance(msg, dict) or msg.get("role") != "toolResult":
            continue
        prunable_tool_chars += estimate_message_chars(msg)
    
    min_prunable_tool_chars = settings.get("minPrunableToolChars", 1000)
    if prunable_tool_chars < min_prunable_tool_chars:
        return output_after_soft_trim
    
    placeholder = hard_clear.get("placeholder", "[Tool result cleared to save context]")
    
    for i in prunable_tool_indexes:
        if ratio < hard_clear_ratio:
            break
        
        if i >= len(output_after_soft_trim):
            continue
        
        msg = (next_messages if next_messages else messages)[i]
        if not isinstance(msg, dict) or msg.get("role") != "toolResult":
            continue
        
        before_chars = estimate_message_chars(msg)
        cleared = {**msg, "content": [_as_text(placeholder)]}
        
        if next_messages is None:
            next_messages = messages[:]
        
        next_messages[i] = cleared
        after_chars = estimate_message_chars(cleared)
        total_chars += after_chars - before_chars
        ratio = total_chars / char_window
    
    return next_messages if next_messages else messages
