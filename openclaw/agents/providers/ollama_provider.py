"""
Ollama provider — native /api/chat implementation.

Mirrors TypeScript: src/agents/ollama-stream.ts + src/agents/models-config.providers.ts

Key design points (aligned with TS):
  1. Uses the native Ollama /api/chat endpoint (NDJSON, not SSE).
  2. Tool calls are collected from ALL done:false intermediate chunks — Ollama
     emits them there, NOT in the final done:true chunk.
  3. Qwen 3 / reasoning models: fall back to message.reasoning when content is empty.
  4. quoteUnsafeIntegerLiterals() pre-processes each NDJSON line before json.loads
     to quote integers > Number.MAX_SAFE_INTEGER as strings — prevents precision
     loss in large IDs (e.g. Telegram chat IDs) passed as tool arguments.
  5. num_ctx is always injected (default 65536) to override Ollama's 4096 default.
  6. Base URL /v1 suffix is stripped so both http://host:11434 and
     http://host:11434/v1 (OpenAI-compat form) work for native API calls.
  7. Bearer auth via OLLAMA_API_KEY env var or api_key constructor arg.
"""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx

from .base import LLMMessage, LLMProvider, LLMResponse

logger = logging.getLogger(__name__)

OLLAMA_NATIVE_BASE_URL = "http://127.0.0.1:11434"
_MAX_SAFE_INTEGER = 9007199254740991  # 2^53 - 1


# ---------------------------------------------------------------------------
# Unsafe-integer quoting — mirrors quoteUnsafeIntegerLiterals() in TS
# ---------------------------------------------------------------------------

def _quote_unsafe_integer_literals(text: str) -> str:
    """Pre-process a JSON string to quote integers > Number.MAX_SAFE_INTEGER.

    JSON.parse (JS) silently loses precision on large integers; Python's
    json.loads preserves them because Python ints are arbitrary precision, but
    we quote them anyway to stay consistent and safe when the parsed value is
    later serialised as JSON (e.g. for a downstream OpenAI-compat call).

    Mirrors quoteUnsafeIntegerLiterals() in src/agents/ollama-stream.ts.
    """
    out_parts: list[str] = []
    in_string = False
    escaped = False
    i = 0
    n = len(text)

    while i < n:
        ch = text[i]

        if in_string:
            out_parts.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            i += 1
            continue

        if ch == '"':
            in_string = True
            out_parts.append(ch)
            i += 1
            continue

        # Potential number token
        if ch == "-" or ch.isdigit():
            token, end, is_integer = _parse_json_number_token(text, i)
            if token is not None:
                if is_integer and _is_unsafe_integer_literal(token):
                    out_parts.append(f'"{token}"')
                else:
                    out_parts.append(token)
                i = end
                continue

        out_parts.append(ch)
        i += 1

    return "".join(out_parts)


def _parse_json_number_token(text: str, start: int) -> tuple[str | None, int, bool]:
    """Return (token_str, end_idx, is_integer) or (None, start, False) if not a number.

    is_integer=True means the token is an integer literal (no decimal or exponent).
    Callers should only quote the token when is_integer=True AND it is unsafe.
    Non-integer numbers (floats) are returned with is_integer=False so they
    are passed through unchanged.
    """
    idx = start
    n = len(text)

    if idx < n and text[idx] == "-":
        idx += 1

    if idx >= n:
        return None, start, False

    if text[idx] == "0":
        idx += 1
    elif text[idx].isdigit() and text[idx] != "0":
        while idx < n and text[idx].isdigit():
            idx += 1
    else:
        return None, start, False

    is_integer = True

    if idx < n and text[idx] == ".":
        is_integer = False
        idx += 1
        if idx >= n or not text[idx].isdigit():
            return None, start, False
        while idx < n and text[idx].isdigit():
            idx += 1

    if idx < n and text[idx] in ("e", "E"):
        is_integer = False
        idx += 1
        if idx < n and text[idx] in ("+", "-"):
            idx += 1
        if idx >= n or not text[idx].isdigit():
            return None, start, False
        while idx < n and text[idx].isdigit():
            idx += 1

    token = text[start:idx]
    return token, idx, is_integer


