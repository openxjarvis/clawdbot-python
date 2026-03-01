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
    # Bucket-throttled warning deduplication — mirrors TS toolLoopWarningBuckets Map
    warning_buckets: dict[str, int] = field(default_factory=dict)


def _stable_stringify(value: Any) -> str:
    """Deterministic JSON serialization (sorted keys). Mirrors TS stableStringify()."""
    if value is None or not isinstance(value, (dict, list)):
        try:
            return json.dumps(value)
        except Exception:
            return str(value)
    if isinstance(value, list):
        return "[" + ",".join(_stable_stringify(v) for v in value) + "]"
    keys = sorted(value.keys())
    return "{" + ",".join(f"{json.dumps(k)}:{_stable_stringify(value[k])}" for k in keys) + "}"


def _digest_stable(value: Any) -> str:
    """SHA-256 of stable-stringified value. Mirrors TS digestStable()."""
    try:
        serialized = _stable_stringify(value)
    except Exception:
        serialized = str(value)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def hash_tool_call(tool_name: str, params: Any) -> str:
    """Hash a tool call for pattern matching.

    Mirrors TS hashToolCall() — uses tool name + deterministic JSON digest of params.
    """
    return f"{tool_name}:{_digest_stable(params)}"


def _is_known_poll_tool_call(tool_name: str, params: Any) -> bool:
    """Return True if this is a known polling tool call.

    Mirrors TS isKnownPollToolCall():
    - command_status (any params)
    - process with action="poll" or action="log"
    """
    if tool_name == "command_status":
        return True
    if tool_name == "process" and isinstance(params, dict):
        action = params.get("action")
        return action in ("poll", "log")
    return False


def _extract_text_content(result: Any) -> str:
    """Extract text content from tool result. Mirrors TS extractTextContent()."""
    if not isinstance(result, dict) or not isinstance(result.get("content"), list):
        return ""
    parts = []
    for entry in result["content"]:
        if isinstance(entry, dict) and isinstance(entry.get("type"), str) and isinstance(entry.get("text"), str):
            parts.append(entry["text"])
    return "\n".join(parts).strip()


def hash_tool_outcome(tool_name: str, params: Any, result: Any, error: Any = None) -> str | None:
    """Hash tool outcome for no-progress detection.

    Mirrors TS hashToolOutcome() — accounts for process poll/log action details.
    Returns None when outcome can't be meaningfully hashed.
    """
    if error is not None:
        error_str = error.args[0] if isinstance(error, Exception) and error.args else str(error)
        return f"error:{_digest_stable(error_str)}"

    if not isinstance(result, dict):
        return _digest_stable(result) if result is not None else None

    details = result.get("details") or {}
    if not isinstance(details, dict):
        details = {}
    text = _extract_text_content(result)

    if _is_known_poll_tool_call(tool_name, params) and tool_name == "process" and isinstance(params, dict):
        action = params.get("action")
        if action == "poll":
            return _digest_stable({
                "action": action,
                "status": details.get("status"),
                "exitCode": details.get("exitCode"),
                "exitSignal": details.get("exitSignal"),
                "aggregated": details.get("aggregated"),
                "text": text,
            })
        if action == "log":
            return _digest_stable({
                "action": action,
                "status": details.get("status"),
                "totalLines": details.get("totalLines"),
                "totalChars": details.get("totalChars"),
                "truncated": details.get("truncated"),
                "exitCode": details.get("exitCode"),
                "exitSignal": details.get("exitSignal"),
                "text": text,
            })

    return _digest_stable({"details": details, "text": text})


def hash_tool_result(result: Any) -> str:
    """Legacy alias for hash_tool_outcome (result-only)."""
    h = hash_tool_outcome("", None, result)
    return h or _digest_stable(result)


def _get_time_ms() -> int:
    """Get current time in milliseconds."""
    import time
    return int(time.time() * 1000)


