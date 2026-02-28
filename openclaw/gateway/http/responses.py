"""
OpenResponses-compatible /v1/responses HTTP endpoint.

Provides POST /v1/responses endpoint matching the OpenResponses API.
Disabled by default; enable via config:
  gateway.http.endpoints.responses.enabled = true

Reference: openclaw/docs/gateway/openresponses-http-api.md
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class ResponsesRequest(BaseModel):
    """OpenResponses POST /v1/responses request body."""

    model: str = "openclaw"
    input: str | list[dict[str, Any]] | None = None
    instructions: str | None = None
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | dict[str, Any] | None = None
    stream: bool = False
    max_output_tokens: int | None = None
    user: str | None = None

    # accepted but ignored fields (schema compatibility)
    max_tool_calls: int | None = None
    reasoning: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    store: bool | None = None
    previous_response_id: str | None = None
    truncation: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_agent_id(model: str) -> str:
    """Extract agent id from model string, mirroring chat_completions.parse_agent_id."""
    if model.startswith("openclaw:"):
        return model.split(":", 1)[1]
    if model.startswith("agent:"):
        return model.split(":", 1)[1]
    return "main"


def _resolve_session_key(agent_id: str, user: str | None) -> str:
    """Derive stable session key from user field (mirrors TS openresponses handler)."""
    if user:
        h = hashlib.sha256(user.encode()).hexdigest()[:16]
        return f"agent:{agent_id}:responses:{h}"
    return f"agent:{agent_id}:responses:ephemeral"


def _extract_user_message(input_val: str | list | None) -> str | None:
    """Extract the most-recent user message from an input string or items array."""
    if input_val is None:
        return None
    if isinstance(input_val, str):
        return input_val
    # Items array: find the last user / function_call_output item
    last_user: str | None = None
    for item in reversed(input_val):
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if item_type == "message":
            role = item.get("role", "user")
            if role in ("user",):
                content = item.get("content", "")
                if isinstance(content, str):
                    last_user = content
                elif isinstance(content, list):
                    parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
                    last_user = " ".join(parts)
                break
        elif item_type == "function_call_output":
            last_user = f"[tool result] {item.get('output', '')}"
            break
    return last_user


def _build_system_additions(input_val: str | list | None, instructions: str | None) -> list[str]:
    """Collect system/developer messages and instructions to prepend to system prompt."""
    additions: list[str] = []
    if instructions:
        additions.append(instructions)
    if isinstance(input_val, list):
        for item in input_val:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "message" and item.get("role") in ("system", "developer"):
                content = item.get("content", "")
                if isinstance(content, str):
                    additions.append(content)
    return additions


# ---------------------------------------------------------------------------
# Main handler
# ---------------------------------------------------------------------------

async def handle_responses_request(
    body: dict[str, Any],
    gateway: Any,
    authorization: str | None = None,
    agent_id_header: str | None = None,
) -> dict[str, Any]:
    """Handle POST /v1/responses (OpenResponses-compatible).

    Mirrors TS handleResponsesRequest() in server-http-openai.ts.

    Args:
        body: Parsed JSON request body.
        gateway: Gateway server instance (provides agent runtime).
        authorization: Authorization header value.
        agent_id_header: x-openclaw-agent-id header value.

    Returns:
        OpenResponses-compatible response dict.
    """
    req = ResponsesRequest(**body)
    agent_id = agent_id_header or _parse_agent_id(req.model)
    session_key = _resolve_session_key(agent_id, req.user)

    user_message = _extract_user_message(req.input)
    if not user_message:
        raise ValueError("No user message found in input")

    system_additions = _build_system_additions(req.input, req.instructions)

    messages = [{"role": "user", "content": user_message}]

    # Run the agent turn
    content_parts: list[str] = []
    usage: dict[str, Any] | None = None
    function_calls: list[dict[str, Any]] = []

    async for event in gateway.run_turn(
        session_key=session_key,
        messages=messages,
        stream=False,
    ):
        if hasattr(event, "type"):
            etype = event.type
            data = event.data if hasattr(event, "data") else {}
        elif isinstance(event, dict):
            etype = event.get("type", "")
            data = event.get("data", {})
        else:
            continue

        if etype == "agent_text":
            content_parts.append(data.get("text", ""))
        elif etype == "agent_usage":
            usage = data
        elif etype in ("tool_call", "function_call"):
            function_calls.append({
                "type": "function_call",
                "id": data.get("id", f"call_{len(function_calls)}"),
                "call_id": data.get("call_id") or data.get("id", ""),
                "name": data.get("name", ""),
                "arguments": json.dumps(data.get("arguments", {})),
            })

    text_content = "".join(content_parts)
    response_id = f"resp_{hashlib.sha256(f'{session_key}{time.time()}'.encode()).hexdigest()[:24]}"

    output_items: list[dict[str, Any]] = []
    if text_content:
        output_items.append({
            "type": "message",
            "id": f"msg_{response_id}",
            "role": "assistant",
            "content": [{"type": "output_text", "text": text_content, "annotations": []}],
        })
    for fc in function_calls:
        output_items.append(fc)

    response: dict[str, Any] = {
        "id": response_id,
        "object": "response",
        "created_at": int(time.time()),
        "status": "completed",
        "model": req.model,
        "output": output_items,
        "parallel_tool_calls": True,
        "tool_choice": req.tool_choice or "auto",
        "tools": req.tools or [],
        "text": {"format": {"type": "text"}},
        "temperature": 1.0,
        "top_p": 1.0,
        "truncation": "disabled",
    }

    if usage:
        response["usage"] = {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "total_tokens": (
                usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
            ),
            "input_tokens_details": {"cached_tokens": usage.get("cache_read_input_tokens", 0)},
            "output_tokens_details": {"reasoning_tokens": 0},
        }

    return response


__all__ = [
    "ResponsesRequest",
    "handle_responses_request",
]
