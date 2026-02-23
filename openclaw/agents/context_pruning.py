"""
Context pruning extension — fully aligned with TypeScript
openclaw/src/agents/pi-extensions/context-pruning/.

Provides opt-in in-memory context pruning ("microcompact"-style) for agent sessions.
Only affects the in-memory context for the current request; does NOT rewrite
session history persisted on disk.

Modes:
  - "off": No pruning (default)
  - "cache-ttl": Prune tool results older than TTL when context exceeds threshold
"""
from __future__ import annotations

import copy
import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

CHARS_PER_TOKEN_ESTIMATE = 4
IMAGE_CHAR_ESTIMATE = 8_000


# ---------------------------------------------------------------------------
# Settings types
# ---------------------------------------------------------------------------

@dataclass
class ContextPruningToolMatch:
    allow: list[str] | None = None
    deny: list[str] | None = None


@dataclass
class SoftTrimSettings:
    max_chars: int = 4_000
    head_chars: int = 1_500
    tail_chars: int = 1_500


@dataclass
class HardClearSettings:
    enabled: bool = True
    placeholder: str = "[Old tool result content cleared]"


@dataclass
class EffectiveContextPruningSettings:
    mode: str = "cache-ttl"  # "cache-ttl" only (off means no instance created)
    ttl_ms: int = 5 * 60 * 1000  # 5 minutes
    keep_last_assistants: int = 3
    soft_trim_ratio: float = 0.3
    hard_clear_ratio: float = 0.5
    min_prunable_tool_chars: int = 50_000
    tools: ContextPruningToolMatch = field(default_factory=ContextPruningToolMatch)
    soft_trim: SoftTrimSettings = field(default_factory=SoftTrimSettings)
    hard_clear: HardClearSettings = field(default_factory=HardClearSettings)


DEFAULT_CONTEXT_PRUNING_SETTINGS = EffectiveContextPruningSettings()


def _parse_duration_ms(raw: str, default_unit: str = "m") -> int:
    """Parse duration string to milliseconds.

    Supports: 5m, 300s, 1h, 500ms etc.
    """
    raw = raw.strip().lower()
    match = re.match(r"^(\d+(?:\.\d+)?)\s*([a-z]*)$", raw)
    if not match:
        raise ValueError(f"Invalid duration: {raw!r}")
    value = float(match.group(1))
    unit = match.group(2) or default_unit
    multipliers = {"ms": 1, "s": 1000, "m": 60_000, "h": 3_600_000, "d": 86_400_000}
    if unit not in multipliers:
        raise ValueError(f"Unknown duration unit: {unit!r}")
    return int(value * multipliers[unit])


def compute_effective_settings(raw: Any) -> EffectiveContextPruningSettings | None:
    """Compute effective context pruning settings from raw config dict.

    Returns None if mode is "off" or config is invalid.
    Mirrors TS computeEffectiveSettings().
    """
    if not isinstance(raw, dict):
        return None
    mode = raw.get("mode")
    if mode != "cache-ttl":
        return None

    s = copy.deepcopy(DEFAULT_CONTEXT_PRUNING_SETTINGS)
    s.mode = mode

    ttl_raw = raw.get("ttl")
    if isinstance(ttl_raw, str):
        try:
            s.ttl_ms = _parse_duration_ms(ttl_raw, default_unit="m")
        except ValueError:
            pass

    keep_raw = raw.get("keepLastAssistants")
    if isinstance(keep_raw, (int, float)) and keep_raw == keep_raw:
        s.keep_last_assistants = max(0, int(keep_raw))

    for ratio_name, attr in [("softTrimRatio", "soft_trim_ratio"), ("hardClearRatio", "hard_clear_ratio")]:
        val = raw.get(ratio_name)
        if isinstance(val, (int, float)) and val == val:
            setattr(s, attr, min(1.0, max(0.0, float(val))))

    min_chars = raw.get("minPrunableToolChars")
    if isinstance(min_chars, (int, float)):
        s.min_prunable_tool_chars = max(0, int(min_chars))

    tools_raw = raw.get("tools")
    if isinstance(tools_raw, dict):
        allow = tools_raw.get("allow")
        deny = tools_raw.get("deny")
        s.tools = ContextPruningToolMatch(
            allow=list(allow) if isinstance(allow, list) else None,
            deny=list(deny) if isinstance(deny, list) else None,
        )

    soft_trim_raw = raw.get("softTrim")
    if isinstance(soft_trim_raw, dict):
        for key, attr in [("maxChars", "max_chars"), ("headChars", "head_chars"), ("tailChars", "tail_chars")]:
            val = soft_trim_raw.get(key)
            if isinstance(val, (int, float)):
                setattr(s.soft_trim, attr, max(0, int(val)))

    hard_clear_raw = raw.get("hardClear")
    if isinstance(hard_clear_raw, dict):
        if isinstance(hard_clear_raw.get("enabled"), bool):
            s.hard_clear.enabled = hard_clear_raw["enabled"]
        placeholder = hard_clear_raw.get("placeholder")
        if isinstance(placeholder, str) and placeholder.strip():
            s.hard_clear.placeholder = placeholder.strip()

    return s