def _get_no_progress_streak(
    history: list[Any],
    tool_name: str,
    args_hash: str,
) -> tuple[int, str | None]:
    """Compute consecutive no-progress streak for a specific tool+args combo.

    Mirrors TS ``getNoProgressStreak``:
    - Iterates history newest-first
    - Counts only records for this tool_name + args_hash that have a result_hash
    - Streak resets when result_hash changes (progress was made)
    Returns (streak_count, latest_result_hash).
    """
    streak = 0
    latest_result_hash: str | None = None

    for rec in reversed(history):
        if rec.tool_name != tool_name or rec.hash != args_hash:
            continue
        if not rec.result_hash:
            continue
        if latest_result_hash is None:
            latest_result_hash = rec.result_hash
            streak = 1
        elif rec.result_hash == latest_result_hash:
            streak += 1
        else:
            break

    return streak, latest_result_hash


# Bucket size for warning throttling — emit once per 10-call increment.
_LOOP_WARNING_BUCKET_SIZE = 10
_MAX_LOOP_WARNING_KEYS = 256


def _should_emit_loop_warning(state: SessionState, warning_key: str, count: int) -> bool:
    """Bucket-throttled warning deduplication — mirrors TS shouldEmitLoopWarning.

    Emits once per LOOP_WARNING_BUCKET_SIZE increment (default: every 10 calls).
    """
    bucket = count // _LOOP_WARNING_BUCKET_SIZE
    last_bucket = state.warning_buckets.get(warning_key, 0)
    if bucket <= last_bucket:
        return False

    state.warning_buckets[warning_key] = bucket
    # Evict oldest key to cap map size
    if len(state.warning_buckets) > _MAX_LOOP_WARNING_KEYS:
        oldest = next(iter(state.warning_buckets))
        del state.warning_buckets[oldest]
    return True


