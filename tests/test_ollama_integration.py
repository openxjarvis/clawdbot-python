"""End-to-end integration tests for Ollama support.

Tests the full Ollama pipeline with a locally running Ollama instance.

Requirements:
  - Ollama running at http://localhost:11434 (or OLLAMA_BASE_URL)
  - qwen3.5:35b pulled (or another available model)

Run with:
  pytest tests/test_ollama_integration.py -v -s

Marks:
  - @pytest.mark.integration — skipped unless OLLAMA_INTEGRATION=1
"""
from __future__ import annotations

import asyncio
import json
import os
import pytest
import sys

# Allow running directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
# Preferred model for testing; falls back to first available model if not installed.
_PREFERRED_TEST_MODEL = os.environ.get("OLLAMA_TEST_MODEL", "qwen3.5:35b")
SKIP_REASON = (
    "Set OLLAMA_INTEGRATION=1 to run Ollama integration tests "
    "(requires local Ollama)"
)
RUN_INTEGRATION = os.environ.get("OLLAMA_INTEGRATION") == "1"


def _resolve_test_model() -> str:
    """Return OLLAMA_TEST_MODEL if installed, else first available model."""
    import httpx
    try:
        resp = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3.0)
        if resp.is_success:
            models = [m.get("name", "") for m in (resp.json().get("models") or [])]
            if _PREFERRED_TEST_MODEL in models:
                return _PREFERRED_TEST_MODEL
            # Prefer a qwen or llama model for tool-calling support
            for preferred in ("qwen3-coder:30b", "qwen3-vl:32b", "llama3.3:latest"):
                if preferred in models:
                    return preferred
            if models:
                return models[0]
    except Exception:
        pass
    return _PREFERRED_TEST_MODEL


OLLAMA_TEST_MODEL: str = _resolve_test_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_provider():
    from openclaw.agents.providers.ollama_provider import OllamaProvider
    return OllamaProvider(model=OLLAMA_TEST_MODEL, base_url=OLLAMA_BASE_URL)


async def _collect_stream(provider, messages, tools=None, **kwargs):
    """Drain the stream, return (text, tool_calls, usage)."""
    text_parts = []
    tool_calls = []
    usage = None
    async for resp in provider.stream(messages, tools=tools, **kwargs):
        if resp.type == "text_delta" and resp.content:
            text_parts.append(resp.content)
        elif resp.type == "tool_call" and resp.tool_calls:
            tool_calls.extend(resp.tool_calls)
        elif resp.type == "done":
            usage = resp.usage
        elif resp.type == "error":
            pytest.fail(f"Ollama stream error: {resp.content}")
    return "".join(text_parts), tool_calls, usage


# ---------------------------------------------------------------------------
# Test: model discovery
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.skipif(not RUN_INTEGRATION, reason=SKIP_REASON)
async def test_ollama_model_discovery():
    """_discover_ollama_models returns at least one model."""
    from openclaw.agents.models_config import _discover_ollama_models

    models = await _discover_ollama_models(OLLAMA_BASE_URL, quiet=False)

    assert isinstance(models, list), "Should return a list"
    assert len(models) > 0, "Should find at least one model"

    # Each entry has expected fields
    for m in models:
        assert "id" in m, f"Model entry missing 'id': {m}"
        assert "name" in m
        assert "contextWindow" in m
        assert isinstance(m["contextWindow"], int) and m["contextWindow"] > 0

    model_ids = [m["id"] for m in models]
    print(f"\nDiscovered {len(models)} Ollama models: {model_ids}")
    print(f"Using test model: {OLLAMA_TEST_MODEL}")
    # At least one model should be present
    assert len(model_ids) > 0, "Should discover at least one model"


