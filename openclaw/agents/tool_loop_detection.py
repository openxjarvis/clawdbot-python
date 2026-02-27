"""
Tool Loop Detection - mirrors TypeScript tool-loop-detection.ts

Detects when agents get stuck in repetitive tool call patterns and provides
warnings or blocks execution to prevent infinite loops.
"""
from __future__ import annotations

import hashlib
import json
import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Constants aligned with TS
TOOL_CALL_HISTORY_SIZE = 30
WARNING_THRESHOLD = 10
CRITICAL_THRESHOLD = 20
GLOBAL_CIRCUIT_BREAKER_THRESHOLD = 30


@dataclass
class LoopDetectionResult:
    """Result from loop detection analysis."""
    stuck: bool
    level: str | None = None  # "warning" | "critical"
    detector: str | None = None
    count: int = 0
    message: str | None = None
    paired_tool_name: str | None = None
    warning_key: str | None = None


@dataclass
class ToolCallRecord:
    """Single tool call record in history."""
    tool_name: str
    hash: str
    timestamp: int  # Unix ms
    result_hash: str | None = None
    outcome: str | None = None  # "success" | "error" | "pending"


@dataclass
class SessionState:
    """Session state for tool loop detection."""
    tool_call_history: deque[ToolCallRecord] = field(default_factory=lambda: deque(maxlen=TOOL_CALL_HISTORY_SIZE))
    shown_warnings: set[str] = field(default_factory=set)


def hash_tool_call(tool_name: str, params: Any) -> str:
    """
    Hash a tool call based on tool name and parameters.
    
    Mirrors TypeScript hashToolCall().
    
    Args:
        tool_name: Name of the tool
        params: Tool parameters
        
    Returns:
        SHA256 hash of tool call
    """
    # Normalize params to JSON string for consistent hashing
    try:
        if isinstance(params, dict):
            # Sort keys for consistent ordering
            param_str = json.dumps(params, sort_keys=True)
        elif isinstance(params, str):
            param_str = params
        else:
            param_str = json.dumps(params)
    except Exception:
        param_str = str(params)
    
    combined = f"{tool_name}::{param_str}"
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()


def hash_tool_result(result: Any) -> str:
    """
    Hash a tool call result for comparison.
    
    Args:
        result: Tool result to hash
        
    Returns:
        SHA256 hash of result
    """
    try:
        if isinstance(result, dict):
            result_str = json.dumps(result, sort_keys=True)
        elif isinstance(result, str):
            result_str = result
        else:
            result_str = json.dumps(result)
    except Exception:
        result_str = str(result)
    
    return hashlib.sha256(result_str.encode('utf-8')).hexdigest()


def _get_time_ms() -> int:
    """Get current time in milliseconds."""
    import time
    return int(time.time() * 1000)