def _is_unsafe_integer_literal(token: str) -> bool:
    """Return True if token is an integer whose absolute value > MAX_SAFE_INTEGER."""
    digits = token[1:] if token.startswith("-") else token
    max_str = str(_MAX_SAFE_INTEGER)
    if len(digits) < len(max_str):
        return False
    if len(digits) > len(max_str):
        return True
    return digits > max_str


def _safe_json_loads(line: str) -> Any:
    """Parse a JSON line, quoting unsafe integers first."""
    return json.loads(_quote_unsafe_integer_literals(line))


# ---------------------------------------------------------------------------
# OllamaProvider
# ---------------------------------------------------------------------------

class OllamaProvider(LLMProvider):
    """
    Ollama provider for local models — native /api/chat path.

    Uses Ollama's NDJSON streaming API directly (not OpenAI-compat /v1).
    Supports tool calling, image inputs, and Qwen3 reasoning fallback.

    Example:
        provider = OllamaProvider("qwen3.5:35b")
        provider = OllamaProvider("llama3", base_url="http://192.168.1.100:11434")
    """

    def __init__(
        self,
        model: str = "llama3",
        base_url: str | None = None,
        api_key: str | None = None,
        **kwargs: Any,
    ) -> None:
        raw_url = base_url or os.environ.get("OLLAMA_BASE_URL") or OLLAMA_NATIVE_BASE_URL
        super().__init__(model, base_url=raw_url, api_key=api_key, **kwargs)
        # Resolve bearer auth: constructor arg > env var
        self._bearer: str | None = (
            (api_key or "").strip()
            or os.environ.get("OLLAMA_API_KEY", "").strip()
            or None
        )
        # Lazily discovered context window for this model (from /api/show)
        self._cached_context_window: int | None = None

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def supports_tool_calling(self) -> bool:
        return True

    def validate_model(self, model: str) -> bool:
        return bool(model and model.strip())

    # ------------------------------------------------------------------
    # URL helpers
    # ------------------------------------------------------------------

    def _resolve_api_base(self) -> str:
        """Strip /v1 suffix so native Ollama /api/* endpoints work correctly.

        Users may configure base_url as http://host:11434/v1 (OpenAI-compat
        form). The native API lives at the root, so we strip /v1.
        Mirrors resolveOllamaApiBase() in models-config.providers.ts.
        """
        return re.sub(r"/v1$", "", (self.base_url or OLLAMA_NATIVE_BASE_URL).rstrip("/"), flags=re.IGNORECASE)

    def _chat_url(self) -> str:
        return f"{self._resolve_api_base()}/api/chat"

    def _tags_url(self) -> str:
        return f"{self._resolve_api_base()}/api/tags"

    def _show_url(self) -> str:
        return f"{self._resolve_api_base()}/api/show"

    def _version_url(self) -> str:
        return f"{self._resolve_api_base()}/api/version"

    # ------------------------------------------------------------------
    # HTTP client
    # ------------------------------------------------------------------

    def get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if self._bearer:
                headers["Authorization"] = f"Bearer {self._bearer}"
            self._client = httpx.AsyncClient(timeout=300.0, headers=headers)
        return self._client

    # ------------------------------------------------------------------
    # Message conversion — mirrors convertToOllamaMessages()
    # ------------------------------------------------------------------

    def _format_messages(self, messages: list[LLMMessage]) -> list[dict[str, Any]]:
        """Convert LLMMessages to Ollama /api/chat message format.

        Handles:
          - user:      text content + optional base64 images
          - assistant: text content + optional tool_calls history
          - tool:      tool result (role="tool", tool_name from msg.name)

        Mirrors convertToOllamaMessages() in src/agents/ollama-stream.ts.
        """
        result: list[dict[str, Any]] = []

        for msg in messages:
            role = msg.role

            if role == "system":
                result.append({"role": "system", "content": msg.content or ""})

            elif role == "user":
                text = _extract_text(msg.content)
                entry: dict[str, Any] = {"role": "user", "content": text}
                images = _extract_images(msg.content, msg.images)
                if images:
                    entry["images"] = images
                result.append(entry)

            elif role == "assistant":
                text = _extract_text(msg.content)
                # Extract tool calls from:
                #   - msg.tool_calls field (standard internal format)
                #   - content parts of type "toolCall" or "tool_use" (Pi SDK format)
                # Mirrors TS extractToolCalls() which handles both variants.
                tool_calls_from_content = _extract_tool_calls_from_content(msg.content)
                all_tool_calls = list(msg.tool_calls or []) + tool_calls_from_content
                if all_tool_calls:
                    ollama_tcs = _convert_tool_calls_to_ollama(all_tool_calls)
                    entry = {"role": "assistant", "content": text}
                    if ollama_tcs:
                        entry["tool_calls"] = ollama_tcs
                    result.append(entry)
                else:
                    result.append({"role": "assistant", "content": text})

            elif role in ("tool", "toolResult") or msg.tool_call_id:
                # Tool result message — Ollama uses role:"tool" + tool_name.
                # TS reads toolName (camelCase) from Pi SDK messages; Python uses msg.name.
                # Also support toolName as a kwarg-style dict field if passed via extra_params.
                text = _extract_text(msg.content)
                entry = {"role": "tool", "content": text}
                tool_name = msg.name or None
                if tool_name:
                    entry["tool_name"] = tool_name
                result.append(entry)

        return result

    # ------------------------------------------------------------------
    # Tool conversion — mirrors extractOllamaTools()
    # ------------------------------------------------------------------

    @staticmethod
    def _format_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert OpenAI-style tool dicts to Ollama tool format.

        Mirrors extractOllamaTools() in src/agents/ollama-stream.ts.
        """
        ollama_tools: list[dict[str, Any]] = []
        for tool in tools or []:
            fn = tool.get("function") or {}
            name = (fn.get("name") or tool.get("name") or "").strip()
            if not name:
                continue
            ollama_tools.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": fn.get("description") or tool.get("description") or "",
                    "parameters": fn.get("parameters") or tool.get("parameters") or {},
                },
            })
        return ollama_tools

    # ------------------------------------------------------------------
    # Utility API calls
    # ------------------------------------------------------------------

    async def list_models(self) -> list[dict[str, Any]]:
        """List locally installed Ollama models via GET /api/tags."""
        client = self.get_client()
        try:
            resp = await client.get(self._tags_url())
            resp.raise_for_status()
            return resp.json().get("models", [])
        except Exception as exc:
            logger.error("Ollama list_models failed: %s", exc)
            return []

    async def check_connection(self) -> bool:
        """Return True if the Ollama server is reachable."""
        client = self.get_client()
        try:
            resp = await client.get(self._version_url())
            return resp.is_success
        except Exception:
            return False

    async def pull_model(self, model: str) -> dict[str, Any]:
        """Pull a model from the Ollama library."""
        client = self.get_client()
        try:
            resp = await client.post(
                f"{self._resolve_api_base()}/api/pull",
                json={"name": model},
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.error("Ollama pull_model(%s) failed: %s", model, exc)
            return {"status": "error", "error": str(exc)}

    async def get_model_info(self, model: str) -> dict[str, Any]:
        """Fetch detailed model info via POST /api/show."""
        client = self.get_client()
        try:
            resp = await client.post(self._show_url(), json={"name": model})
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.debug("Ollama get_model_info(%s) failed: %s", model, exc)
            return {}

    async def _resolve_num_ctx(self) -> int:
        """Return context window for the current model, querying /api/show if needed.

        Mirrors the TS pattern where `model.contextWindow ?? 65536` is used and
        the contextWindow comes from per-model /api/show discovery at startup.
        Python does lazy discovery here so any OllamaProvider instance can get
        the correct context window even if it was not pre-discovered via models.json.

        Result is cached on the instance for the lifetime of the provider.
        """
        if self._cached_context_window is not None:
            return self._cached_context_window

        info = await self.get_model_info(self.model)
        model_info: dict[str, Any] = info.get("model_info") or {}
        for key, value in model_info.items():
            if key.endswith(".context_length") and isinstance(value, (int, float)) and value > 0:
                ctx = int(value)
                self._cached_context_window = ctx
                logger.debug("Ollama model %s context window: %d", self.model, ctx)
                return ctx

        # Fallback — matches TS: model.contextWindow ?? 65536
        self._cached_context_window = 65536
        return 65536

    # ------------------------------------------------------------------
    # Main streaming method — mirrors createOllamaStreamFn run loop
    # ------------------------------------------------------------------

    async def stream(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> AsyncIterator[LLMResponse]:
        """Stream responses from Ollama /api/chat.

        Fully mirrors the TypeScript createOllamaStreamFn() behaviour:
          - Always injects options.num_ctx (default 65536) to override Ollama's 4096 default
          - Accumulates tool_calls from ALL done:false intermediate chunks
          - Falls back to message.reasoning when message.content is empty (Qwen3)
          - Quotes unsafe integers in NDJSON before JSON parsing
          - Emits text_delta per chunk for real-time streaming
          - Emits tool_call LLMResponse with normalised tool call list when done
          - Emits done LLMResponse with token usage
        """
        client = self.get_client()
        model_id = kwargs.get("model") or self.model

        # ── Options (num_ctx is always set) ──────────────────────────────────
        # Prefer explicit kwarg, then auto-discover from /api/show (cached).
        # Mirrors TS: { num_ctx: model.contextWindow ?? 65536 }
        num_ctx: int = (
            kwargs.get("num_ctx")
            or kwargs.get("context_window")
            or await self._resolve_num_ctx()
        )
        options: dict[str, Any] = {"num_ctx": num_ctx}
        if isinstance(kwargs.get("temperature"), (int, float)):
            options["temperature"] = float(kwargs["temperature"])
        if max_tokens:
            options["num_predict"] = max_tokens

        # ── Request body ─────────────────────────────────────────────────────
        ollama_messages = self._format_messages(messages)
        body: dict[str, Any] = {
            "model": model_id,
            "messages": ollama_messages,
            "stream": True,
            "options": options,
        }

        ollama_tools = self._format_tools(tools or [])
        if ollama_tools:
            body["tools"] = ollama_tools

        # ── Stream request ───────────────────────────────────────────────────
        try:
            async with client.stream("POST", self._chat_url(), json=body) as response:
                response.raise_for_status()

                accumulated_content = ""
                accumulated_tool_calls: list[dict[str, Any]] = []
                final_chunk: dict[str, Any] | None = None

                async for raw_line in response.aiter_lines():
                    if not raw_line:
                        continue

                    try:
                        chunk: dict[str, Any] = _safe_json_loads(raw_line)
                    except (json.JSONDecodeError, ValueError) as exc:
                        logger.debug("Ollama NDJSON parse error (skipping line): %s", exc)
                        continue

                    msg_part = chunk.get("message") or {}
                    content_delta: str = msg_part.get("content") or ""
                    reasoning_delta: str = msg_part.get("reasoning") or ""

                    # Qwen 3 reasoning mode: content may be empty; output is in reasoning
                    effective_delta = content_delta or reasoning_delta
                    if effective_delta:
                        accumulated_content += effective_delta
                        yield LLMResponse(type="text_delta", content=effective_delta)

                    # Collect tool_calls from intermediate chunks (Ollama quirk —
                    # tool calls arrive in done:false chunks, NOT the done:true chunk)
                    if msg_part.get("tool_calls"):
                        for tc in msg_part["tool_calls"]:
                            accumulated_tool_calls.append(tc)

                    if chunk.get("done"):
                        final_chunk = chunk
                        break

                # ── Emit tool calls ───────────────────────────────────────────
                if accumulated_tool_calls:
                    normalised = _normalise_tool_calls(accumulated_tool_calls)
                    yield LLMResponse(
                        type="tool_call",
                        content=None,
                        tool_calls=normalised,
                    )

                # ── Emit done with usage ──────────────────────────────────────
                usage: dict[str, Any] | None = None
                if final_chunk:
                    prompt_tokens = final_chunk.get("prompt_eval_count") or 0
                    completion_tokens = final_chunk.get("eval_count") or 0
                    usage = {
                        "input": prompt_tokens,
                        "output": completion_tokens,
                        "total": prompt_tokens + completion_tokens,
                        "cache_read": 0,
                        "cache_write": 0,
                    }
                else:
                    logger.warning("Ollama stream ended without a done:true final chunk")

                finish_reason = "tool_use" if accumulated_tool_calls else "stop"
                yield LLMResponse(
                    type="done",
                    content=None,
                    finish_reason=finish_reason,
                    usage=usage,
                )

        except httpx.HTTPStatusError as exc:
            logger.error("Ollama HTTP error %s: %s", exc.response.status_code, exc)
            yield LLMResponse(
                type="error",
                content=f"Ollama HTTP error {exc.response.status_code}: {exc}",
            )
        except httpx.HTTPError as exc:
            logger.error("Ollama connection error: %s", exc)
            yield LLMResponse(type="error", content=f"Ollama connection error: {exc}")
        except Exception as exc:
            logger.error("Ollama streaming error: %s", exc, exc_info=True)
            yield LLMResponse(type="error", content=str(exc))


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _extract_text(content: Any) -> str:
    """Extract plain text from string or content-part list."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                parts.append(str(part.get("text") or ""))
            elif isinstance(part, str):
                parts.append(part)
        return "".join(parts)
    if content is None:
        return ""
    return str(content)