@pytest.mark.asyncio
@pytest.mark.skipif(not RUN_INTEGRATION, reason=SKIP_REASON)
async def test_ollama_model_discovery_context_window():
    """Model discovery extracts non-default context windows via /api/show."""
    from openclaw.agents.models_config import _discover_ollama_models

    models = await _discover_ollama_models(OLLAMA_BASE_URL, quiet=True)
    target = next((m for m in models if OLLAMA_TEST_MODEL in m["id"]), None)
    if target is None:
        msg = f"{OLLAMA_TEST_MODEL} not installed — skipping context_window check"
        if "pytest" in sys.modules and hasattr(pytest, "skip"):
            pytest.skip(msg)
        else:
            print(f"  SKIP: {msg}")
            return

    ctx = target["contextWindow"]
    print(f"\n{OLLAMA_TEST_MODEL} context window: {ctx}")
    # qwen3.5:35b has a large context window; it should not be 0
    assert ctx > 0, "Context window should be positive"


# ---------------------------------------------------------------------------
# Test: OllamaProvider — connection check
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.skipif(not RUN_INTEGRATION, reason=SKIP_REASON)
async def test_ollama_connection():
    """OllamaProvider.check_connection() returns True when Ollama is running."""
    provider = _get_provider()
    try:
        connected = await provider.check_connection()
        assert connected, "Ollama should be reachable"
    finally:
        await provider.get_client().aclose()


# ---------------------------------------------------------------------------
# Test: text streaming
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.skipif(not RUN_INTEGRATION, reason=SKIP_REASON)
async def test_ollama_text_streaming():
    """Stream a simple text response; should yield text_delta chunks."""
    from openclaw.agents.providers.base import LLMMessage

    provider = _get_provider()
    try:
        messages = [
            LLMMessage(role="user", content="Reply with exactly the word: PONG"),
        ]
        text, tool_calls, usage = await _collect_stream(provider, messages, max_tokens=32)

        print(f"\nStreamed text: {text!r}")
        assert text.strip(), "Should have received some text"
        assert not tool_calls, "Should not have tool calls for plain text"
        assert usage is not None, "Should have usage stats"
        assert isinstance(usage.get("output"), int)
        print(f"Usage: {usage}")
    finally:
        await provider.get_client().aclose()


# ---------------------------------------------------------------------------
# Test: tool calling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.skipif(not RUN_INTEGRATION, reason=SKIP_REASON)
async def test_ollama_tool_calling():
    """Verify that the model uses a tool when explicitly asked.

    Uses a simple 'get_weather' stub tool — the model should call it
    rather than hallucinate a weather report.
    """
    from openclaw.agents.providers.base import LLMMessage

    provider = _get_provider()
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the current weather for a given city.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "The city name",
                        }
                    },
                    "required": ["city"],
                },
            },
        }
    ]

    messages = [
        LLMMessage(
            role="user",
            content="What is the weather in Tokyo? Use the get_weather tool.",
        )
    ]

    try:
        text, tool_calls, usage = await _collect_stream(provider, messages, tools=tools, max_tokens=256)

        print(f"\nText: {text!r}")
        print(f"Tool calls: {tool_calls}")

        assert len(tool_calls) > 0, (
            f"Expected at least one tool call but got none. Text: {text!r}"
        )
        tc = tool_calls[0]
        assert tc.get("name") == "get_weather", f"Expected 'get_weather', got {tc.get('name')!r}"
        args = tc.get("arguments") or tc.get("params") or {}
        assert "city" in args, f"Expected 'city' in tool call arguments: {args}"
        print(f"Tool call args: {args}")
    finally:
        await provider.get_client().aclose()


