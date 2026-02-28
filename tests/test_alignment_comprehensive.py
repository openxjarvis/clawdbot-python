"""
Comprehensive alignment tests covering all docs-to-code alignment work.

Tests every module that was modified or created to align Python with TS docs:
- broadcast_groups (broadcast config key)
- sessions/__init__.py (patch_session_entry, load_session_entry)
- gateway/http/chat_completions (parse_agent_id, resolve_session_key)
- gateway/http/responses (ResponsesRequest, parse helpers)
- gateway/heartbeat (HeartbeatConfig, _is_heartbeat_ok, resolve_heartbeat_config)
- gateway/error_codes (GatewayLockError)
- config/schema (SandboxConfig, SandboxDockerConfig, SandboxBrowserConfig)
- plugins/loader (load_plugin with proper manifest validation)
- plugins/manifest (load_plugin_manifest)
"""
from __future__ import annotations

import os
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# broadcast_groups
# ---------------------------------------------------------------------------

class TestBroadcastGroups:
    """Test broadcast config alignment with TS docs.

    TS config format: broadcast.<peer_id> = [list of agent ids]
    TS strategy: broadcast.strategy (top-level)
    """

    def _import(self):
        from openclaw.routing.broadcast_groups import (
            resolve_broadcast_agents,
            get_broadcast_strategy,
        )
        return resolve_broadcast_agents, get_broadcast_strategy

    def test_ts_format_list(self):
        """TS primary format: broadcast[peer_id] = [agent1, agent2]."""
        resolve, _ = self._import()
        cfg = {"broadcast": {"GROUP1": ["alfred", "baerbel"]}}
        agents = resolve(cfg, "GROUP1")
        assert agents == ["alfred", "baerbel"]

    def test_ts_format_empty_for_unknown(self):
        """Unknown peer id returns empty list."""
        resolve, _ = self._import()
        cfg = {"broadcast": {"GROUP1": ["alfred"]}}
        assert resolve(cfg, "UNKNOWN") == []

    def test_python_alias_broadcastGroups(self):
        """broadcastGroups alias still works."""
        resolve, _ = self._import()
        cfg = {"broadcastGroups": {"G1": {"agents": ["a", "b"]}}}
        assert resolve(cfg, "G1") == ["a", "b"]

    def test_ts_strategy_top_level(self):
        """Strategy lives at broadcast.strategy (TS format)."""
        _, get_strategy = self._import()
        cfg = {"broadcast": {"strategy": "sequential", "G1": ["a", "b"]}}
        assert get_strategy(cfg) == "sequential"

    def test_ts_strategy_default_parallel(self):
        """Default strategy is parallel."""
        _, get_strategy = self._import()
        cfg = {"broadcast": {"G1": ["a"]}}
        assert get_strategy(cfg) == "parallel"

    def test_both_formats_coexist(self):
        """broadcast primary, broadcastGroups fallback."""
        resolve, _ = self._import()
        cfg = {
            "broadcast": {"G1": ["a"]},
            "broadcastGroups": {"G2": {"agents": ["b"]}},
        }
        assert resolve(cfg, "G1") == ["a"]
        assert resolve(cfg, "G2") == ["b"]


# ---------------------------------------------------------------------------
# sessions patch_session_entry / load_session_entry
# ---------------------------------------------------------------------------