def detect_tool_call_loop(
    state: SessionState,
    tool_name: str,
    params: Any,
    config: dict[str, Any] | None = None,
) -> LoopDetectionResult:
    """Detect if agent is stuck in a tool call loop.

    Mirrors TypeScript ``detectToolCallLoop()``.

    Checks:
    1. Global Circuit Breaker — no-progress streak for this tool >= globalThreshold
    2. Known Poll No Progress — polling tools with no-progress streak >= critical/warning
    3. Ping Pong — two tools alternating with no progress
    4. Generic Repeat — same non-poll tool called >= warningThreshold times

    Key TS alignment fixes:
    - Global circuit breaker uses no-progress *streak* (same result), not total history length
    - Critical-level detections always block (no shown_warnings deduplication)
    - Warning-level detections use bucket throttling (emit once per 10-call increment)
    """
    if not state or not state.tool_call_history:
        return LoopDetectionResult(stuck=False)

    history = list(state.tool_call_history)
    current_hash = hash_tool_call(tool_name, params)

    warning_threshold = config.get("warningThreshold", WARNING_THRESHOLD) if config else WARNING_THRESHOLD
    critical_threshold = config.get("criticalThreshold", CRITICAL_THRESHOLD) if config else CRITICAL_THRESHOLD
    global_threshold = config.get("globalThreshold", GLOBAL_CIRCUIT_BREAKER_THRESHOLD) if config else GLOBAL_CIRCUIT_BREAKER_THRESHOLD

    is_known_poll = _is_known_poll_tool_call(tool_name, params)

    # Detector 1 (TS order): Global Circuit Breaker
    # Uses the no-progress streak (same tool + same args + same result), not len(history).
    # Critical blocks ALWAYS fire — no shown_warnings deduplication (mirrors TS).
    no_progress_streak, latest_result_hash = _get_no_progress_streak(history, tool_name, current_hash)
    if no_progress_streak >= global_threshold:
        warning_key = f"global:{tool_name}:{current_hash}:{latest_result_hash or 'none'}"
        return LoopDetectionResult(
            stuck=True,
            level="critical",
            detector="global_circuit_breaker",
            count=no_progress_streak,
            message=(
                f"CRITICAL: {tool_name} has repeated identical no-progress outcomes "
                f"{no_progress_streak} times. Session execution blocked by global circuit breaker."
            ),
            warning_key=warning_key,
        )

    # Detector 2: Known Poll No Progress
    if is_known_poll:
        if no_progress_streak >= critical_threshold:
            warning_key = f"poll:{tool_name}:{current_hash}:{latest_result_hash or 'none'}"
            return LoopDetectionResult(
                stuck=True,
                level="critical",
                detector="known_poll_no_progress",
                count=no_progress_streak,
                message=(
                    f"CRITICAL: Called {tool_name} with identical arguments and no progress "
                    f"{no_progress_streak} times. This appears to be a stuck polling loop. "
                    "Session execution blocked to prevent resource waste."
                ),
                warning_key=warning_key,
            )

        if no_progress_streak >= warning_threshold:
            warning_key = f"poll:{tool_name}:{current_hash}:{latest_result_hash or 'none'}"
            if _should_emit_loop_warning(state, warning_key, no_progress_streak):
                return LoopDetectionResult(
                    stuck=True,
                    level="warning",
                    detector="known_poll_no_progress",
                    count=no_progress_streak,
                    message=(
                        f"WARNING: You have called {tool_name} {no_progress_streak} times with "
                        "identical arguments and no progress. Stop polling and either (1) increase "
                        "wait time between checks, or (2) report the task as failed if stuck."
                    ),
                    warning_key=warning_key,
                )

    # Detector 3: Ping Pong
    if len(history) >= 6:
        last_6 = history[-6:]
        tool_names = [rec.tool_name for rec in last_6]
        unique_tools = list(set(tool_names))
        if len(unique_tools) == 2:
            tool_a, tool_b = unique_tools
            is_alternating = True
            expected_tool = tool_a if tool_names[0] == tool_a else tool_b
            for actual_tool in tool_names:
                if actual_tool != expected_tool:
                    is_alternating = False
                    break
                expected_tool = tool_b if expected_tool == tool_a else tool_a

            if is_alternating:
                result_hashes = [rec.result_hash for rec in last_6 if rec.result_hash]
                if len(set(result_hashes)) <= 2 and len(result_hashes) >= 4:
                    warning_key = f"ping_pong_{min(tool_a, tool_b)}_{max(tool_a, tool_b)}"
                    if _should_emit_loop_warning(state, warning_key, len(last_6)):
                        return LoopDetectionResult(
                            stuck=True,
                            level="warning",
                            detector="ping_pong",
                            count=len(last_6),
                            message=f"Ping-pong loop detected: alternating between {tool_a} and {tool_b} with no progress",
                            paired_tool_name=tool_b if tool_name == tool_a else tool_a,
                            warning_key=warning_key,
                        )

    # Detector 4: Generic Repeat (warning only, non-poll tools only).
    if not is_known_poll:
        exact_count = sum(1 for rec in history if rec.hash == current_hash)
        if exact_count >= warning_threshold:
            warning_key = f"generic:{tool_name}:{current_hash}"
            if _should_emit_loop_warning(state, warning_key, exact_count):
                return LoopDetectionResult(
                    stuck=True,
                    level="warning",
                    detector="generic_repeat",
                    count=exact_count,
                    message=(
                        f"WARNING: You have called {tool_name} {exact_count} times with identical "
                        "arguments. If this is not making progress, stop retrying and report the task as failed."
                    ),
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
    result: Any = None,
    outcome: str = "success",
    params: Any = None,
    error: Any = None,
) -> None:
    """Record the outcome of a tool call for no-progress loop detection.

    Mirrors TS recordToolCallOutcome() — uses hash_tool_outcome() which accounts
    for process poll/log action-specific details.

    Args:
        state: Session state
        tool_name: Tool name
        result: Tool result
        outcome: Outcome type ("success" | "error")
        params: Original tool params (needed for hashToolOutcome)
        error: Error if any
    """
    if not state or not state.tool_call_history:
        return

    result_hash = hash_tool_outcome(tool_name, params, result, error)
    if result_hash is None:
        return

    args_hash = hash_tool_call(tool_name, params) if params is not None else None

    # Match most-recent pending record for this tool (optionally by args_hash)
    for record in reversed(list(state.tool_call_history)):
        if record.tool_name == tool_name and record.outcome == "pending":
            if args_hash is None or record.hash == args_hash:
                record.outcome = outcome
                record.result_hash = result_hash
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
