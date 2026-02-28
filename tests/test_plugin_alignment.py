"""Tests for OpenClaw Python plugin system alignment with TypeScript version.

Covers:
- Hook event/context/result dataclass field correctness
- Manifest loading (openclaw.plugin.json and plugin.json fallback)
- Plugin API registration methods (command, hook)
- Integration test: loading a sample extension (telegram/matrix)
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import fields
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Hook Event Types alignment
# ---------------------------------------------------------------------------

class TestHookEventTypes:
    """Verify all hook event/context/result dataclasses have the fields
    expected by the TypeScript alignment plan."""

    def test_llm_input_event_fields(self):
        from openclaw.plugins.types import PluginHookLlmInputEvent
        e = PluginHookLlmInputEvent(
            run_id="r1",
            session_id="s1",
            provider="anthropic",
            model="claude-opus-4-5",
            system_prompt="You are helpful.",
            prompt="Hello",
            history_messages=[{"role": "user", "content": "hi"}],
            images_count=2,
        )
        assert e.run_id == "r1"
        assert e.session_id == "s1"
        assert e.provider == "anthropic"
        assert e.model == "claude-opus-4-5"
        assert e.system_prompt == "You are helpful."
        assert e.prompt == "Hello"
        assert len(e.history_messages) == 1
        assert e.images_count == 2

    def test_llm_input_event_defaults(self):
        from openclaw.plugins.types import PluginHookLlmInputEvent
        e = PluginHookLlmInputEvent()
        assert e.run_id == ""
        assert e.session_id == ""
        assert e.provider == ""
        assert e.model == ""
        assert e.system_prompt is None
        assert e.prompt == ""
        assert e.history_messages == []
        assert e.images_count == 0

    def test_llm_output_event_fields(self):
        from openclaw.plugins.types import PluginHookLlmOutputEvent
        e = PluginHookLlmOutputEvent(
            run_id="r1",
            session_id="s1",
            provider="openai",
            model="gpt-4o",
            assistant_texts=["hello world"],
            last_assistant={"role": "assistant", "content": "hello world"},
            usage={"input_tokens": 10, "output_tokens": 5},
        )
        assert e.run_id == "r1"
        assert e.provider == "openai"
        assert e.assistant_texts == ["hello world"]
        assert e.usage["input_tokens"] == 10

    def test_agent_end_event_fields(self):
        from openclaw.plugins.types import PluginHookAgentEndEvent
        e = PluginHookAgentEndEvent(
            messages=[{"role": "assistant", "content": "done"}],
            success=True,
            error=None,
            duration_ms=1234,
        )
        assert e.messages[0]["role"] == "assistant"
        assert e.success is True
        assert e.error is None
        assert e.duration_ms == 1234

    def test_before_compaction_event_fields(self):
        from openclaw.plugins.types import PluginHookBeforeCompactionEvent
        e = PluginHookBeforeCompactionEvent(
            message_count=50,
            compacting_count=30,
            token_count=10000,
            messages=[],
            session_file="/path/session.jsonl",
        )
        assert e.message_count == 50
        assert e.compacting_count == 30
        assert e.token_count == 10000
        assert e.session_file == "/path/session.jsonl"

    def test_after_compaction_event_fields(self):
        from openclaw.plugins.types import PluginHookAfterCompactionEvent
        e = PluginHookAfterCompactionEvent(
            message_count=20,
            token_count=3000,
            compacted_count=30,
            session_file="/path/session.jsonl",
        )
        assert e.message_count == 20
        assert e.compacted_count == 30
        assert e.session_file == "/path/session.jsonl"

    def test_before_reset_event_fields(self):
        from openclaw.plugins.types import PluginHookBeforeResetEvent
        e = PluginHookBeforeResetEvent(
            session_file="/path/session.jsonl",
            messages=[],
            reason="user requested",
        )
        assert e.session_file == "/path/session.jsonl"
        assert e.reason == "user requested"

    def test_message_received_event_fields(self):
        from openclaw.plugins.types import PluginHookMessageReceivedEvent
        e = PluginHookMessageReceivedEvent(
            from_="alice",
            content="Hello bot!",
            timestamp=1700000000,
            metadata={"source": "telegram"},
        )
        assert e.from_ == "alice"
        assert e.content == "Hello bot!"
        assert e.timestamp == 1700000000
        assert e.metadata["source"] == "telegram"

    def test_message_sending_result_cancel(self):
        from openclaw.plugins.types import PluginHookMessageSendingResult
        r = PluginHookMessageSendingResult(cancel=True)
        assert r.cancel is True
        assert r.content is None

    def test_message_sent_event_fields(self):
        from openclaw.plugins.types import PluginHookMessageSentEvent
        e = PluginHookMessageSentEvent(
            to="telegram:+1234567890",
            content="reply text",
            success=True,
            error=None,
        )
        assert e.to == "telegram:+1234567890"
        assert e.success is True

    def test_before_tool_call_event_fields(self):
        from openclaw.plugins.types import PluginHookBeforeToolCallEvent
        e = PluginHookBeforeToolCallEvent(
            tool_name="bash",
            params={"command": "ls -la"},
        )
        assert e.tool_name == "bash"
        assert e.params["command"] == "ls -la"

    def test_after_tool_call_event_fields(self):
        from openclaw.plugins.types import PluginHookAfterToolCallEvent
        e = PluginHookAfterToolCallEvent(
            tool_name="bash",
            params={"command": "ls"},
            result="file.txt\ndir/",
            error=None,
            duration_ms=50,
        )
        assert e.tool_name == "bash"
        assert e.result == "file.txt\ndir/"
        assert e.duration_ms == 50

    def test_session_start_event_fields(self):
        from openclaw.plugins.types import PluginHookSessionStartEvent
        e = PluginHookSessionStartEvent(session_id="abc123", resumed_from="xyz456")
        assert e.session_id == "abc123"
        assert e.resumed_from == "xyz456"

    def test_session_end_event_fields(self):
        from openclaw.plugins.types import PluginHookSessionEndEvent
        e = PluginHookSessionEndEvent(session_id="abc123", message_count=10, duration_ms=5000)
        assert e.session_id == "abc123"
        assert e.message_count == 10
        assert e.duration_ms == 5000

    def test_gateway_start_event_fields(self):
        from openclaw.plugins.types import PluginHookGatewayStartEvent
        e = PluginHookGatewayStartEvent(port=8080)
        assert e.port == 8080

    def test_gateway_stop_event_fields(self):
        from openclaw.plugins.types import PluginHookGatewayStopEvent
        e = PluginHookGatewayStopEvent(reason="shutdown signal")
        assert e.reason == "shutdown signal"

    def test_agent_context_fields(self):
        from openclaw.plugins.types import PluginHookAgentContext
        ctx = PluginHookAgentContext(
            agent_id="main",
            session_key="agent:main:main",
            session_id="abc123",
            workspace_dir="/workspace",
            message_provider="telegram",
        )
        assert ctx.agent_id == "main"
        assert ctx.message_provider == "telegram"

    def test_gateway_context_fields(self):
        from openclaw.plugins.types import PluginHookGatewayContext
        ctx = PluginHookGatewayContext(port=8080)
        assert ctx.port == 8080

    def test_message_context_fields(self):
        from openclaw.plugins.types import PluginHookMessageContext
        ctx = PluginHookMessageContext(
            channel_id="telegram",
            account_id="default",
            conversation_id="+1234567890",
        )
        assert ctx.channel_id == "telegram"
        assert ctx.conversation_id == "+1234567890"

    def test_tool_context_fields(self):
        from openclaw.plugins.types import PluginHookToolContext
        ctx = PluginHookToolContext(
            agent_id="main",
            session_key="agent:main:main",
            tool_name="bash",
        )
        assert ctx.tool_name == "bash"

    def test_tool_result_persist_context_fields(self):
        from openclaw.plugins.types import PluginHookToolResultPersistContext
        ctx = PluginHookToolResultPersistContext(
            agent_id="main",
            session_key="agent:main:main",
            tool_name="bash",
            tool_call_id="call_abc123",
        )
        assert ctx.tool_call_id == "call_abc123"

    def test_before_model_resolve_event_has_prompt(self):
        from openclaw.plugins.types import PluginHookBeforeModelResolveEvent
        e = PluginHookBeforeModelResolveEvent(prompt="What is the weather?")
        assert e.prompt == "What is the weather?"

    def test_session_context_has_agent_id(self):
        from openclaw.plugins.types import PluginHookSessionContext
        ctx = PluginHookSessionContext(agent_id="main", session_id="abc123")
        assert ctx.agent_id == "main"
        assert ctx.session_id == "abc123"


# ---------------------------------------------------------------------------
# Manifest loading
# ---------------------------------------------------------------------------

class TestManifestLoading:
    """Tests for load_plugin_manifest with both filenames."""

    def _write_manifest(self, dir_path: str, filename: str, data: dict) -> None:
        path = os.path.join(dir_path, filename)
        with open(path, "w") as f:
            json.dump(data, f)

    def test_load_openclaw_plugin_json(self, tmp_path):
        from openclaw.plugins.manifest import load_plugin_manifest
        data = {
            "id": "test-plugin",
            "configSchema": {"type": "object", "additionalProperties": False, "properties": {}},
        }
        self._write_manifest(str(tmp_path), "openclaw.plugin.json", data)
        result = load_plugin_manifest(str(tmp_path))
        assert result.ok is True
        assert result.manifest.id == "test-plugin"
        assert result.manifest_path.endswith("openclaw.plugin.json")

    def test_load_plugin_json_fallback(self, tmp_path):
        from openclaw.plugins.manifest import load_plugin_manifest
        data = {
            "id": "fallback-plugin",
            "configSchema": {"type": "object", "additionalProperties": False, "properties": {}},
        }
        self._write_manifest(str(tmp_path), "plugin.json", data)
        result = load_plugin_manifest(str(tmp_path))
        assert result.ok is True
        assert result.manifest.id == "fallback-plugin"
        assert result.manifest_path.endswith("plugin.json")

    def test_openclaw_plugin_json_takes_precedence_over_plugin_json(self, tmp_path):
        from openclaw.plugins.manifest import load_plugin_manifest
        self._write_manifest(str(tmp_path), "openclaw.plugin.json", {
            "id": "primary",
            "configSchema": {"type": "object", "additionalProperties": False, "properties": {}},
        })
        self._write_manifest(str(tmp_path), "plugin.json", {
            "id": "secondary",
            "configSchema": {"type": "object", "additionalProperties": False, "properties": {}},
        })
        result = load_plugin_manifest(str(tmp_path))
        assert result.ok is True
        assert result.manifest.id == "primary"

    def test_missing_manifest_returns_fail(self, tmp_path):
        from openclaw.plugins.manifest import load_plugin_manifest
        result = load_plugin_manifest(str(tmp_path))
        assert result.ok is False
        assert "not found" in result.error.lower() or "manifest" in result.error.lower()

    def test_missing_id_returns_fail(self, tmp_path):
        from openclaw.plugins.manifest import load_plugin_manifest
        self._write_manifest(str(tmp_path), "openclaw.plugin.json", {
            "configSchema": {"type": "object", "additionalProperties": False, "properties": {}},
        })
        result = load_plugin_manifest(str(tmp_path))
        assert result.ok is False
        assert "id" in result.error.lower()

    def test_missing_config_schema_returns_fail(self, tmp_path):
        from openclaw.plugins.manifest import load_plugin_manifest
        self._write_manifest(str(tmp_path), "openclaw.plugin.json", {"id": "no-schema"})
        result = load_plugin_manifest(str(tmp_path))
        assert result.ok is False
        assert "configSchema" in result.error or "schema" in result.error.lower()

    def test_all_optional_fields_parsed(self, tmp_path):
        from openclaw.plugins.manifest import load_plugin_manifest
        data = {
            "id": "full-plugin",
            "name": "Full Plugin",
            "description": "A plugin with all fields",
            "version": "1.2.3",
            "kind": "memory",
            "channels": ["telegram", "discord"],
            "providers": ["openai-compat"],
            "skills": ["./skills"],
            "configSchema": {"type": "object", "additionalProperties": False, "properties": {}},
            "uiHints": {
                "apiKey": {"label": "API Key", "sensitive": True},
            },
        }
        self._write_manifest(str(tmp_path), "openclaw.plugin.json", data)
        result = load_plugin_manifest(str(tmp_path))
        assert result.ok is True
        m = result.manifest
        assert m.name == "Full Plugin"
        assert m.description == "A plugin with all fields"
        assert m.version == "1.2.3"
        assert m.kind == "memory"
        assert m.channels == ["telegram", "discord"]
        assert m.providers == ["openai-compat"]
        assert m.skills == ["./skills"]
        assert m.ui_hints is not None
        assert "apiKey" in m.ui_hints


# ---------------------------------------------------------------------------
# Plugin API registration methods
# ---------------------------------------------------------------------------

class TestPluginApiRegistration:
    """Tests for PluginApi registration methods."""

    def _make_api(self, plugin_id: str = "test"):
        from openclaw.plugins.api import create_plugin_api
        from openclaw.plugins.registry import create_empty_plugin_registry
        registry = create_empty_plugin_registry()
        api = create_plugin_api(plugin_id, f"{plugin_id} Plugin", registry, {}, source="/tmp/test.py")
        return api, registry

    def test_register_command_success(self):
        from openclaw.plugins.types import OpenClawPluginCommandDefinition
        api, registry = self._make_api()
        api.register_command(OpenClawPluginCommandDefinition(
            name="mycmd",
            description="My command",
            handler=lambda ctx: {"text": "ok"},
        ))
        assert len(registry.commands) == 1
        assert registry.commands[0].command.name == "mycmd"

    def test_register_command_duplicate_rejected(self):
        from openclaw.plugins.types import OpenClawPluginCommandDefinition
        api, registry = self._make_api()
        cmd = OpenClawPluginCommandDefinition(name="mycmd", description="cmd", handler=lambda ctx: {})
        api.register_command(cmd)
        api.register_command(cmd)
        assert len(registry.commands) == 1
        assert len(registry.diagnostics) == 1
        assert "already registered" in registry.diagnostics[0].message

    def test_register_command_reserved_name_rejected(self):
        from openclaw.plugins.types import OpenClawPluginCommandDefinition
        api, registry = self._make_api()
        api.register_command(OpenClawPluginCommandDefinition(
            name="help",
            description="override help",
            handler=lambda ctx: {},
        ))
        assert len(registry.commands) == 0
        assert any("reserved" in d.message for d in registry.diagnostics)

    def test_register_command_invalid_name_rejected(self):
        from openclaw.plugins.types import OpenClawPluginCommandDefinition
        api, registry = self._make_api()
        api.register_command(OpenClawPluginCommandDefinition(
            name="bad name!",
            description="bad",
            handler=lambda ctx: {},
        ))
        assert len(registry.commands) == 0
        assert any("invalid" in d.message for d in registry.diagnostics)

    def test_register_hook_with_name_succeeds(self):
        api, registry = self._make_api()
        async def my_hook(event, ctx):
            pass
        api.register_hook(
            "llm_output",
            my_hook,
            opts={"name": "my-llm-hook"},
        )
        assert len(registry.hooks) == 1
        assert registry.hooks[0].events == ["llm_output"]

    def test_register_hook_without_name_rejected(self):
        api, registry = self._make_api()
        async def my_hook(event, ctx):
            pass
        api.register_hook("llm_output", my_hook, opts={})
        assert len(registry.hooks) == 0
        assert len(registry.diagnostics) == 1

    def test_register_hook_with_register_false(self):
        api, registry = self._make_api()
        async def my_hook(event, ctx):
            pass
        api.register_hook(
            "llm_output",
            my_hook,
            opts={"name": "my-hook", "register": False},
        )
        # Hook should be registered in registry but NOT wired to internal_hooks
        assert len(registry.hooks) == 1

    def test_register_tool_adds_to_registry(self):
        from openclaw.plugins.types import PluginToolRegistration
        api, registry = self._make_api()
        api.register_tool({
            "name": "my_tool",
            "description": "A test tool",
            "parameters": {"type": "object", "properties": {}, "required": []},
            "execute": lambda _id, params: {"content": [{"type": "text", "text": "ok"}]},
        })
        assert len(registry.tools) == 1
        assert "my_tool" in registry.tools[0].names


# ---------------------------------------------------------------------------
# Integration test: load a bundled extension
# ---------------------------------------------------------------------------

class TestExtensionIntegration:
    """Integration tests for loading bundled extensions."""

    EXTENSIONS_DIR = Path(__file__).parent.parent / "extensions"

    def test_telegram_manifest_loads(self):
        from openclaw.plugins.manifest import load_plugin_manifest
        ext_dir = str(self.EXTENSIONS_DIR / "telegram")
        if not os.path.isdir(ext_dir):
            pytest.skip("telegram extension not present")
        result = load_plugin_manifest(ext_dir)
        assert result.ok is True
        assert result.manifest.id == "telegram"
        assert "telegram" in result.manifest.channels
        assert result.manifest.config_schema is not None

    def test_matrix_manifest_loads(self):
        from openclaw.plugins.manifest import load_plugin_manifest
        ext_dir = str(self.EXTENSIONS_DIR / "matrix")
        if not os.path.isdir(ext_dir):
            pytest.skip("matrix extension not present")
        result = load_plugin_manifest(ext_dir)
        assert result.ok is True
        assert result.manifest.id == "matrix"
        assert "matrix" in result.manifest.channels

    def test_memory_lancedb_manifest_has_config_schema(self):
        from openclaw.plugins.manifest import load_plugin_manifest
        ext_dir = str(self.EXTENSIONS_DIR / "memory-lancedb")
        if not os.path.isdir(ext_dir):
            pytest.skip("memory-lancedb extension not present")
        result = load_plugin_manifest(ext_dir)
        assert result.ok is True
        assert result.manifest.kind == "memory"
        schema = result.manifest.config_schema
        assert "properties" in schema
        assert "embedding" in schema["properties"]

    def test_telegram_plugin_py_has_plugin_dict(self):
        """plugin.py files must export a module-level plugin dict."""
        import importlib.util
        plugin_py = str(self.EXTENSIONS_DIR / "telegram" / "plugin.py")
        if not os.path.exists(plugin_py):
            pytest.skip("telegram plugin.py not present")
        spec = importlib.util.spec_from_file_location("openclaw_plugin_telegram_test", plugin_py)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        plugin = getattr(module, "plugin", None)
        assert plugin is not None, "plugin.py must export a module-level 'plugin' dict"
        assert isinstance(plugin, dict), "plugin must be a dict"
        assert plugin.get("id") == "telegram"
        assert plugin.get("name") is not None
        assert callable(plugin.get("register"))

    def test_all_extensions_have_openclaw_plugin_json(self):
        """Every extension directory must have openclaw.plugin.json."""
        if not self.EXTENSIONS_DIR.is_dir():
            pytest.skip("extensions directory not found")
        missing = []
        for ext_dir in sorted(self.EXTENSIONS_DIR.iterdir()):
            if not ext_dir.is_dir():
                continue
            if not (ext_dir / "openclaw.plugin.json").exists():
                missing.append(ext_dir.name)
        assert not missing, f"Missing openclaw.plugin.json in: {missing}"

    def test_all_extensions_manifests_loadable(self):
        """All openclaw.plugin.json files must parse and validate correctly."""
        from openclaw.plugins.manifest import load_plugin_manifest
        if not self.EXTENSIONS_DIR.is_dir():
            pytest.skip("extensions directory not found")
        failures = []
        for ext_dir in sorted(self.EXTENSIONS_DIR.iterdir()):
            if not ext_dir.is_dir():
                continue
            manifest_file = ext_dir / "openclaw.plugin.json"
            if not manifest_file.exists():
                continue
            result = load_plugin_manifest(str(ext_dir))
            if not result.ok:
                failures.append(f"{ext_dir.name}: {result.error}")
        assert not failures, f"Manifest load failures:\n" + "\n".join(failures)


# ---------------------------------------------------------------------------
# Plugin SDK helpers
# ---------------------------------------------------------------------------

class TestPluginSdkHelpers:
    """Tests for plugin_sdk utility functions."""

    def test_empty_plugin_config_schema_returns_valid_schema(self):
        from openclaw.plugin_sdk import empty_plugin_config_schema
        schema = empty_plugin_config_schema()
        assert isinstance(schema, dict)
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False
        assert schema["properties"] == {}

    def test_empty_plugin_config_schema_returns_new_dict_each_call(self):
        from openclaw.plugin_sdk import empty_plugin_config_schema
        a = empty_plugin_config_schema()
        b = empty_plugin_config_schema()
        assert a == b
        # Mutating one should not affect the other
        a["extra"] = True
        assert "extra" not in b

    def test_register_plugin_hooks_from_dir_nonexistent_dir(self, tmp_path):
        """Should not raise for missing directory."""
        from openclaw.plugin_sdk import register_plugin_hooks_from_dir
        from openclaw.plugins.api import create_plugin_api
        from openclaw.plugins.registry import create_empty_plugin_registry
        registry = create_empty_plugin_registry()
        api = create_plugin_api("test", "Test", registry, {}, source=str(tmp_path / "plugin.py"))
        # Should not raise
        register_plugin_hooks_from_dir(api, "./nonexistent-hooks-dir")
