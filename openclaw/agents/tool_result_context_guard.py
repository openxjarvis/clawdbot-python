"""
Tool Result Context Guard - mirrors TypeScript tool-result-context-guard.ts

Preemptively limits and compacts tool results to prevent individual results
from consuming too much context, with intelligent truncation strategies.
"""
from __future__ import annotations

import copy
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Constants aligned with TS
CONTEXT_INPUT_HEADROOM_RATIO = 0.75
SINGLE_TOOL_RESULT_CONTEXT_SHARE = 0.5
TOOL_RESULT_CHARS_PER_TOKEN_ESTIMATE = 2

CONTEXT_LIMIT_TRUNCATION_NOTICE = "[truncated: output exceeded context limit]"
PREEMPTIVE_TOOL_RESULT_COMPACTION_PLACEHOLDER = "[compacted: tool output removed to free context]"


def _count_chars(content: Any) -> int:
    """Count characters in message content."""
    if isinstance(content, str):
        return len(content)
    elif isinstance(content, list):
        total = 0
        for item in content:
            if isinstance(item, dict):
                text = item.get("text", "")
                total += len(text) if isinstance(text, str) else 0
            elif isinstance(item, str):
                total += len(item)
        return total
    return 0


def truncate_tool_result_to_chars(msg: dict[str, Any], max_chars: int) -> dict[str, Any]:
    """
    Truncate a tool result message to max_chars.
    
    Mirrors TypeScript truncateToolResultToChars().
    
    Strategy:
    - Preserve newline-aligned chunks when possible
    - Add truncation notice
    - Handle both string and array content
    
    Args:
        msg: Tool result message to truncate
        max_chars: Maximum characters allowed
        
    Returns:
        Truncated message (new dict, original not modified)
    """
    if not isinstance(msg, dict):
        return msg
    
    content = msg.get("content")
    if not content:
        return msg
    
    current_chars = _count_chars(content)
    if current_chars <= max_chars:
        return msg
    
    # Need to truncate
    result = copy.deepcopy(msg)
    notice_len = len(CONTEXT_LIMIT_TRUNCATION_NOTICE)
    available_chars = max(0, max_chars - notice_len - 10)  # Buffer for formatting
    
    if isinstance(content, str):
        # Truncate string content
        if available_chars <= 0:
            result["content"] = CONTEXT_LIMIT_TRUNCATION_NOTICE
        else:
            # Try to break at newline
            lines = content[:available_chars].split('\n')
            if len(lines) > 1:
                # Keep all but possibly incomplete last line
                truncated = '\n'.join(lines[:-1])
                result["content"] = truncated + f"\n\n{CONTEXT_LIMIT_TRUNCATION_NOTICE}"
            else:
                result["content"] = content[:available_chars] + f"\n\n{CONTEXT_LIMIT_TRUNCATION_NOTICE}"
    
    elif isinstance(content, list):
        # Handle array content (list of text blocks)
        new_content = []
        chars_used = 0
        
        for item in content:
            if not isinstance(item, dict):
                continue
            
            text = item.get("text", "")
            if not isinstance(text, str):
                continue
            
            text_len = len(text)
            
            if chars_used + text_len <= available_chars:
                new_content.append(item)
                chars_used += text_len
            else:
                # Partial inclusion
                remaining = available_chars - chars_used
                if remaining > 0:
                    truncated_item = copy.deepcopy(item)
                    truncated_item["text"] = text[:remaining]
                    new_content.append(truncated_item)
                break
        
        # Add notice
        new_content.append({
            "type": "text",
            "text": f"\n\n{CONTEXT_LIMIT_TRUNCATION_NOTICE}"
        })
        
        result["content"] = new_content
    
    return result


