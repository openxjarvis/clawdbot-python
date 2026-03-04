"""Session message pipeline guards.

Mirrors TypeScript openclaw/src/agents/session-tool-result-guard.ts.

Key behaviours:
- ``install_session_tool_result_guard`` monkey-patches an agent's
  ``add_message()`` method to intercept all messages written to the
  session.
- Auto-injects synthetic ``tool_result`` messages for any
  ``tool_use``/``tool_calls`` that never received a real result
  (e.g. because the run was aborted).
- Caps individual tool result sizes via ``cap_tool_result_size``.
- Normalizes ``tool_name`` on persisted tool-result messages via
  ``normalize_persisted_tool_result_name``.
- Skips tool-call extraction for ``aborted``/``error`` stop-reason
  assistant messages (incomplete blocks cause API 400s).
- Fires a ``beforeMessageWriteHook`` if provided, with support for
  blocking or replacing individual messages.
- Emits ``session_transcript_update`` events after each successful write.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Maximum chars for a single tool result persisted to the transcript.
# Mirrors TS HARD_MAX_TOOL_RESULT_CHARS.
HARD_MAX_TOOL_RESULT_CHARS = 200_000

_GUARD_TRUNCATION_SUFFIX = (
    "\n\n⚠️ [Content truncated during persistence — original exceeded size limit. "
    "Use offset/limit parameters or request specific sections for large content.]"
)

_MIN_KEEP_CHARS = 2_000


# ---------------------------------------------------------------------------
# cap_tool_result_size
# ---------------------------------------------------------------------------

def cap_tool_result_size(msg: dict[str, Any]) -> dict[str, Any]:
    """Truncate oversized text content in a tool_result message.

    Returns the original dict if under the limit, otherwise a shallow copy
    with truncated ``content`` string.
    Mirrors TS ``capToolResultSize()``.
    """
    if msg.get("role") not in ("tool", "tool_result", "toolResult"):
        return msg
    content = msg.get("content")
    if isinstance(content, str) and len(content) > HARD_MAX_TOOL_RESULT_CHARS:
        keep = max(_MIN_KEEP_CHARS, HARD_MAX_TOOL_RESULT_CHARS - len(_GUARD_TRUNCATION_SUFFIX))
        truncated = content[:keep] + _GUARD_TRUNCATION_SUFFIX
        return {**msg, "content": truncated}
    if isinstance(content, list):
        changed = False
        new_blocks = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text", "")
                if isinstance(text, str) and len(text) > HARD_MAX_TOOL_RESULT_CHARS:
                    keep = max(
                        _MIN_KEEP_CHARS,
                        HARD_MAX_TOOL_RESULT_CHARS - len(_GUARD_TRUNCATION_SUFFIX),
                    )
                    new_blocks.append({**block, "text": text[:keep] + _GUARD_TRUNCATION_SUFFIX})
                    changed = True
                    continue
            new_blocks.append(block)
        if changed:
            return {**msg, "content": new_blocks}
    return msg


# ---------------------------------------------------------------------------
# normalize_persisted_tool_result_name
# ---------------------------------------------------------------------------

def normalize_persisted_tool_result_name(
    message: dict[str, Any],
    fallback_name: str | None = None,
) -> dict[str, Any]:
    """Ensure ``tool_name`` on a tool-result message is a non-empty string.

    Mirrors TS ``normalizePersistedToolResultName()``.
    """
    if message.get("role") not in ("tool", "tool_result", "toolResult"):
        return message
    raw_name = message.get("tool_name") or message.get("toolName")
    if isinstance(raw_name, str):
        normalized = raw_name.strip()
        if normalized:
            if normalized == raw_name:
                return message
            return {**message, "tool_name": normalized, "toolName": normalized}
    # Fall back
    if fallback_name and fallback_name.strip():
        return {**message, "tool_name": fallback_name.strip(), "toolName": fallback_name.strip()}
    if isinstance(raw_name, str):
        return {**message, "tool_name": "unknown", "toolName": "unknown"}
    return message


# ---------------------------------------------------------------------------
# Pending tool-call state tracker
# ---------------------------------------------------------------------------

class _PendingToolCallState:
    """Track unresolved tool_use/tool_call blocks from assistant messages."""

    def __init__(self) -> None:
        self._pending: dict[str, str | None] = {}  # id → tool_name or None

    def size(self) -> int:
        return len(self._pending)

    def entries(self) -> list[tuple[str, str | None]]:
        return list(self._pending.items())

    def get_tool_name(self, tool_call_id: str) -> str | None:
        return self._pending.get(tool_call_id)

    def delete(self, tool_call_id: str) -> None:
        self._pending.pop(tool_call_id, None)

    def clear(self) -> None:
        self._pending.clear()

    def get_pending_ids(self) -> list[str]:
        return list(self._pending.keys())

    def track_tool_calls(self, tool_calls: list[dict[str, Any]]) -> None:
        for tc in tool_calls:
            tc_id = tc.get("id") or tc.get("tool_use_id") or tc.get("toolCallId")
            tc_name = tc.get("name") or tc.get("function", {}).get("name") if isinstance(tc.get("function"), dict) else None
            if tc_id:
                self._pending[str(tc_id)] = tc_name

    def should_flush_before_non_tool_result(self, role: str, new_tool_call_count: int) -> bool:
        if self.size() == 0:
            return False
        if role in ("user", "human"):
            return True
        if role in ("assistant",) and new_tool_call_count > 0:
            return False
        if role == "assistant" and new_tool_call_count == 0:
            return True
        return role not in ("tool", "tool_result", "toolResult", "assistant")

    def should_flush_before_new_tool_calls(self, new_count: int) -> bool:
        return self.size() > 0 and new_count > 0

    def should_flush_for_sanitized_drop(self) -> bool:
        return self.size() > 0


# ---------------------------------------------------------------------------
# Helpers to extract tool calls from messages
# ---------------------------------------------------------------------------

def _extract_tool_calls_from_assistant(msg: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract tool_use/tool_call blocks from an assistant message."""
    calls: list[dict[str, Any]] = []
    # OpenAI-style
    tool_calls = msg.get("tool_calls") or []
    if isinstance(tool_calls, list):
        calls.extend(tool_calls)
    # Anthropic-style content blocks
    content = msg.get("content")
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") in ("tool_use", "tool_call"):
                calls.append(block)
    return calls