def _extract_tool_calls_from_content(content: Any) -> list[dict[str, Any]]:
    """Extract tool calls from Pi SDK content-part arrays.

    TS SDK assistant messages may encode tool calls as content parts of type
    "toolCall" or "tool_use" (Anthropic-style). This mirrors extractToolCalls()
    in ollama-stream.ts so both formats are handled uniformly.

    Returns a list of internal tool call dicts (same format as LLMMessage.tool_calls).
    """
    if not isinstance(content, list):
        return []
    result: list[dict[str, Any]] = []
    for part in content:
        if not isinstance(part, dict):
            continue
        t = part.get("type")
        if t == "toolCall":
            result.append({
                "id": part.get("id", ""),
                "name": part.get("name", ""),
                "arguments": part.get("arguments") or {},
            })
        elif t == "tool_use":
            result.append({
                "id": part.get("id", ""),
                "name": part.get("name", ""),
                "arguments": part.get("input") or part.get("arguments") or {},
            })
    return result


def _extract_images(content: Any, images_field: list[str] | None) -> list[str]:
    """Extract base64 image data from content parts or the images field.

    Mirrors extractOllamaImages() — returns list of base64-encoded strings.
    """
    result: list[str] = []
    # Prefer structured content parts
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and part.get("type") == "image":
                data = part.get("data") or part.get("url") or ""
                if data:
                    result.append(data)
    # Fallback: explicit images field
    if not result and images_field:
        result.extend(images_field)
    return result