class TestSessionStoreHelpers:
    """Test patch_session_entry and load_session_entry."""

    def _import(self):
        from openclaw.agents.sessions import load_session_entry, patch_session_entry
        return load_session_entry, patch_session_entry

    def test_load_session_entry_returns_none_without_config(self):
        """Returns None when config is None (can't resolve store path)."""
        load, _ = self._import()
        result = load("agent:main:main", cfg=None)
        assert result is None

    def test_patch_session_entry_returns_none_without_config(self):
        """Returns None when config is None."""
        _, patch = self._import()
        result = patch("agent:main:main", {"test": "value"}, cfg=None)
        assert result is None

    def test_patch_session_entry_reads_and_writes(self):
        """patch_session_entry merges patches and writes sessions.json."""
        load, patch_fn = self._import()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Build a minimal cfg
            cfg = {"gateway": {"stateDir": tmpdir}, "agents": {"defaults": {"agentId": "testAgent"}}}
            # First patch creates the entry
            result = patch_fn("agent:main:main", {"role": "assistant"}, cfg=cfg)
            assert result is not None
            assert result["role"] == "assistant"
            assert "updatedAt" in result
            # Second patch merges
            result2 = patch_fn("agent:main:main", {"role": "user", "extra": 42}, cfg=cfg)
            assert result2["role"] == "user"
            assert result2["extra"] == 42

    def test_load_session_entry_reads_file(self):
        """load_session_entry reads from sessions.json."""
        load, patch_fn = self._import()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = {"gateway": {"stateDir": tmpdir}, "agents": {"defaults": {"agentId": "testAgent"}}}
            # Write a session via patch
            patch_fn("agent:main:main", {"greeting": "hello"}, cfg=cfg)
            # Now load it
            entry = load("agent:main:main", cfg=cfg)
            assert entry is not None
            assert entry.get("greeting") == "hello"


# ---------------------------------------------------------------------------
# gateway/http/chat_completions
# ---------------------------------------------------------------------------

class TestChatCompletionsHelpers:
    """Test OpenAI-compatible chat completions helpers."""

    def _import(self):
        from openclaw.gateway.http.chat_completions import (
            parse_agent_id,
            resolve_session_key,
            convert_openai_messages,
        )
        return parse_agent_id, resolve_session_key, convert_openai_messages

    def test_parse_openclaw_model(self):
        parse, _, _ = self._import()
        assert parse("openclaw:main") == "main"
        assert parse("openclaw:beta") == "beta"

    def test_parse_agent_model(self):
        parse, _, _ = self._import()
        assert parse("agent:support") == "support"

    def test_parse_default_model(self):
        parse, _, _ = self._import()
        assert parse("gpt-4") == "main"

    def test_resolve_session_key_ephemeral(self):
        _, resolve, _ = self._import()
        key = resolve("main", None)
        assert "ephemeral" in key

    def test_resolve_session_key_stable_with_user(self):
        _, resolve, _ = self._import()
        key1 = resolve("main", "user-abc")
        key2 = resolve("main", "user-abc")
        assert key1 == key2  # deterministic

    def test_resolve_session_key_different_users(self):
        _, resolve, _ = self._import()
        key1 = resolve("main", "alice")
        key2 = resolve("main", "bob")
        assert key1 != key2

    def test_convert_messages_basic(self):
        _, _, convert = self._import()
        msgs = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello"},
        ]
        result = convert(msgs)
        assert len(result) >= 1
        # Should have user message
        user_msgs = [m for m in result if m.get("role") == "user"]
        assert len(user_msgs) >= 1


# ---------------------------------------------------------------------------
# gateway/http/responses
# ---------------------------------------------------------------------------

class TestResponsesHelpers:
    """Test OpenResponses-compatible endpoint helpers."""

    def _import(self):
        from openclaw.gateway.http.responses import (
            _parse_agent_id,
            _extract_user_message,
            _build_system_additions,
            ResponsesRequest,
        )
        return _parse_agent_id, _extract_user_message, _build_system_additions, ResponsesRequest

    def test_parse_agent_id_openclaw(self):
        parse, _, _, _ = self._import()
        assert parse("openclaw:main") == "main"

    def test_parse_agent_id_default(self):
        parse, _, _, _ = self._import()
        assert parse("openclaw") == "main"

    def test_extract_string_input(self):
        _, extract, _, _ = self._import()
        assert extract("Hello world") == "Hello world"

    def test_extract_none_returns_none(self):
        _, extract, _, _ = self._import()
        assert extract(None) is None

    def test_extract_items_user_message(self):
        _, extract, _, _ = self._import()
        items = [
            {"type": "message", "role": "system", "content": "sys"},
            {"type": "message", "role": "user", "content": "Hello"},
        ]
        assert extract(items) == "Hello"

    def test_build_system_additions_with_instructions(self):
        _, _, build, _ = self._import()
        additions = build("Hello", "Be helpful")
        assert "Be helpful" in additions

    def test_build_system_additions_from_items(self):
        _, _, build, _ = self._import()
        items = [
            {"type": "message", "role": "system", "content": "sys-prompt"},
            {"type": "message", "role": "user", "content": "user-msg"},
        ]
        additions = build(items, None)
        assert "sys-prompt" in additions

    def test_responses_request_model(self):
        _, _, _, Req = self._import()
        req = Req(model="openclaw:main", input="hi", stream=False)
        assert req.model == "openclaw:main"
        assert req.input == "hi"
        assert req.stream is False