def _extract_tool_result_id(msg: dict[str, Any]) -> str | None:
    return (
        msg.get("tool_call_id")
        or msg.get("tool_use_id")
        or msg.get("toolCallId")
        or None
    )


# ---------------------------------------------------------------------------
# Synthetic tool-result factory
# ---------------------------------------------------------------------------

def _make_missing_tool_result(
    tool_call_id: str,
    tool_name: str | None,
) -> dict[str, Any]:
    """Build a synthetic tool_result placeholder for a missing response.

    Mirrors TS ``makeMissingToolResult()``.
    """
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "tool_name": tool_name or "unknown",
        "toolName": tool_name or "unknown",
        "content": "[Tool result missing — run was interrupted or aborted.]",
        "_synthetic": True,
    }


# ---------------------------------------------------------------------------
# Transcript update event
# ---------------------------------------------------------------------------

def _emit_session_transcript_update(session_key: str | None) -> None:
    """Broadcast a lightweight 'transcript updated' signal.

    Mirrors TS ``emitSessionTranscriptUpdate()``.
    """
    if not session_key:
        return
    try:
        from openclaw.hooks.internal_hooks import trigger_internal_hook, InternalHookEvent
        import asyncio
        event = InternalHookEvent(
            type="session",
            action="transcript_update",
            session_key=session_key,
            context={"sessionKey": session_key},
        )
        try:
            asyncio.ensure_future(trigger_internal_hook(event))
        except RuntimeError:
            pass
    except Exception:
        pass


# ---------------------------------------------------------------------------
# install_session_tool_result_guard
# ---------------------------------------------------------------------------