def _convert_tool_calls_to_ollama(tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert internal tool call dicts to Ollama's tool_calls format.

    Internal format (from AgentMessage/LLMMessage):
      {"id": "...", "name": "tool_name", "params": {...}}
      OR OpenAI-style: {"id": "...", "type": "function", "function": {"name": ..., "arguments": ...}}

    Ollama format:
      {"function": {"name": "...", "arguments": {...}}}
    """
    result: list[dict[str, Any]] = []
    for tc in tool_calls or []:
        # OpenAI-style
        if "function" in tc:
            fn = tc["function"]
            args = fn.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            result.append({"function": {"name": fn.get("name", ""), "arguments": args}})
        else:
            # Internal pi-style
            name = tc.get("name") or ""
            params = tc.get("params") or tc.get("arguments") or {}
            result.append({"function": {"name": name, "arguments": params}})
    return result


def _normalise_tool_calls(
    ollama_tcs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert Ollama tool_call objects to the internal LLMResponse tool call format.

    Ollama: {"function": {"name": "...", "arguments": {...}}}
    Internal: {"id": "ollama_call_<uuid>", "name": "...", "arguments": {...}}

    Mirrors buildAssistantMessage() tool call normalisation in ollama-stream.ts.
    """
    result: list[dict[str, Any]] = []
    for tc in ollama_tcs:
        fn = tc.get("function") or {}
        name: str = fn.get("name") or ""
        arguments: Any = fn.get("arguments") or {}
        # Arguments may arrive as JSON string from some Ollama versions
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except Exception:
                arguments = {}
        result.append({
            "id": f"ollama_call_{uuid.uuid4().hex[:16]}",
            "name": name,
            "arguments": arguments,
            # Also include params alias (used by AgentLoop)
            "params": arguments,
        })
    return result