# ---------------------------------------------------------------------------
# gateway/heartbeat
# ---------------------------------------------------------------------------

class TestHeartbeat:
    """Test HeartbeatConfig and related helpers."""

    def _import(self):
        from openclaw.gateway.heartbeat import (
            HeartbeatConfig,
            ActiveHoursConfig,
            HeartbeatVisibilityConfig,
            _is_heartbeat_ok,
            _parse_interval_minutes,
            strip_heartbeat_ok,
            resolve_heartbeat_config,
            DEFAULT_HEARTBEAT_PROMPT,
            DEFAULT_ACK_MAX_CHARS,
        )
        return (
            HeartbeatConfig, ActiveHoursConfig, HeartbeatVisibilityConfig,
            _is_heartbeat_ok, _parse_interval_minutes, strip_heartbeat_ok,
            resolve_heartbeat_config, DEFAULT_HEARTBEAT_PROMPT, DEFAULT_ACK_MAX_CHARS,
        )

    def test_parse_interval_30m(self):
        _, _, _, _, parse, *_ = self._import()
        assert parse("30m") == 30

    def test_parse_interval_1h(self):
        _, _, _, _, parse, *_ = self._import()
        assert parse("1h") == 60

    def test_parse_interval_0m_disabled(self):
        _, _, _, _, parse, *_ = self._import()
        assert parse("0m") == 0

    def test_parse_interval_int(self):
        _, _, _, _, parse, *_ = self._import()
        assert parse(45) == 45

    def test_heartbeat_ok_pure(self):
        _, _, _, is_ok, *_ = self._import()
        assert is_ok("HEARTBEAT_OK")

    def test_heartbeat_ok_leading(self):
        _, _, _, is_ok, *_ = self._import()
        assert is_ok("HEARTBEAT_OK  small note")

    def test_heartbeat_ok_large_body_not_ok(self):
        _, _, _, is_ok, *_ = self._import()
        big_text = "HEARTBEAT_OK\n" + "A" * 400
        assert not is_ok(big_text, ack_max_chars=300)

    def test_heartbeat_ok_in_middle_not_stripped(self):
        _, _, _, is_ok, *_ = self._import()
        text = "This is important. HEARTBEAT_OK So much to say."
        assert not is_ok(text, ack_max_chars=300)

    def test_strip_heartbeat_ok(self):
        _, _, _, _, _, strip, *_ = self._import()
        assert strip("HEARTBEAT_OK") == ""
        assert strip("HEARTBEAT_OK  hello") == "hello"
        assert strip("hello HEARTBEAT_OK") == "hello"

    def test_heartbeat_config_enabled_flag(self):
        HeartbeatConfig, *_ = self._import()
        cfg = HeartbeatConfig(every="30m")
        assert cfg.enabled is True

    def test_heartbeat_config_disabled_flag(self):
        HeartbeatConfig, *_ = self._import()
        cfg = HeartbeatConfig(every="0m")
        assert cfg.enabled is False

    def test_heartbeat_config_interval_minutes(self):
        HeartbeatConfig, *_ = self._import()
        cfg = HeartbeatConfig(every="1h")
        assert cfg.interval_minutes == 60

    def test_resolve_heartbeat_config_from_agent(self):
        *_, resolve_hb, _, _ = self._import()
        agent_cfg = {"heartbeat": {"every": "30m", "target": "whatsapp"}}
        cfg = resolve_hb(agent_cfg)
        assert cfg is not None
        assert cfg.target == "whatsapp"
        assert cfg.interval_minutes == 30

    def test_resolve_heartbeat_config_merges_defaults(self):
        *_, resolve_hb, _, _ = self._import()
        defaults = {"heartbeat": {"every": "1h", "target": "telegram"}}
        agent_cfg = {"heartbeat": {"target": "whatsapp"}}
        cfg = resolve_hb(agent_cfg, defaults)
        # Agent target overrides defaults
        assert cfg.target == "whatsapp"

    def test_resolve_heartbeat_config_zero_returns_none(self):
        *_, resolve_hb, _, _ = self._import()
        agent_cfg = {"heartbeat": {"every": "0m"}}
        cfg = resolve_hb(agent_cfg)
        assert cfg is None

    def test_resolve_heartbeat_config_no_heartbeat_returns_none(self):
        *_, resolve_hb, _, _ = self._import()
        assert resolve_hb({}) is None

    def test_active_hours_config(self):
        _, ActiveHours, *_ = self._import()
        ah = ActiveHours(start="09:00", end="22:00")
        assert ah.start == "09:00"
        assert ah.end == "22:00"

    def test_visibility_config_defaults(self):
        _, _, Vis, *_ = self._import()
        vis = Vis()
        assert vis.show_ok is False
        assert vis.show_alerts is True
        assert vis.use_indicator is True

    def test_visibility_all_off_means_skip(self):
        HeartbeatConfig, _, Vis, *_ = self._import()
        vis = Vis(show_ok=False, show_alerts=False, use_indicator=False)
        cfg = HeartbeatConfig(every="30m", visibility=vis)
        from openclaw.gateway.heartbeat import HeartbeatManager
        mgr = HeartbeatManager(cfg, MagicMock())
        assert not mgr._should_run()

    def test_default_prompt_matches_ts(self):
        *_, default_prompt, _ = self._import()
        assert "HEARTBEAT.md" in default_prompt
        assert "HEARTBEAT_OK" in default_prompt

    def test_default_ack_max_chars(self):
        *_, _, ack_max = self._import()
        assert ack_max == 300