# ---------------------------------------------------------------------------
# Test: tool result in messages
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.skipif(not RUN_INTEGRATION, reason=SKIP_REASON)
async def test_ollama_tool_result_message():
    """Verify multi-turn: tool call → tool result → final text answer."""
    from openclaw.agents.providers.base import LLMMessage

    provider = _get_provider()
    tools = [
        {
            "type": "function",
            "function": {
                "name": "add_numbers",
                "description": "Add two numbers together.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "a": {"type": "number"},
                        "b": {"type": "number"},
                    },
                    "required": ["a", "b"],
                },
            },
        }
    ]

    messages = [
        LLMMessage(role="user", content="What is 17 + 25? Use the add_numbers tool."),
    ]

    try:
        # Turn 1: get the tool call
        text, tool_calls, _ = await _collect_stream(provider, messages, tools=tools, max_tokens=128)
        print(f"\nTurn 1 text: {text!r}, tool_calls: {tool_calls}")

        if not tool_calls:
            pytest.skip("Model did not emit a tool call — skipping multi-turn test")

        tc = tool_calls[0]

        # Add assistant message with tool call + tool result message
        messages_turn2 = messages + [
            LLMMessage(
                role="assistant",
                content=text or "",
                tool_calls=tool_calls,
            ),
            LLMMessage(
                role="tool",
                content="42",
                tool_call_id=tc.get("id", "call_1"),
                name=tc.get("name", "add_numbers"),
            ),
        ]

        # Turn 2: get the final answer
        text2, tool_calls2, usage2 = await _collect_stream(
            provider, messages_turn2, tools=tools, max_tokens=128
        )
        print(f"Turn 2 text: {text2!r}")

        assert "42" in text2, f"Expected '42' in final answer: {text2!r}"
    finally:
        await provider.get_client().aclose()


# ---------------------------------------------------------------------------
# Test: unsafe integer quoting
# ---------------------------------------------------------------------------

def test_quote_unsafe_integer_literals():
    """_quote_unsafe_integer_literals rounds-trip large integers safely."""
    from openclaw.agents.providers.ollama_provider import _quote_unsafe_integer_literals, _safe_json_loads

    MAX_SAFE = 9007199254740991

    # Should NOT quote safe integers
    safe_line = '{"id": 12345}'
    assert _quote_unsafe_integer_literals(safe_line) == safe_line

    # Should quote integers > MAX_SAFE_INTEGER
    large_id = MAX_SAFE + 1
    unsafe_line = f'{{"chat_id": {large_id}}}'
    quoted = _quote_unsafe_integer_literals(unsafe_line)
    print(f"\nUnsafe input: {unsafe_line}")
    print(f"Quoted output: {quoted}")

    # The large int should be quoted as string in output
    assert f'"{large_id}"' in quoted, f"Expected quoted integer in: {quoted}"

    # json.loads should now parse it as a string (not lose precision)
    parsed = _safe_json_loads(unsafe_line)
    assert str(parsed["chat_id"]) == str(large_id)

    # Strings should not be double-quoted
    string_line = '{"key": "hello world"}'
    assert _quote_unsafe_integer_literals(string_line) == string_line

    # Floats should not be quoted
    float_line = '{"val": 1.23456789012345678}'
    result = _quote_unsafe_integer_literals(float_line)
    assert '"1.23456789012345678"' not in result, "Floats should not be quoted"


# ---------------------------------------------------------------------------
# Test: base URL normalisation
# ---------------------------------------------------------------------------

def test_base_url_normalization():
    """OllamaProvider._resolve_api_base() strips /v1 suffix."""
    from openclaw.agents.providers.ollama_provider import OllamaProvider

    cases = [
        ("http://localhost:11434", "http://localhost:11434"),
        ("http://localhost:11434/", "http://localhost:11434"),
        ("http://localhost:11434/v1", "http://localhost:11434"),
        ("http://localhost:11434/V1", "http://localhost:11434"),
        ("http://192.168.1.100:11434/v1", "http://192.168.1.100:11434"),
        ("http://192.168.1.100:11434/v1/", "http://192.168.1.100:11434"),
    ]
    for raw, expected in cases:
        p = OllamaProvider("test-model", base_url=raw)
        resolved = p._resolve_api_base()
        assert resolved == expected, f"For input {raw!r}, expected {expected!r}, got {resolved!r}"


# ---------------------------------------------------------------------------
# Test: message format conversion
# ---------------------------------------------------------------------------

def test_format_messages_user():
    """_format_messages converts user messages correctly."""
    from openclaw.agents.providers.base import LLMMessage
    from openclaw.agents.providers.ollama_provider import OllamaProvider

    p = OllamaProvider("test")
    msgs = [LLMMessage(role="user", content="Hello")]
    result = p._format_messages(msgs)
    assert result == [{"role": "user", "content": "Hello"}]