def install_session_tool_result_guard(
    agent: Any,
    *,
    before_message_write_hook: Callable[[dict[str, Any]], dict[str, Any] | None] | None = None,
    allow_synthetic_tool_results: bool = True,
    transform_message_for_persistence: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    transform_tool_result_for_persistence: Callable[
        [dict[str, Any], dict[str, Any]], dict[str, Any]
    ] | None = None,
    allowed_tool_names: set[str] | None = None,
) -> dict[str, Any]:
    """Monkey-patch ``agent.add_message`` with a guarded version.

    The guard:
    1. Normalizes and caps tool-result messages.
    2. Tracks unresolved tool_use blocks.
    3. Flushes synthetic tool_results before user / next-assistant messages.
    4. Applies ``before_message_write_hook`` to allow blocking/replacing.
    5. Emits ``session_transcript_update`` after each write.

    Returns a dict with:
    - ``flush_pending_tool_results`` callable
    - ``get_pending_ids`` callable
    - ``restore`` callable to undo the monkey-patch

    Mirrors TS ``installSessionToolResultGuard()``.
    """
    original_add_message = agent.add_message

    pending_state = _PendingToolCallState()

    def _persist_msg(msg: dict[str, Any]) -> dict[str, Any]:
        return transform_message_for_persistence(msg) if transform_message_for_persistence else msg

    def _persist_tool_result(msg: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
        return (
            transform_tool_result_for_persistence(msg, meta)
            if transform_tool_result_for_persistence
            else msg
        )

    def _apply_before_write_hook(msg: dict[str, Any]) -> dict[str, Any] | None:
        if not before_message_write_hook:
            return msg
        result = before_message_write_hook(msg)
        return result  # None means block

    def _flush_pending_tool_results() -> None:
        if pending_state.size() == 0:
            return
        if allow_synthetic_tool_results:
            for tc_id, tc_name in pending_state.entries():
                synthetic = _make_missing_tool_result(tc_id, tc_name)
                candidate = _apply_before_write_hook(
                    _persist_tool_result(
                        _persist_msg(synthetic),
                        {"toolCallId": tc_id, "toolName": tc_name, "isSynthetic": True},
                    )
                )
                if candidate is not None:
                    original_add_message(candidate)
        pending_state.clear()

    def _guarded_add_message(message: dict[str, Any]) -> Any:
        next_msg = message
        role = message.get("role", "")

        # Sanitize assistant messages — drop unknown tool calls if filter active
        if role == "assistant" and allowed_tool_names is not None:
            tool_calls = _extract_tool_calls_from_assistant(next_msg)
            filtered = [
                tc for tc in tool_calls
                if (tc.get("name") or (tc.get("function") or {}).get("name") or "") in allowed_tool_names
            ]
            if len(filtered) != len(tool_calls):
                # Rebuild message without unknown tool calls
                next_msg = {**next_msg}
                if "tool_calls" in next_msg:
                    next_msg["tool_calls"] = filtered
                # Anthropic content blocks
                if isinstance(next_msg.get("content"), list):
                    next_msg["content"] = [
                        b for b in next_msg["content"]
                        if not (isinstance(b, dict) and b.get("type") in ("tool_use", "tool_call"))
                        or (b.get("name") in (allowed_tool_names or set()))
                    ]
                if pending_state.should_flush_for_sanitized_drop():
                    _flush_pending_tool_results()
                if not filtered and not next_msg.get("content"):
                    return None

        next_role = next_msg.get("role", "")

        if next_role in ("tool", "tool_result", "toolResult"):
            tc_id = _extract_tool_result_id(next_msg)
            tool_name = pending_state.get_tool_name(tc_id) if tc_id else None
            if tc_id:
                pending_state.delete(tc_id)
            normalized = normalize_persisted_tool_result_name(next_msg, tool_name)
            capped = cap_tool_result_size(_persist_msg(normalized))
            persisted = _apply_before_write_hook(
                _persist_tool_result(
                    capped,
                    {"toolCallId": tc_id, "toolName": tool_name, "isSynthetic": False},
                )
            )
            if persisted is None:
                return None
            return original_add_message(persisted)

        # For assistant messages: skip tool-call extraction on aborted/error stop
        stop_reason = next_msg.get("stop_reason") or next_msg.get("stopReason") or ""
        tool_calls = (
            _extract_tool_calls_from_assistant(next_msg)
            if next_role == "assistant" and stop_reason not in ("aborted", "error")
            else []
        )

        if pending_state.should_flush_before_non_tool_result(next_role, len(tool_calls)):
            _flush_pending_tool_results()
        if pending_state.should_flush_before_new_tool_calls(len(tool_calls)):
            _flush_pending_tool_results()

        final = _apply_before_write_hook(_persist_msg(next_msg))
        if final is None:
            return None

        result = original_add_message(final)

        # Emit transcript update event
        session_key = getattr(agent, "session_key", None) or getattr(agent, "_session_key", None)
        _emit_session_transcript_update(session_key)

        if tool_calls:
            pending_state.track_tool_calls(tool_calls)

        return result

    # Monkey-patch
    agent.add_message = _guarded_add_message

    def _restore() -> None:
        agent.add_message = original_add_message

    return {
        "flush_pending_tool_results": _flush_pending_tool_results,
        "get_pending_ids": pending_state.get_pending_ids,
        "restore": _restore,
    }