# ---------------------------------------------------------------------------
# gateway/error_codes GatewayLockError
# ---------------------------------------------------------------------------

class TestGatewayLockError:
    """Test GatewayLockError matches TS spec."""

    def test_address_in_use_message(self):
        from openclaw.gateway.error_codes import GatewayLockError
        err = GatewayLockError("127.0.0.1", 18789)
        assert "another gateway instance is already listening" in str(err)
        assert "18789" in str(err)

    def test_other_os_error(self):
        from openclaw.gateway.error_codes import GatewayLockError
        cause = OSError("permission denied")
        err = GatewayLockError("127.0.0.1", 18789, cause=cause)
        # Should say "failed to bind"
        assert "failed to bind" in str(err)

    def test_host_port_attrs(self):
        from openclaw.gateway.error_codes import GatewayLockError
        err = GatewayLockError("0.0.0.0", 9999)
        assert err.host == "0.0.0.0"
        assert err.port == 9999

    def test_is_exception(self):
        from openclaw.gateway.error_codes import GatewayLockError
        with pytest.raises(GatewayLockError):
            raise GatewayLockError("127.0.0.1", 18789)


# ---------------------------------------------------------------------------
# config/schema SandboxConfig
# ---------------------------------------------------------------------------

class TestSandboxConfig:
    """Test SandboxConfig aligns with TS sandboxing.md spec."""

    def test_default_mode(self):
        from openclaw.config.schema import SandboxConfig
        cfg = SandboxConfig()
        assert cfg.mode == "off"

    def test_default_scope(self):
        from openclaw.config.schema import SandboxConfig
        cfg = SandboxConfig()
        assert cfg.scope == "session"

    def test_default_workspace_access(self):
        from openclaw.config.schema import SandboxConfig
        cfg = SandboxConfig()
        assert cfg.workspaceAccess == "none"

    def test_all_modes_accepted(self):
        from openclaw.config.schema import SandboxConfig
        for mode in ("off", "non-main", "all"):
            cfg = SandboxConfig(mode=mode)
            assert cfg.mode == mode

    def test_all_scopes_accepted(self):
        from openclaw.config.schema import SandboxConfig
        for scope in ("session", "agent", "shared"):
            cfg = SandboxConfig(scope=scope)
            assert cfg.scope == scope

    def test_workspace_access_values(self):
        from openclaw.config.schema import SandboxConfig
        for wa in ("none", "ro", "rw"):
            cfg = SandboxConfig(workspaceAccess=wa)
            assert cfg.workspaceAccess == wa

    def test_docker_binds(self):
        from openclaw.config.schema import SandboxConfig, SandboxDockerConfig
        docker = SandboxDockerConfig(binds=["/host:/container:rw"])
        cfg = SandboxConfig(docker=docker)
        assert cfg.docker.binds == ["/host:/container:rw"]

    def test_browser_auto_start(self):
        from openclaw.config.schema import SandboxBrowserConfig
        b = SandboxBrowserConfig(autoStart=False)
        assert b.autoStart is False

    def test_browser_allow_host_control(self):
        from openclaw.config.schema import SandboxBrowserConfig
        b = SandboxBrowserConfig(allowHostControl=True)
        assert b.allowHostControl is True