def test_format_messages_tool_result():
    """_format_messages converts tool result messages to Ollama format."""
    from openclaw.agents.providers.base import LLMMessage
    from openclaw.agents.providers.ollama_provider import OllamaProvider

    p = OllamaProvider("test")
    msgs = [
        LLMMessage(
            role="tool",
            content="42",
            tool_call_id="call_abc",
            name="add_numbers",
        )
    ]
    result = p._format_messages(msgs)
    assert result == [{"role": "tool", "content": "42", "tool_name": "add_numbers"}]


def test_format_messages_assistant_with_tool_calls():
    """_format_messages converts assistant+tool_calls to Ollama format."""
    from openclaw.agents.providers.base import LLMMessage
    from openclaw.agents.providers.ollama_provider import OllamaProvider

    p = OllamaProvider("test")
    tool_calls = [{"name": "my_tool", "arguments": {"x": 1}}]
    msgs = [
        LLMMessage(role="assistant", content="", tool_calls=tool_calls)
    ]
    result = p._format_messages(msgs)
    assert len(result) == 1
    entry = result[0]
    assert entry["role"] == "assistant"
    assert "tool_calls" in entry
    assert entry["tool_calls"][0]["function"]["name"] == "my_tool"


def test_format_tools():
    """_format_tools converts OpenAI-style tools to Ollama format."""
    from openclaw.agents.providers.ollama_provider import OllamaProvider

    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]
    result = OllamaProvider._format_tools(tools)
    assert len(result) == 1
    assert result[0]["type"] == "function"
    assert result[0]["function"]["name"] == "get_weather"


# ---------------------------------------------------------------------------
# Test: catalog api field preservation
# ---------------------------------------------------------------------------

def test_model_catalog_entry_api_field():
    """ModelCatalogEntry exposes api field; _read_models_json_directly preserves it."""
    import json, tempfile, os
    from openclaw.agents.model_catalog import ModelCatalogEntry, _read_models_json_directly

    models_json = {
        "providers": {
            "ollama": {
                "baseUrl": "http://localhost:11434",
                "api": "ollama",
                "models": [
                    {"id": "llama3", "name": "Llama 3", "contextWindow": 131072}
                ],
            }
        }
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "models.json")
        with open(path, "w") as f:
            json.dump(models_json, f)

        entries = _read_models_json_directly(tmpdir)

    assert len(entries) == 1
    entry = entries[0]
    assert entry.id == "llama3"
    assert entry.provider == "ollama"
    assert entry.api == "ollama", f"Expected api='ollama', got {entry.api!r}"
    assert entry.context_window == 131072


# ---------------------------------------------------------------------------
# Run directly
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    os.environ.setdefault("OLLAMA_INTEGRATION", "1")

    async def _run_all():
        print("=== test_ollama_model_discovery ===")
        await test_ollama_model_discovery()
        print("=== test_ollama_model_discovery_context_window ===")
        await test_ollama_model_discovery_context_window()
        print("=== test_ollama_connection ===")
        await test_ollama_connection()
        print("=== test_ollama_text_streaming ===")
        await test_ollama_text_streaming()
        print("=== test_ollama_tool_calling ===")
        await test_ollama_tool_calling()
        print("=== test_ollama_tool_result_message ===")
        await test_ollama_tool_result_message()
        print("All integration tests passed!")

    # Unit tests (no Ollama required)
    print("=== Unit tests ===")
    test_quote_unsafe_integer_literals()
    print("  test_quote_unsafe_integer_literals: PASS")
    test_base_url_normalization()
    print("  test_base_url_normalization: PASS")
    test_format_messages_user()
    print("  test_format_messages_user: PASS")
    test_format_messages_tool_result()
    print("  test_format_messages_tool_result: PASS")
    test_format_messages_assistant_with_tool_calls()
    print("  test_format_messages_assistant_with_tool_calls: PASS")
    test_format_tools()
    print("  test_format_tools: PASS")
    test_model_catalog_entry_api_field()
    print("  test_model_catalog_entry_api_field: PASS")

    print("\n=== Integration tests (requires Ollama) ===")
    asyncio.run(_run_all())