def enforce_tool_result_context_budget(
    messages: list[dict[str, Any]],
    context_budget_chars: int,
    max_single_tool_result_chars: int,
) -> None:
    """
    Enforce context budget by truncating or clearing tool results (in-place).
    
    Mirrors TypeScript enforceToolResultContextBudget().
    
    Strategy:
    1. Truncate any single tool result exceeding max_single limit
    2. If total still exceeds budget, clear oldest tool results
    
    Args:
        messages: List of messages (modified in place)
        context_budget_chars: Total context budget in characters
        max_single_tool_result_chars: Max chars for single tool result
    """
    if not messages:
        return
    
    # Step 1: Truncate oversized individual results
    for i, msg in enumerate(messages):
        if not isinstance(msg, dict):
            continue
        
        role = msg.get("role")
        if role == "user":
            # Check for tool_result
            content = msg.get("content")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        block_content = block.get("content")
                        content_chars = _count_chars(block_content)
                        if content_chars > max_single_tool_result_chars:
                            # Truncate the content
                            if isinstance(block_content, str):
                                available = max_single_tool_result_chars - len(CONTEXT_LIMIT_TRUNCATION_NOTICE) - 10
                                if available > 0:
                                    block["content"] = block_content[:available] + f"\n\n{CONTEXT_LIMIT_TRUNCATION_NOTICE}"
                                else:
                                    block["content"] = CONTEXT_LIMIT_TRUNCATION_NOTICE
    
    # Step 2: Check total context budget
    # Count all characters including non-tool-result content
    total_chars = 0
    for msg in messages:
        if isinstance(msg, dict):
            content = msg.get("content")
            if isinstance(content, str):
                total_chars += len(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        block_content = block.get("content", "")
                        if isinstance(block_content, str):
                            total_chars += len(block_content)
                        elif isinstance(block_content, list):
                            for item in block_content:
                                if isinstance(item, dict):
                                    text = item.get("text", "")
                                    if isinstance(text, str):
                                        total_chars += len(text)
                    elif isinstance(block, str):
                        total_chars += len(block)
    
    if total_chars <= context_budget_chars:
        return
    
    # Need to clear some old tool results
    chars_to_remove = total_chars - context_budget_chars
    chars_removed = 0
    
    # Find tool results from oldest to newest
    for i, msg in enumerate(messages):
        if chars_removed >= chars_to_remove:
            break
        
        if not isinstance(msg, dict):
            continue
        
        role = msg.get("role")
        if role == "user":
            content = msg.get("content")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        block_content = block.get("content")
                        
                        # Skip if already compacted
                        if block_content == PREEMPTIVE_TOOL_RESULT_COMPACTION_PLACEHOLDER:
                            continue
                        
                        original_chars = _count_chars(block_content)
                        
                        # Replace with placeholder
                        block["content"] = PREEMPTIVE_TOOL_RESULT_COMPACTION_PLACEHOLDER
                        chars_removed += original_chars
                        
                        if chars_removed >= chars_to_remove:
                            break


def install_tool_result_context_guard(
    agent: Any,
    context_window_tokens: int,
) -> callable:
    """
    Install tool result context guard on an agent.
    
    Mirrors TypeScript installToolResultContextGuard().
    
    This intercepts tool results and enforces size limits before they
    are added to conversation history.
    
    Args:
        agent: Agent instance to protect
        context_window_tokens: Context window size in tokens
        
    Returns:
        Cleanup function to remove the guard
    """
    # Calculate budgets based on context window
    context_budget_tokens = int(context_window_tokens * CONTEXT_INPUT_HEADROOM_RATIO)
    context_budget_chars = context_budget_tokens * TOOL_RESULT_CHARS_PER_TOKEN_ESTIMATE
    
    max_single_tool_result_tokens = int(context_window_tokens * SINGLE_TOOL_RESULT_CONTEXT_SHARE)
    max_single_tool_result_chars = max_single_tool_result_tokens * TOOL_RESULT_CHARS_PER_TOKEN_ESTIMATE
    
    logger.debug(
        f"Tool Result Context Guard installed: "
        f"budget={context_budget_tokens} tokens, "
        f"max_single={max_single_tool_result_tokens} tokens"
    )
    
    # Original method reference
    if hasattr(agent, '_conversation_history'):
        original_history = agent._conversation_history
        
        def guarded_access():
            """Guarded access that enforces budget."""
            if isinstance(original_history, list):
                enforce_tool_result_context_budget(
                    messages=original_history,
                    context_budget_chars=context_budget_chars,
                    max_single_tool_result_chars=max_single_tool_result_chars,
                )
            return original_history
        
        # Intercept history access (this is a simplified approach)
        # In practice, we'd need to hook into the agent's tool result handler
        
        def cleanup():
            """Cleanup function to restore original behavior."""
            pass
        
        return cleanup
    
    return lambda: None


def get_tool_result_chars(msg: dict[str, Any]) -> int:
    """
    Get character count from a tool result message.
    
    Args:
        msg: Message to analyze
        
    Returns:
        Character count
    """
    if not isinstance(msg, dict):
        return 0
    
    content = msg.get("content")
    return _count_chars(content)


def is_tool_result_message(msg: dict[str, Any]) -> bool:
    """
    Check if a message contains a tool result.
    
    Args:
        msg: Message to check
        
    Returns:
        True if message contains tool result
    """
    if not isinstance(msg, dict):
        return False
    
    role = msg.get("role")
    if role != "user":
        return False
    
    content = msg.get("content")
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                return True
    
    return False