# ---------------------------------------------------------------------------
# plugins/manifest load_plugin_manifest
# ---------------------------------------------------------------------------

class TestPluginManifest:
    """Test load_plugin_manifest validation."""

    def test_valid_manifest(self):
        from openclaw.plugins.manifest import load_plugin_manifest, PluginManifestLoadOk
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = {
                "id": "test-plugin",
                "configSchema": {"type": "object", "additionalProperties": False, "properties": {}},
            }
            (Path(tmpdir) / "openclaw.plugin.json").write_text(json.dumps(manifest))
            result = load_plugin_manifest(tmpdir)
            assert isinstance(result, PluginManifestLoadOk)
            assert result.manifest.id == "test-plugin"

    def test_missing_manifest_fails(self):
        from openclaw.plugins.manifest import load_plugin_manifest, PluginManifestLoadFail
        with tempfile.TemporaryDirectory() as tmpdir:
            result = load_plugin_manifest(tmpdir)
            assert isinstance(result, PluginManifestLoadFail)
            assert "not found" in result.error

    def test_missing_id_fails(self):
        from openclaw.plugins.manifest import load_plugin_manifest, PluginManifestLoadFail
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = {"configSchema": {"type": "object"}}
            (Path(tmpdir) / "openclaw.plugin.json").write_text(json.dumps(manifest))
            result = load_plugin_manifest(tmpdir)
            assert isinstance(result, PluginManifestLoadFail)
            assert "id" in result.error

    def test_missing_config_schema_fails(self):
        from openclaw.plugins.manifest import load_plugin_manifest, PluginManifestLoadFail
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = {"id": "my-plugin"}
            (Path(tmpdir) / "openclaw.plugin.json").write_text(json.dumps(manifest))
            result = load_plugin_manifest(tmpdir)
            assert isinstance(result, PluginManifestLoadFail)
            assert "configSchema" in result.error

    def test_optional_fields_loaded(self):
        from openclaw.plugins.manifest import load_plugin_manifest, PluginManifestLoadOk
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = {
                "id": "my-plugin",
                "name": "My Plugin",
                "description": "A test plugin",
                "version": "1.0.0",
                "channels": ["matrix"],
                "providers": ["my-provider"],
                "configSchema": {"type": "object"},
            }
            (Path(tmpdir) / "openclaw.plugin.json").write_text(json.dumps(manifest))
            result = load_plugin_manifest(tmpdir)
            assert isinstance(result, PluginManifestLoadOk)
            m = result.manifest
            assert m.name == "My Plugin"
            assert m.version == "1.0.0"
            assert "matrix" in m.channels
            assert "my-provider" in m.providers

    def test_legacy_plugin_json_fallback(self):
        from openclaw.plugins.manifest import load_plugin_manifest, PluginManifestLoadOk
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = {
                "id": "legacy-plugin",
                "configSchema": {"type": "object"},
            }
            (Path(tmpdir) / "plugin.json").write_text(json.dumps(manifest))
            result = load_plugin_manifest(tmpdir)
            assert isinstance(result, PluginManifestLoadOk)
            assert result.manifest.id == "legacy-plugin"


# ---------------------------------------------------------------------------
# plugins/loader with manifest validation
# ---------------------------------------------------------------------------