# ---------------------------------------------------------------------------
# Message estimation
# ---------------------------------------------------------------------------

def _estimate_message_chars(message: dict[str, Any]) -> int:
    """Estimate character count of a message."""
    role = message.get("role", "")
    content = message.get("content", "")

    if role == "user":
        if isinstance(content, str):
            return len(content)
        if isinstance(content, list):
            chars = 0
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    chars += len(block.get("text", ""))
                elif block.get("type") == "image":
                    chars += IMAGE_CHAR_ESTIMATE
            return chars

    if role == "assistant":
        chars = 0
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type", "")
                if btype == "text":
                    chars += len(block.get("text", ""))
                elif btype == "thinking":
                    chars += len(block.get("thinking", ""))
                elif btype == "toolCall":
                    try:
                        import json
                        chars += len(json.dumps(block.get("arguments") or {}))
                    except Exception:
                        chars += 128
        elif isinstance(content, str):
            chars = len(content)
        return chars

    if role == "toolResult":
        chars = 0
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    chars += len(block.get("text", ""))
                elif block.get("type") == "image":
                    chars += IMAGE_CHAR_ESTIMATE
        elif isinstance(content, str):
            chars = len(content)
        return chars

    return 256


def _estimate_context_chars(messages: list[dict[str, Any]]) -> int:
    return sum(_estimate_message_chars(m) for m in messages)


# ---------------------------------------------------------------------------
# Tool match predicate
# ---------------------------------------------------------------------------

def _is_tool_prunable(tool_name: str, tool_match: ContextPruningToolMatch) -> bool:
    """Check if a tool result is eligible for pruning."""
    if tool_match.deny:
        if tool_name in tool_match.deny:
            return False
    if tool_match.allow:
        return tool_name in tool_match.allow
    return True


# ---------------------------------------------------------------------------
# Pruner
# ---------------------------------------------------------------------------


def _get_tool_result_name(message: dict[str, Any]) -> str:
    """Extract tool name from a toolResult message."""
    content = message.get("content", [])
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "toolResult":
                return str(block.get("toolName", "") or block.get("name", "") or "")
    tool_name = message.get("toolName") or message.get("name") or ""
    return str(tool_name)


def _collect_text_segments(content: list[dict[str, Any]]) -> list[str]:
    """Collect text segments from a list of content blocks."""
    return [block["text"] for block in content if isinstance(block, dict) and block.get("type") == "text"]


def _estimate_joined_text_length(parts: list[str]) -> int:
    """Estimate total length when parts are joined with newlines."""
    if not parts:
        return 0
    total = sum(len(p) for p in parts)
    total += max(0, len(parts) - 1)  # "\n" separators
    return total


def _take_head_from_joined_text(parts: list[str], max_chars: int) -> str:
    """Take the head portion across joined text blocks."""
    if max_chars <= 0 or not parts:
        return ""
    remaining = max_chars
    out = ""
    for i, p in enumerate(parts):
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
    """Take the tail portion across joined text blocks."""
    if max_chars <= 0 or not parts:
        return ""
    remaining = max_chars
    out: list[str] = []
    for i in range(len(parts) - 1, -1, -1):
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
    return any(isinstance(b, dict) and b.get("type") == "image" for b in content)


def _soft_trim_tool_result_message(
    msg: dict[str, Any],
    settings: EffectiveContextPruningSettings,
) -> dict[str, Any] | None:
    """
    Perform block-level soft-trim on a toolResult message.
    Returns new message or None if no trim needed.
    Mirrors TS softTrimToolResultMessage().
    """
    content = msg.get("content", [])
    if not isinstance(content, list):
        return None
    if _has_image_blocks(content):
        return None

    parts = _collect_text_segments(content)
    raw_len = _estimate_joined_text_length(parts)
    if raw_len <= settings.soft_trim.max_chars:
        return None

    head_chars = max(0, settings.soft_trim.head_chars)
    tail_chars = max(0, settings.soft_trim.tail_chars)
    if head_chars + tail_chars >= raw_len:
        return None

    head = _take_head_from_joined_text(parts, head_chars)
    tail = _take_tail_from_joined_text(parts, tail_chars)
    trimmed = f"{head}\n...\n{tail}"
    note = (
        f"\n\n[Tool result trimmed: kept first {head_chars} chars and last {tail_chars} chars of {raw_len} chars.]"
    )
    return {**msg, "content": [{"type": "text", "text": trimmed + note}]}