def detect_tool_call_loop(
    state: SessionState,
    tool_name: str,
    params: Any,
    config: dict[str, Any] | None = None,
) -> LoopDetectionResult:
    """
    Detect if agent is stuck in a tool call loop.
    
    Mirrors TypeScript detectToolCallLoop().
    
    Checks for:
    1. Generic Repeat: Same tool + params repeated
    2. Known Poll No Progress: Polling tools with no progress
    3. Ping Pong: Two tools alternating with no progress
    4. Global Circuit Breaker: Too many total calls
    
    Args:
        state: Session state with tool call history
        tool_name: Current tool name
        params: Current tool parameters
        config: Optional configuration dict
        
    Returns:
        LoopDetectionResult with detection info
    """
    if not state or not state.tool_call_history:
        return LoopDetectionResult(stuck=False)
    
    history = list(state.tool_call_history)
    current_hash = hash_tool_call(tool_name, params)
    
    # Get thresholds from config (with defaults)
    warning_threshold = config.get("warningThreshold", WARNING_THRESHOLD) if config else WARNING_THRESHOLD
    critical_threshold = config.get("criticalThreshold", CRITICAL_THRESHOLD) if config else CRITICAL_THRESHOLD
    global_threshold = config.get("globalThreshold", GLOBAL_CIRCUIT_BREAKER_THRESHOLD) if config else GLOBAL_CIRCUIT_BREAKER_THRESHOLD
    
    # Detector 1: Generic Repeat
    # Count exact matches (tool + params)
    exact_matches = [rec for rec in history if rec.hash == current_hash]
    exact_count = len(exact_matches)
    
    if exact_count >= critical_threshold:
        warning_key = f"generic_repeat_critical_{tool_name}_{current_hash[:8]}"
        if warning_key not in state.shown_warnings:
            return LoopDetectionResult(
                stuck=True,
                level="critical",
                detector="generic_repeat",
                count=exact_count,
                message=f"Agent is stuck: {tool_name} called {exact_count} times with identical parameters",
                warning_key=warning_key,
            )
    
    if exact_count >= warning_threshold:
        warning_key = f"generic_repeat_warning_{tool_name}_{current_hash[:8]}"
        if warning_key not in state.shown_warnings:
            return LoopDetectionResult(
                stuck=True,
                level="warning",
                detector="generic_repeat",
                count=exact_count,
                message=f"Potential loop: {tool_name} called {exact_count} times with identical parameters",
                warning_key=warning_key,
            )
    
    # Detector 2: Known Poll No Progress
    # Check if this is a polling tool (Read, Shell with monitoring patterns)
    known_poll_tools = ["Read", "Shell", "Glob", "ReadTerminal"]
    
    if tool_name in known_poll_tools:
        # Check for repeated calls with same hash but no result changes
        same_tool_recent = [rec for rec in history[-20:] if rec.tool_name == tool_name]
        
        if len(same_tool_recent) >= warning_threshold:
            # Check if results are unchanged
            result_hashes = [rec.result_hash for rec in same_tool_recent if rec.result_hash]
            if len(set(result_hashes)) <= 2 and len(result_hashes) >= warning_threshold:
                warning_key = f"known_poll_{tool_name}_{current_hash[:8]}"
                if warning_key not in state.shown_warnings:
                    level = "critical" if len(same_tool_recent) >= critical_threshold else "warning"
                    return LoopDetectionResult(
                        stuck=True,
                        level=level,
                        detector="known_poll_no_progress",
                        count=len(same_tool_recent),
                        message=f"Polling loop detected: {tool_name} called {len(same_tool_recent)} times with no progress",
                        warning_key=warning_key,
                    )
    
    # Detector 3: Ping Pong
    # Check for alternating pattern between two tools
    if len(history) >= 6:
        last_6 = history[-6:]
        
        # Extract tool names
        tool_names = [rec.tool_name for rec in last_6]
        
        # Check if alternating between 2 tools
        unique_tools = list(set(tool_names))
        if len(unique_tools) == 2:
            tool_a, tool_b = unique_tools
            
            # Check if pattern is alternating (A, B, A, B, A, B)
            is_alternating = True
            expected_tool = tool_a if tool_names[0] == tool_a else tool_b
            
            for i, actual_tool in enumerate(tool_names):
                if actual_tool != expected_tool:
                    is_alternating = False
                    break
                expected_tool = tool_b if expected_tool == tool_a else tool_a
            
            if is_alternating:
                # Check if results are not changing
                result_hashes = [rec.result_hash for rec in last_6 if rec.result_hash]
                unique_results = len(set(result_hashes))
                
                if unique_results <= 2 and len(result_hashes) >= 4:
                    warning_key = f"ping_pong_{min(tool_a, tool_b)}_{max(tool_a, tool_b)}"
                    if warning_key not in state.shown_warnings:
                        return LoopDetectionResult(
                            stuck=True,
                            level="warning",
                            detector="ping_pong",
                            count=len(last_6),
                            message=f"Ping-pong loop detected: alternating between {tool_a} and {tool_b} with no progress",
                            paired_tool_name=tool_b if tool_name == tool_a else tool_a,
                            warning_key=warning_key,
                        )
    
    # Detector 4: Global Circuit Breaker
    # Total calls in recent history exceeds threshold
    if len(history) >= global_threshold:
        warning_key = "global_circuit_breaker"
        if warning_key not in state.shown_warnings:
            return LoopDetectionResult(
                stuck=True,
                level="critical",
                detector="global_circuit_breaker",
                count=len(history),
                message=f"Global circuit breaker: {len(history)} tool calls in recent history",
                warning_key=warning_key,
            )
    
    return LoopDetectionResult(stuck=False)


def record_tool_call(
    state: SessionState,
    tool_name: str,
    params: Any,
) -> None:
    """
    Record a tool call in session history.
    
    Args:
        state: Session state
        tool_name: Tool name
        params: Tool parameters
    """
    if not state:
        return
    
    call_hash = hash_tool_call(tool_name, params)
    
    record = ToolCallRecord(
        tool_name=tool_name,
        hash=call_hash,
        timestamp=_get_time_ms(),
        outcome="pending",
    )
    
    state.tool_call_history.append(record)


def record_tool_call_outcome(
    state: SessionState,
    tool_name: str,
    result: Any,
    outcome: str = "success",
) -> None:
    """
    Record the outcome of a tool call.
    
    Args:
        state: Session state
        tool_name: Tool name
        result: Tool result
        outcome: Outcome type ("success" | "error")
    """
    if not state or not state.tool_call_history:
        return
    
    # Find the most recent pending call for this tool
    for record in reversed(state.tool_call_history):
        if record.tool_name == tool_name and record.outcome == "pending":
            record.outcome = outcome
            record.result_hash = hash_tool_result(result)
            break


def mark_warning_shown(state: SessionState, warning_key: str) -> None:
    """
    Mark a warning as shown to prevent duplicate warnings.
    
    Args:
        state: Session state
        warning_key: Unique warning identifier
    """
    if state:
        state.shown_warnings.add(warning_key)


def reset_tool_loop_detection(state: SessionState) -> None:
    """
    Reset tool loop detection state.
    
    Args:
        state: Session state to reset
    """
    if state:
        state.tool_call_history.clear()
        state.shown_warnings.clear()