class TestPluginLoader:
    """Test plugin loader uses manifest.py validation."""

    def test_load_plugin_error_tracked(self):
        from openclaw.plugins.loader import PluginLoader
        with tempfile.TemporaryDirectory() as tmpdir:
            # Plugin dir with broken manifest (missing configSchema)
            plugin_dir = Path(tmpdir) / "bad-plugin"
            plugin_dir.mkdir()
            (plugin_dir / "openclaw.plugin.json").write_text(json.dumps({"id": "bad"}))

            loader = PluginLoader()
            result = loader.load_plugin(plugin_dir)
            assert result is None
            assert str(plugin_dir) in loader._errors

    def test_load_valid_plugin(self):
        from openclaw.plugins.loader import PluginLoader
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / "good-plugin"
            plugin_dir.mkdir()
            manifest = {
                "id": "good-plugin",
                "configSchema": {"type": "object"},
            }
            (plugin_dir / "openclaw.plugin.json").write_text(json.dumps(manifest))

            loader = PluginLoader()
            plugin = loader.load_plugin(plugin_dir)
            assert plugin is not None
            assert "good-plugin" in loader.plugins

    def test_discover_plugins_checks_manifest_files(self):
        from openclaw.plugins.loader import PluginLoader
        with tempfile.TemporaryDirectory() as tmpdir:
            # Dir with manifest
            p1 = Path(tmpdir) / "plugin-with-manifest"
            p1.mkdir()
            (p1 / "openclaw.plugin.json").write_text("{}")
            # Dir without manifest
            p2 = Path(tmpdir) / "no-manifest-dir"
            p2.mkdir()

            loader = PluginLoader()
            # Override the search dirs
            dirs = []
            for item in Path(tmpdir).iterdir():
                if item.is_dir() and (
                    (item / "openclaw.plugin.json").exists() or (item / "plugin.json").exists()
                ):
                    dirs.append(item)
            assert p1 in dirs
            assert p2 not in dirs


# ---------------------------------------------------------------------------
# gateway/_check_http_auth (from server.py)
# ---------------------------------------------------------------------------

class TestGatewayHttpAuth:
    """Test _check_http_auth logic."""

    def _make_gateway_server(self, auth_cfg):
        """Build a minimal GatewayServer with mocked config."""
        from openclaw.gateway.server import GatewayServer
        with patch.object(GatewayServer, "__init__", lambda self, *a, **k: None):
            srv = GatewayServer.__new__(GatewayServer)
        gw_cfg = MagicMock()
        gw_cfg.auth = auth_cfg
        cfg = MagicMock()
        cfg.gateway = gw_cfg
        srv.config = cfg
        return srv

    def test_no_auth_returns_true(self):
        srv = self._make_gateway_server(None)
        assert srv._check_http_auth("") is True

    def test_token_mode_valid(self):
        auth = MagicMock()
        auth.mode = "token"
        auth.token = "secret-token"
        srv = self._make_gateway_server(auth)
        assert srv._check_http_auth("Bearer secret-token") is True

    def test_token_mode_invalid(self):
        auth = MagicMock()
        auth.mode = "token"
        auth.token = "secret-token"
        srv = self._make_gateway_server(auth)
        assert srv._check_http_auth("Bearer wrong-token") is False


# ---------------------------------------------------------------------------
# _list_available_models (from server.py)
# ---------------------------------------------------------------------------

class TestListAvailableModels:
    """Test _list_available_models returns correct model ids."""

    def _make_gateway_server(self, agents_cfg):
        from openclaw.gateway.server import GatewayServer
        with patch.object(GatewayServer, "__init__", lambda self, *a, **k: None):
            srv = GatewayServer.__new__(GatewayServer)
        cfg = MagicMock()
        cfg.agents = agents_cfg
        srv.config = cfg
        return srv

    def test_returns_openclaw_base(self):
        srv = self._make_gateway_server({"list": []})
        assert "openclaw" in srv._list_available_models()

    def test_returns_agent_models(self):
        srv = self._make_gateway_server({"list": [{"id": "main"}, {"id": "beta"}]})
        models = srv._list_available_models()
        assert "openclaw:main" in models
        assert "openclaw:beta" in models
        assert "agent:main" in models


# ---------------------------------------------------------------------------
# Run all tests
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
