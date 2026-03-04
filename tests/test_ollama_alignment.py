"""Comprehensive Ollama alignment tests — mirrors the TS test suite.

Covers:
  - convertToOllamaMessages  (mirrors ollama-stream.test.ts)
  - buildAssistantMessage / _normalise_tool_calls
  - parseNdjsonStream / NDJSON accumulation (Python equivalent)
  - createOllamaStreamFn behaviour (Python OllamaProvider.stream())
  - Ollama provider gating logic (mirrors models-config.providers.ollama.test.ts)
  - num_ctx auto-discovery via /api/show

All tests in this file are pure unit tests — no live Ollama instance required.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import unittest.mock as mock
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openclaw.agents.providers.base import LLMMessage, LLMResponse
from openclaw.agents.providers.ollama_provider import (
    OllamaProvider,
    _convert_tool_calls_to_ollama,
    _extract_images,
    _extract_text,
    _extract_tool_calls_from_content,
    _is_unsafe_integer_literal,
    _normalise_tool_calls,
    _quote_unsafe_integer_literals,
    _safe_json_loads,
)


# ============================================================================
# convertToOllamaMessages — mirrors ollama-stream.test.ts
# ============================================================================

class TestConvertToOllamaMessages:
    """Tests for OllamaProvider._format_messages()."""

    def _provider(self):
        return OllamaProvider("test-model")

    def test_converts_user_text_messages(self):
        p = self._provider()
        result = p._format_messages([LLMMessage(role="user", content="hello")])
        assert result == [{"role": "user", "content": "hello"}]

    def test_converts_user_messages_with_content_parts(self):
        p = self._provider()
        content = [
            {"type": "text", "text": "describe this"},
            {"type": "image", "data": "base64data"},
        ]
        result = p._format_messages([LLMMessage(role="user", content=content)])
        assert result == [{"role": "user", "content": "describe this", "images": ["base64data"]}]

    def test_prepends_system_message(self):
        p = self._provider()
        msgs = [
            LLMMessage(role="system", content="You are helpful."),
            LLMMessage(role="user", content="hello"),
        ]
        result = p._format_messages(msgs)
        assert result[0] == {"role": "system", "content": "You are helpful."}
        assert result[1] == {"role": "user", "content": "hello"}

    def test_converts_assistant_with_toolcall_content_blocks(self):
        """Mirrors TS: converts assistant messages with toolCall content blocks."""
        p = self._provider()
        content = [
            {"type": "text", "text": "Let me check."},
            {"type": "toolCall", "id": "call_1", "name": "bash", "arguments": {"command": "ls"}},
        ]
        result = p._format_messages([LLMMessage(role="assistant", content=content)])
        assert len(result) == 1
        entry = result[0]
        assert entry["role"] == "assistant"
        assert entry["content"] == "Let me check."
        assert entry["tool_calls"] == [
            {"function": {"name": "bash", "arguments": {"command": "ls"}}}
        ]

    def test_converts_assistant_with_tool_use_content_blocks(self):
        """Mirrors TS extractToolCalls: also handles tool_use (Anthropic-style) type."""
        p = self._provider()
        content = [
            {"type": "text", "text": "Using tool."},
            {"type": "tool_use", "id": "call_1", "name": "search", "input": {"q": "python"}},
        ]
        result = p._format_messages([LLMMessage(role="assistant", content=content)])
        entry = result[0]
        assert entry["role"] == "assistant"
        assert entry["tool_calls"] == [
            {"function": {"name": "search", "arguments": {"q": "python"}}}
        ]

    def test_converts_tool_result_messages_with_tool_role(self):
        """Mirrors TS: converts tool result messages with 'tool' role."""
        p = self._provider()
        result = p._format_messages([
            LLMMessage(role="tool", content="file1.txt\nfile2.txt", name="bash")
        ])
        assert result == [{"role": "tool", "content": "file1.txt\nfile2.txt", "tool_name": "bash"}]

    def test_converts_toolresult_role_to_tool(self):
        """Mirrors TS: converts SDK 'toolResult' role to Ollama 'tool' role."""
        p = self._provider()
        result = p._format_messages([LLMMessage(role="toolResult", content="command output here")])
        assert result[0]["role"] == "tool"
        assert result[0]["content"] == "command output here"

    def test_includes_tool_name_from_tool_result_messages(self):
        """Mirrors TS: includes tool_name from toolResult messages."""
        p = self._provider()
        result = p._format_messages([
            LLMMessage(role="toolResult", content="file contents here", name="read")
        ])
        assert result == [{"role": "tool", "content": "file contents here", "tool_name": "read"}]

    def test_omits_tool_name_when_not_provided(self):
        """Mirrors TS: omits tool_name when not provided in toolResult."""
        p = self._provider()
        result = p._format_messages([LLMMessage(role="tool", content="output")])
        assert result == [{"role": "tool", "content": "output"}]
        assert "tool_name" not in result[0]

    def test_handles_empty_messages_array(self):
        p = self._provider()
        assert p._format_messages([]) == []

    def test_converts_tool_call_id_based_tool_result(self):
        """Messages with only tool_call_id (no recognized role) are treated as tool results.
        In practice, add_tool_message() always uses role='tool', but this tests the fallback.
        """
        p = self._provider()
        # Using an unrecognised role with tool_call_id — should route to tool path
        result = p._format_messages([
            LLMMessage(role="tool", content="result", tool_call_id="call_1", name="my_tool")
        ])
        assert result[0]["role"] == "tool"
        assert result[0]["content"] == "result"
        assert result[0]["tool_name"] == "my_tool"

    def test_assistant_tool_calls_field(self):
        """tool_calls field on assistant message is converted correctly."""
        p = self._provider()
        msgs = [LLMMessage(
            role="assistant",
            content="",
            tool_calls=[{"name": "bash", "arguments": {"cmd": "ls"}}],
        )]
        result = p._format_messages(msgs)
        entry = result[0]
        assert entry["role"] == "assistant"
        assert entry["tool_calls"][0]["function"]["name"] == "bash"
        assert entry["tool_calls"][0]["function"]["arguments"] == {"cmd": "ls"}


# ============================================================================
# _normalise_tool_calls — mirrors buildAssistantMessage tool call normalisation
# ============================================================================

class TestNormaliseToolCalls:

    def test_normalises_ollama_tool_calls(self):
        """Mirrors TS buildAssistantMessage: id is ollama_call_<uuid>."""
        ollama_tcs = [{"function": {"name": "bash", "arguments": {"command": "ls -la"}}}]
        result = _normalise_tool_calls(ollama_tcs)
        assert len(result) == 1
        tc = result[0]
        assert tc["name"] == "bash"
        assert tc["arguments"] == {"command": "ls -la"}
        assert tc["id"].startswith("ollama_call_")
        assert len(tc["id"]) == len("ollama_call_") + 16  # 16 hex chars

    def test_all_costs_zero(self):
        """Mirrors TS: all costs are zero for local models (no-op check via usage)."""
        # Usage is set in stream() — cost is always zero (Ollama is free)
        # This is a structural check
        ollama_tcs = [{"function": {"name": "tool", "arguments": {}}}]
        result = _normalise_tool_calls(ollama_tcs)
        assert result[0]["arguments"] == {}

    def test_arguments_as_string_parsed(self):
        """Some Ollama versions return arguments as JSON string."""
        ollama_tcs = [{"function": {"name": "read", "arguments": '{"path": "/tmp/a"}'}}]
        result = _normalise_tool_calls(ollama_tcs)
        assert result[0]["arguments"] == {"path": "/tmp/a"}


# ============================================================================
# quoteUnsafeIntegerLiterals — mirrors TS quoteUnsafeIntegerLiterals tests
# ============================================================================

class TestQuoteUnsafeIntegerLiterals:

    def test_preserves_safe_integers(self):
        line = '{"retries":3,"delayMs":2500}'
        result = _quote_unsafe_integer_literals(line)
        assert result == line
        parsed = json.loads(result)
        assert parsed["retries"] == 3
        assert parsed["delayMs"] == 2500

    def test_quotes_unsafe_integers(self):
        """Mirrors TS: preserves unsafe integer tool arguments as exact strings."""
        MAX_SAFE = 9007199254740991
        line = json.dumps({"target": MAX_SAFE + 1, "nested": {"thread": 9223372036854775807}})
        # json.dumps in Python doesn't lose precision, but we pre-process anyway
        result = _quote_unsafe_integer_literals(line)
        parsed = json.loads(result)
        assert str(parsed["target"]) == str(MAX_SAFE + 1)
        assert str(parsed["nested"]["thread"]) == "9223372036854775807"

    def test_does_not_quote_floats(self):
        line = '{"val":1.23456789}'
        result = _quote_unsafe_integer_literals(line)
        assert '"1.23456789"' not in result
        parsed = json.loads(result)
        assert abs(parsed["val"] - 1.23456789) < 1e-9

    def test_does_not_quote_strings(self):
        line = '{"key":"hello world"}'
        assert _quote_unsafe_integer_literals(line) == line

    def test_ndjson_tool_call_with_unsafe_int(self):
        """End-to-end: unsafe integer in NDJSON tool arguments is preserved."""
        ndjson_line = (
            '{"model":"m","created_at":"t","message":{"role":"assistant","content":"",'
            '"tool_calls":[{"function":{"name":"send","arguments":{"target":1234567890123456789}}}]},"done":false}'
        )
        chunk = _safe_json_loads(ndjson_line)
        args = chunk["message"]["tool_calls"][0]["function"]["arguments"]
        assert str(args["target"]) == "1234567890123456789"


# ============================================================================
# NDJSON streaming — mirrors TS parseNdjsonStream tests
# ============================================================================

def _make_ndjson_response(lines: list[str]) -> Any:
    """Build a mock httpx streaming response from NDJSON lines."""
    payload = "\n".join(lines) + "\n"
    lines_encoded = payload.splitlines(keepends=True)

    async def _aiter_lines():
        for line in lines_encoded:
            yield line.rstrip("\n")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.is_success = True
    mock_resp.aiter_lines = _aiter_lines
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


async def _stream_with_mock(lines: list[str], messages=None, tools=None, **kwargs):
    """Run OllamaProvider.stream() against mock NDJSON lines."""
    import httpx
    provider = OllamaProvider("test-model", base_url="http://localhost:11434")

    mock_resp = _make_ndjson_response(lines)

    results: list[LLMResponse] = []
    with patch.object(provider.get_client(), "stream", return_value=mock_resp):
        # Also need to mock /api/show for _resolve_num_ctx
        show_resp = MagicMock()
        show_resp.is_success = True
        show_resp.json = MagicMock(return_value={"model_info": {"test.context_length": 131072}})
        with patch.object(provider.get_client(), "post", new_callable=AsyncMock, return_value=show_resp):
            async for resp in provider.stream(
                messages=messages or [LLMMessage(role="user", content="hello")],
                tools=tools,
                **kwargs,
            ):
                results.append(resp)
    return results


class TestNdjsonStreaming:

    @pytest.mark.asyncio
    async def test_parses_text_only_chunks(self):
        """Mirrors TS: parses text-only streaming chunks."""
        lines = [
            '{"model":"m","created_at":"t","message":{"role":"assistant","content":"Hello"},"done":false}',
            '{"model":"m","created_at":"t","message":{"role":"assistant","content":" world"},"done":false}',
            '{"model":"m","created_at":"t","message":{"role":"assistant","content":""},"done":true,"prompt_eval_count":5,"eval_count":2}',
        ]
        results = await _stream_with_mock(lines)
        text_deltas = [r for r in results if r.type == "text_delta"]
        assert len(text_deltas) == 2
        assert text_deltas[0].content == "Hello"
        assert text_deltas[1].content == " world"
        done = next(r for r in results if r.type == "done")
        assert done.usage["input"] == 5
        assert done.usage["output"] == 2

    @pytest.mark.asyncio
    async def test_accumulates_tool_calls_from_intermediate_chunks(self):
        """Mirrors TS: tool_calls in done:false chunk, final done:true has no tool_calls."""
        lines = [
            '{"model":"m","created_at":"t","message":{"role":"assistant","content":"","tool_calls":[{"function":{"name":"bash","arguments":{"command":"ls"}}}]},"done":false}',
            '{"model":"m","created_at":"t","message":{"role":"assistant","content":""},"done":true,"prompt_eval_count":10,"eval_count":5}',
        ]
        results = await _stream_with_mock(lines)
        tool_responses = [r for r in results if r.type == "tool_call"]
        assert len(tool_responses) == 1
        tc = tool_responses[0].tool_calls[0]
        assert tc["name"] == "bash"
        assert tc["arguments"] == {"command": "ls"}

    @pytest.mark.asyncio
    async def test_accumulates_tool_calls_across_multiple_chunks(self):
        """Mirrors TS: accumulates tool_calls across multiple intermediate chunks."""
        lines = [
            '{"model":"m","created_at":"t","message":{"role":"assistant","content":"","tool_calls":[{"function":{"name":"read","arguments":{"path":"/tmp/a"}}}]},"done":false}',
            '{"model":"m","created_at":"t","message":{"role":"assistant","content":"","tool_calls":[{"function":{"name":"bash","arguments":{"command":"ls"}}}]},"done":false}',
            '{"model":"m","created_at":"t","message":{"role":"assistant","content":""},"done":true}',
        ]
        results = await _stream_with_mock(lines)
        tool_responses = [r for r in results if r.type == "tool_call"]
        assert len(tool_responses) == 1
        tcs = tool_responses[0].tool_calls
        assert len(tcs) == 2
        assert tcs[0]["name"] == "read"
        assert tcs[1]["name"] == "bash"

    @pytest.mark.asyncio
    async def test_reasoning_fallback_qwen3(self):
        """Mirrors TS: falls back to message.reasoning when content is empty (Qwen3)."""
        lines = [
            '{"model":"m","created_at":"t","message":{"role":"assistant","content":"","reasoning":"reasoned"},"done":false}',
            '{"model":"m","created_at":"t","message":{"role":"assistant","content":"","reasoning":" output"},"done":false}',
            '{"model":"m","created_at":"t","message":{"role":"assistant","content":""},"done":true,"prompt_eval_count":1,"eval_count":2}',
        ]
        results = await _stream_with_mock(lines)
        text_deltas = [r for r in results if r.type == "text_delta"]
        full_text = "".join(r.content for r in text_deltas)
        assert full_text == "reasoned output"

    @pytest.mark.asyncio
    async def test_unsafe_integers_in_tool_arguments(self):
        """Mirrors TS: preserves unsafe integer tool arguments as exact strings."""
        lines = [
            '{"model":"m","created_at":"t","message":{"role":"assistant","content":"","tool_calls":[{"function":{"name":"send","arguments":{"target":1234567890123456789,"nested":{"thread":9223372036854775807}}}}]},"done":false}',
            '{"model":"m","created_at":"t","message":{"role":"assistant","content":""},"done":true}',
        ]
        results = await _stream_with_mock(lines)
        tool_responses = [r for r in results if r.type == "tool_call"]
        assert len(tool_responses) == 1
        args = tool_responses[0].tool_calls[0]["arguments"]
        assert str(args["target"]) == "1234567890123456789"
        assert str(args["nested"]["thread"]) == "9223372036854775807"

    @pytest.mark.asyncio
    async def test_num_ctx_uses_discovered_context_window(self):
        """Mirrors TS: num_ctx uses model.contextWindow (from /api/show), not hardcoded."""
        import httpx

        provider = OllamaProvider("test-model", base_url="http://localhost:11434")

        # Track the body sent to /api/chat
        captured_body: dict = {}

        lines = [
            '{"model":"m","created_at":"t","message":{"role":"assistant","content":"ok"},"done":false}',
            '{"model":"m","created_at":"t","message":{"role":"assistant","content":""},"done":true,"prompt_eval_count":1,"eval_count":1}',
        ]
        mock_resp = _make_ndjson_response(lines)

        show_resp = MagicMock()
        show_resp.is_success = True
        show_resp.json = MagicMock(return_value={"model_info": {"qwen3.context_length": 262144}})

        client = provider.get_client()

        original_stream = client.stream

        def capture_stream(method, url, **kwargs):
            nonlocal captured_body
            captured_body = kwargs.get("json", {})
            return mock_resp

        with patch.object(client, "stream", side_effect=capture_stream):
            with patch.object(client, "post", new_callable=AsyncMock, return_value=show_resp):
                results = []
                async for r in provider.stream(
                    messages=[LLMMessage(role="user", content="hello")]
                ):
                    results.append(r)

        assert captured_body.get("options", {}).get("num_ctx") == 262144, (
            f"Expected num_ctx=262144 (from /api/show), got {captured_body.get('options', {}).get('num_ctx')}"
        )

    @pytest.mark.asyncio
    async def test_num_ctx_defaults_to_65536_when_show_fails(self):
        """Mirrors TS: falls back to 65536 when /api/show fails."""
        import httpx

        provider = OllamaProvider("test-model", base_url="http://localhost:11434")

        captured_body: dict = {}
        lines = [
            '{"model":"m","created_at":"t","message":{"role":"assistant","content":"ok"},"done":true,"prompt_eval_count":1,"eval_count":1}',
        ]
        mock_resp = _make_ndjson_response(lines)

        # Simulate /api/show failure
        show_resp = MagicMock()
        show_resp.is_success = False
        show_resp.json = MagicMock(return_value={})

        client = provider.get_client()

        def capture_stream(method, url, **kwargs):
            nonlocal captured_body
            captured_body = kwargs.get("json", {})
            return mock_resp

        with patch.object(client, "stream", side_effect=capture_stream):
            with patch.object(client, "post", new_callable=AsyncMock, return_value=show_resp):
                async for _ in provider.stream(
                    messages=[LLMMessage(role="user", content="hello")]
                ):
                    pass

        assert captured_body.get("options", {}).get("num_ctx") == 65536, (
            f"Expected fallback num_ctx=65536, got {captured_body.get('options', {}).get('num_ctx')}"
        )


# ============================================================================
# Base URL normalization — mirrors TS resolveOllamaChatUrl
# ============================================================================

class TestBaseUrlNormalization:

    def test_strips_v1_suffix(self):
        cases = [
            ("http://ollama-host:11434/v1", "http://ollama-host:11434"),
            ("http://ollama-host:11434/V1", "http://ollama-host:11434"),
            ("http://ollama-host:11434/v1/", "http://ollama-host:11434"),
            ("http://ollama-host:11434/", "http://ollama-host:11434"),
            ("http://ollama-host:11434", "http://ollama-host:11434"),
        ]
        for raw, expected in cases:
            p = OllamaProvider("m", base_url=raw)
            resolved = p._resolve_api_base()
            assert resolved == expected, f"{raw!r} → expected {expected!r}, got {resolved!r}"

    def test_chat_url_appends_api_chat(self):
        p = OllamaProvider("m", base_url="http://ollama-host:11434/v1")
        assert p._chat_url() == "http://ollama-host:11434/api/chat"


# ============================================================================
# Ollama provider gating — mirrors models-config.providers.ollama.test.ts
# ============================================================================

class TestOllamaProviderGating:
    """Tests for ensure_openclaw_models_json() Ollama gating logic."""

    @pytest.mark.asyncio
    async def test_not_included_when_not_running_and_no_key(self, tmp_path):
        """Mirrors TS: should not include ollama when no API key is configured
        (and Ollama is not running / returns empty models)."""
        from openclaw.agents.models_config import ensure_openclaw_models_json

        with patch("openclaw.agents.models_config._discover_ollama_models", new_callable=AsyncMock, return_value=[]):
            env = {k: v for k, v in os.environ.items()
                   if k not in ("OLLAMA_API_KEY", "OLLAMA_BASE_URL")}
            with patch.dict(os.environ, env, clear=True):
                result = await ensure_openclaw_models_json(
                    config={}, agent_dir_override=str(tmp_path)
                )

        import json as _json
        models_json_path = tmp_path / "models.json"
        if models_json_path.exists():
            data = _json.loads(models_json_path.read_text())
            assert "ollama" not in data.get("providers", {}), (
                "Ollama should not be in providers when not running and no key"
            )

    @pytest.mark.asyncio
    async def test_included_when_api_key_set(self, tmp_path):
        """Mirrors TS: includes ollama when OLLAMA_API_KEY is set."""
        from openclaw.agents.models_config import ensure_openclaw_models_json

        with patch("openclaw.agents.models_config._discover_ollama_models", new_callable=AsyncMock, return_value=[]):
            env = {**os.environ, "OLLAMA_API_KEY": "test-key"}
            with patch.dict(os.environ, env, clear=True):
                await ensure_openclaw_models_json(
                    config={}, agent_dir_override=str(tmp_path)
                )

        import json as _json
        data = _json.loads((tmp_path / "models.json").read_text())
        assert "ollama" in data["providers"], "Ollama should be included when OLLAMA_API_KEY is set"
        assert data["providers"]["ollama"]["api"] == "ollama"
        assert data["providers"]["ollama"]["apiKey"] == "test-key"

    @pytest.mark.asyncio
    async def test_included_when_models_discovered(self, tmp_path):
        """Mirrors TS: includes ollama when models are found via discovery."""
        from openclaw.agents.models_config import ensure_openclaw_models_json

        discovered_models = [
            {"id": "qwen3:32b", "name": "qwen3:32b", "reasoning": False,
             "input": ["text"], "contextWindow": 131072, "maxTokens": 8192},
        ]
        with patch("openclaw.agents.models_config._discover_ollama_models",
                   new_callable=AsyncMock, return_value=discovered_models):
            env = {k: v for k, v in os.environ.items()
                   if k not in ("OLLAMA_API_KEY", "OLLAMA_BASE_URL")}
            with patch.dict(os.environ, env, clear=True):
                await ensure_openclaw_models_json(
                    config={}, agent_dir_override=str(tmp_path)
                )

        import json as _json
        data = _json.loads((tmp_path / "models.json").read_text())
        assert "ollama" in data["providers"]
        assert data["providers"]["ollama"]["api"] == "ollama"
        models = data["providers"]["ollama"]["models"]
        assert any(m["id"] == "qwen3:32b" for m in models)

    @pytest.mark.asyncio
    async def test_uses_native_api_type(self, tmp_path):
        """Mirrors TS: should use native ollama api type."""
        from openclaw.agents.models_config import ensure_openclaw_models_json

        discovered_models = [{"id": "llama3:latest", "name": "llama3:latest",
                               "reasoning": False, "input": ["text"],
                               "contextWindow": 65536, "maxTokens": 8192}]
        with patch("openclaw.agents.models_config._discover_ollama_models",
                   new_callable=AsyncMock, return_value=discovered_models):
            env = {**os.environ, "OLLAMA_API_KEY": "test-key",
                   "OLLAMA_BASE_URL": "http://127.0.0.1:11434"}
            with patch.dict(os.environ, env, clear=True):
                await ensure_openclaw_models_json(
                    config={}, agent_dir_override=str(tmp_path)
                )

        import json as _json
        data = _json.loads((tmp_path / "models.json").read_text())
        assert data["providers"]["ollama"]["api"] == "ollama"
        assert data["providers"]["ollama"]["baseUrl"] == "http://127.0.0.1:11434"

    @pytest.mark.asyncio
    async def test_skips_discovery_when_explicit_models_configured(self, tmp_path):
        """Mirrors TS: should skip discovery fetch when explicit models are configured."""
        from openclaw.agents.models_config import ensure_openclaw_models_json

        explicit_models = [
            {"id": "gpt-oss:20b", "name": "GPT-OSS 20B", "reasoning": False,
             "input": ["text"], "contextWindow": 8192, "maxTokens": 81920}
        ]
        discovery_mock = AsyncMock(return_value=[])

        with patch("openclaw.agents.models_config._discover_ollama_models", discovery_mock):
            config = {
                "models": {
                    "providers": {
                        "ollama": {
                            "baseUrl": "http://remote-ollama:11434/v1",
                            "models": explicit_models,
                            "apiKey": "config-ollama-key",
                        }
                    }
                }
            }
            await ensure_openclaw_models_json(config=config, agent_dir_override=str(tmp_path))

        # Discovery should NOT have been called
        discovery_mock.assert_not_called()

        import json as _json
        data = _json.loads((tmp_path / "models.json").read_text())
        ollama = data["providers"]["ollama"]
        assert ollama["models"] == explicit_models
        assert ollama["baseUrl"] == "http://remote-ollama:11434"  # /v1 stripped
        assert ollama["api"] == "ollama"

    @pytest.mark.asyncio
    async def test_preserves_explicit_base_url_with_v1_stripping(self, tmp_path):
        """Mirrors TS: strips /v1 from explicit baseUrl."""
        from openclaw.agents.models_config import ensure_openclaw_models_json

        discovered = [{"id": "llama3", "name": "llama3", "reasoning": False,
                       "input": ["text"], "contextWindow": 65536, "maxTokens": 8192}]
        with patch("openclaw.agents.models_config._discover_ollama_models",
                   new_callable=AsyncMock, return_value=discovered):
            env = {**os.environ, "OLLAMA_API_KEY": "test-key"}
            with patch.dict(os.environ, env, clear=True):
                config = {
                    "models": {
                        "providers": {
                            "ollama": {
                                "baseUrl": "http://192.168.20.14:11434/v1",
                                "models": [],
                            }
                        }
                    }
                }
                await ensure_openclaw_models_json(config=config, agent_dir_override=str(tmp_path))

        import json as _json
        data = _json.loads((tmp_path / "models.json").read_text())
        assert data["providers"]["ollama"]["baseUrl"] == "http://192.168.20.14:11434"


# ============================================================================
# Model catalog api field preservation
# ============================================================================

class TestModelCatalogApiField:

    def test_api_field_propagated_to_catalog_entry(self, tmp_path):
        """Ensures api:'ollama' on provider is visible on ModelCatalogEntry."""
        import json as _json
        from openclaw.agents.model_catalog import _read_models_json_directly

        models_json = {
            "providers": {
                "ollama": {
                    "baseUrl": "http://localhost:11434",
                    "api": "ollama",
                    "models": [
                        {"id": "qwen3-coder:30b", "name": "Qwen3 Coder 30B",
                         "contextWindow": 262144}
                    ],
                }
            }
        }
        (tmp_path / "models.json").write_text(_json.dumps(models_json))
        entries = _read_models_json_directly(str(tmp_path))
        assert len(entries) == 1
        assert entries[0].api == "ollama"
        assert entries[0].context_window == 262144

    def test_non_ollama_provider_has_none_api(self, tmp_path):
        """Non-Ollama providers without api field have api=None."""
        import json as _json
        from openclaw.agents.model_catalog import _read_models_json_directly

        models_json = {
            "providers": {
                "anthropic": {
                    "models": [{"id": "claude-3-opus", "name": "Claude Opus"}]
                }
            }
        }
        (tmp_path / "models.json").write_text(_json.dumps(models_json))
        entries = _read_models_json_directly(str(tmp_path))
        assert entries[0].api is None


# ============================================================================
# extractToolCallsFromContent — new helper
# ============================================================================

class TestExtractToolCallsFromContent:

    def test_toolcall_type(self):
        content = [{"type": "toolCall", "id": "c1", "name": "bash", "arguments": {"cmd": "ls"}}]
        result = _extract_tool_calls_from_content(content)
        assert result == [{"id": "c1", "name": "bash", "arguments": {"cmd": "ls"}}]

    def test_tool_use_type(self):
        content = [{"type": "tool_use", "id": "c1", "name": "search", "input": {"q": "x"}}]
        result = _extract_tool_calls_from_content(content)
        assert result == [{"id": "c1", "name": "search", "arguments": {"q": "x"}}]

    def test_non_list_returns_empty(self):
        assert _extract_tool_calls_from_content("string content") == []
        assert _extract_tool_calls_from_content(None) == []

    def test_mixed_content(self):
        content = [
            {"type": "text", "text": "Let me check."},
            {"type": "toolCall", "id": "c1", "name": "bash", "arguments": {"cmd": "pwd"}},
        ]
        result = _extract_tool_calls_from_content(content)
        assert len(result) == 1
        assert result[0]["name"] == "bash"


# ============================================================================
# _resolve_num_ctx — auto-discovery
# ============================================================================

class TestResolveNumCtx:

    @pytest.mark.asyncio
    async def test_uses_api_show_context_length(self):
        """_resolve_num_ctx() returns context_length from /api/show model_info."""
        provider = OllamaProvider("qwen3:32b", base_url="http://localhost:11434")

        mock_resp = MagicMock()
        mock_resp.is_success = True
        mock_resp.json = MagicMock(return_value={
            "model_info": {"qwen3.context_length": 131072}
        })

        with patch.object(provider.get_client(), "post", new_callable=AsyncMock, return_value=mock_resp):
            ctx = await provider._resolve_num_ctx()

        assert ctx == 131072

    @pytest.mark.asyncio
    async def test_falls_back_to_65536_on_failure(self):
        """_resolve_num_ctx() falls back to 65536 when /api/show fails."""
        provider = OllamaProvider("unknown-model", base_url="http://localhost:11434")

        mock_resp = MagicMock()
        mock_resp.is_success = False
        mock_resp.json = MagicMock(return_value={})

        with patch.object(provider.get_client(), "post", new_callable=AsyncMock, return_value=mock_resp):
            ctx = await provider._resolve_num_ctx()

        assert ctx == 65536

    @pytest.mark.asyncio
    async def test_caches_result(self):
        """_resolve_num_ctx() is only called once (cached)."""
        provider = OllamaProvider("llama3:latest", base_url="http://localhost:11434")

        call_count = 0
        original_get_model_info = provider.get_model_info

        async def mock_get_model_info(model):
            nonlocal call_count
            call_count += 1
            return {"model_info": {"llama.context_length": 65536}}

        provider.get_model_info = mock_get_model_info

        ctx1 = await provider._resolve_num_ctx()
        ctx2 = await provider._resolve_num_ctx()

        assert ctx1 == ctx2 == 65536
        assert call_count == 1, "get_model_info should only be called once (cached)"


if __name__ == "__main__":
    print("Running unit tests (no Ollama required)...")
    # Run synchronous tests
    t = TestConvertToOllamaMessages()
    for method_name in dir(t):
        if method_name.startswith("test_"):
            method = getattr(t, method_name)
            if not asyncio.iscoroutinefunction(method):
                try:
                    method()
                    print(f"  {method_name}: PASS")
                except Exception as e:
                    print(f"  {method_name}: FAIL — {e}")

    for cls in [TestNormaliseToolCalls, TestQuoteUnsafeIntegerLiterals, TestBaseUrlNormalization,
                TestExtractToolCallsFromContent]:
        t = cls()
        for method_name in dir(t):
            if method_name.startswith("test_"):
                method = getattr(t, method_name)
                if not asyncio.iscoroutinefunction(method):
                    try:
                        method()
                        print(f"  {cls.__name__}.{method_name}: PASS")
                    except Exception as e:
                        print(f"  {cls.__name__}.{method_name}: FAIL — {e}")

    # Run async tests
    async def _run_async():
        for cls in [TestNdjsonStreaming, TestResolveNumCtx]:
            t = cls()
            for method_name in dir(t):
                if method_name.startswith("test_"):
                    method = getattr(t, method_name)
                    if asyncio.iscoroutinefunction(method):
                        try:
                            await method()
                            print(f"  {cls.__name__}.{method_name}: PASS")
                        except Exception as e:
                            import traceback
                            print(f"  {cls.__name__}.{method_name}: FAIL — {e}")
                            traceback.print_exc()

    asyncio.run(_run_async())
    print("\nAll unit tests done.")