def prune_context_messages(
    messages: list[dict[str, Any]],
    context_tokens: int,
    settings: EffectiveContextPruningSettings,
    current_time_ms: int | None = None,
) -> list[dict[str, Any]]:
    """Prune in-memory context messages to fit within context window.

    Mirrors TS pruneContextMessages() in context-pruning/pruner.ts.

    Protection rules (never prune):
    - Messages before the first user message (bootstrap safety)
    - The last keep_last_assistants assistant messages

    Prunable targets:
    - Tool result text blocks above soft_trim_ratio threshold (soft-trim)
    - Tool result text blocks above hard_clear_ratio threshold (hard-clear)
    """
    if not messages:
        return messages

    if context_tokens <= 0:
        return messages

    char_window = context_tokens * CHARS_PER_TOKEN_ESTIMATE
    if char_window <= 0:
        return messages

    # Bootstrap safety: never prune before first user message
    first_user_idx: int | None = next(
        (i for i, m in enumerate(messages) if m.get("role") == "user"), None
    )
    prune_start_idx = len(messages) if first_user_idx is None else first_user_idx

    # Find cutoff index for protected tail of assistant messages
    if settings.keep_last_assistants <= 0:
        cutoff_idx: int | None = len(messages)
    else:
        cutoff_idx = None
        remaining = settings.keep_last_assistants
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].get("role") == "assistant":
                remaining -= 1
                if remaining == 0:
                    cutoff_idx = i
                    break

    if cutoff_idx is None:
        # Not enough assistant messages — nothing to prune
        return messages

    total_chars = _estimate_context_chars(messages)
    ratio = total_chars / char_window

    # Only prune if ratio >= soft_trim_ratio (TS: if ratio < threshold, return unchanged)
    if ratio < settings.soft_trim_ratio:
        return messages

    prunable_tool_indexes: list[int] = []
    next_msgs: list[dict[str, Any]] | None = None

    # Pass 1: soft-trim prunable tool results
    for i in range(prune_start_idx, cutoff_idx):
        msg = messages[i]
        if msg.get("role") != "toolResult":
            continue
        content = msg.get("content", [])
        if not isinstance(content, list):
            continue
        if _has_image_blocks(content):
            continue
        tool_name = _get_tool_result_name(msg)
        if not _is_tool_prunable(tool_name, settings.tools):
            continue
        prunable_tool_indexes.append(i)

        updated = _soft_trim_tool_result_message(msg, settings)
        if updated is None:
            continue

        before_chars = _estimate_message_chars(msg)
        after_chars = _estimate_message_chars(updated)
        total_chars += after_chars - before_chars
        if next_msgs is None:
            next_msgs = list(messages)
        next_msgs[i] = updated

    output_after_soft_trim = next_msgs if next_msgs is not None else messages
    ratio = total_chars / char_window

    if ratio < settings.hard_clear_ratio:
        return output_after_soft_trim
    if not settings.hard_clear.enabled:
        return output_after_soft_trim

    # Check if prunable tool chars meet minimum threshold
    prunable_tool_chars = 0
    for i in prunable_tool_indexes:
        msg = output_after_soft_trim[i]
        if msg.get("role") == "toolResult":
            prunable_tool_chars += _estimate_message_chars(msg)
    if prunable_tool_chars < settings.min_prunable_tool_chars:
        return output_after_soft_trim

    # Pass 2: hard-clear prunable tool results until ratio falls below hard_clear_ratio
    for i in prunable_tool_indexes:
        if ratio < settings.hard_clear_ratio:
            break
        src = next_msgs if next_msgs is not None else messages
        msg = src[i]
        if msg.get("role") != "toolResult":
            continue
        before_chars = _estimate_message_chars(msg)
        cleared = {**msg, "content": [{"type": "text", "text": settings.hard_clear.placeholder}]}
        if next_msgs is None:
            next_msgs = list(messages)
        next_msgs[i] = cleared
        after_chars = _estimate_message_chars(cleared)
        total_chars += after_chars - before_chars
        ratio = total_chars / char_window

    return next_msgs if next_msgs is not None else messages


# ---------------------------------------------------------------------------
# High-level integration helper
# ---------------------------------------------------------------------------

def apply_context_pruning(
    messages: list[dict[str, Any]],
    context_tokens: int,
    pruning_config: Any,
    last_cache_touch_ms: int | None = None,
) -> tuple[list[dict[str, Any]], int | None]:
    """Apply context pruning to a message list if configured.

    Mirrors the TS `context` event handler in extension.ts.

    pruning_config: dict with "mode", "ttl", etc. or None (no pruning).
    last_cache_touch_ms: timestamp of last cache touch (for cache-ttl mode).

    Returns (messages, new_last_cache_touch_ms).
    In cache-ttl mode, pruning is skipped until TTL has elapsed since the last touch.
    """
    import time as _time

    if not pruning_config:
        return messages, last_cache_touch_ms

    settings = compute_effective_settings(
        pruning_config if isinstance(pruning_config, dict) else {}
    )
    if settings is None:
        return messages, last_cache_touch_ms

    if settings.mode == "cache-ttl":
        ttl_ms = settings.ttl_ms
        if not last_cache_touch_ms or ttl_ms <= 0:
            return messages, last_cache_touch_ms
        if _time.time() * 1000 - last_cache_touch_ms < ttl_ms:
            return messages, last_cache_touch_ms

    pruned = prune_context_messages(messages, context_tokens, settings)

    if pruned is messages:
        return messages, last_cache_touch_ms

    new_touch = int(_time.time() * 1000) if settings.mode == "cache-ttl" else last_cache_touch_ms
    return pruned, new_touch
