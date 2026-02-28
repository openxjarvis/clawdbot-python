"""Round-2 alignment tests.

Covers all code changes from the second alignment pass:
1. apply_patch (*** Begin Patch format)
2. /tools/invoke (DEFAULT_GATEWAY_HTTP_TOOL_DENY, sessionKey, dryRun, action merge, HTTP codes)
3. model-failover (exponential cooldown, billing disable)
4. loop-detection (hash_tool_outcome, _is_known_poll_tool_call, knownPollNoProgress)
5. discovery (_openclaw-gw._tcp service type, TXT keys)
6. subagents (sessions_spawn tool schema: task/label/agentId/model/cleanup/runTimeoutSeconds)
"""
from __future__ import annotations

import os
import tempfile
import pytest
from pathlib import Path


# ===========================================================================
# 1. apply_patch
# ===========================================================================

class TestApplyPatch:
    """Tests for patch.py — *** Begin Patch format."""

    def _make_patch(self, body: str) -> str:
        return f"*** Begin Patch\n{body}\n*** End Patch"

    def test_parse_add_file(self):
        from openclaw.agents.tools.patch import parse_patch_text, AddFileHunk
        patch = self._make_patch("*** Add File: hello.txt\n+Hello, World!\n+Line 2")
        hunks = parse_patch_text(patch)
        assert len(hunks) == 1
        h = hunks[0]
        assert isinstance(h, AddFileHunk)
        assert h.path == "hello.txt"
        assert "Hello, World!\n" in h.contents
        assert "Line 2\n" in h.contents

    def test_parse_delete_file(self):
        from openclaw.agents.tools.patch import parse_patch_text, DeleteFileHunk
        patch = self._make_patch("*** Delete File: old.txt")
        hunks = parse_patch_text(patch)
        assert len(hunks) == 1
        assert isinstance(hunks[0], DeleteFileHunk)
        assert hunks[0].path == "old.txt"

    def test_parse_update_file(self):
        from openclaw.agents.tools.patch import parse_patch_text, UpdateFileHunk
        patch = self._make_patch(
            "*** Update File: foo.py\n@@ some context\n-old line\n+new line\n context line"
        )
        hunks = parse_patch_text(patch)
        assert len(hunks) == 1
        h = hunks[0]
        assert isinstance(h, UpdateFileHunk)
        assert h.path == "foo.py"
        assert len(h.chunks) == 1
        chunk = h.chunks[0]
        assert "old line" in chunk.old_lines
        assert "new line" in chunk.new_lines

    def test_parse_move_file(self):
        from openclaw.agents.tools.patch import parse_patch_text, UpdateFileHunk
        patch = self._make_patch(
            "*** Update File: src.py\n*** Move to: dst.py\n@@\n-old\n+new"
        )
        hunks = parse_patch_text(patch)
        assert len(hunks) == 1
        h = hunks[0]
        assert isinstance(h, UpdateFileHunk)
        assert h.move_path == "dst.py"

    def test_empty_input_raises(self):
        from openclaw.agents.tools.patch import parse_patch_text
        with pytest.raises(ValueError, match="empty"):
            parse_patch_text("")

    def test_missing_begin_marker_raises(self):
        from openclaw.agents.tools.patch import parse_patch_text
        with pytest.raises(ValueError):
            parse_patch_text("*** Delete File: foo.txt\n*** End Patch")

    def test_apply_add_file(self, tmp_path):
        from openclaw.agents.tools.patch import apply_patch
        patch = self._make_patch("*** Add File: greet.txt\n+Hello!\n+World!")
        text, summary = apply_patch(patch, str(tmp_path))
        assert "A greet.txt" in text
        assert "greet.txt" in summary.added
        assert (tmp_path / "greet.txt").read_text() == "Hello!\nWorld!\n"

    def test_apply_update_file(self, tmp_path):
        from openclaw.agents.tools.patch import apply_patch
        f = tmp_path / "code.py"
        f.write_text("def foo():\n    return 1\n")
        patch = self._make_patch(
            "*** Update File: code.py\n@@\n def foo():\n-    return 1\n+    return 2"
        )
        text, summary = apply_patch(patch, str(tmp_path))
        assert "M code.py" in text
        assert "return 2" in f.read_text()

    def test_apply_delete_file(self, tmp_path):
        from openclaw.agents.tools.patch import apply_patch
        f = tmp_path / "gone.txt"
        f.write_text("bye\n")
        patch = self._make_patch("*** Delete File: gone.txt")
        text, summary = apply_patch(patch, str(tmp_path))
        assert "D gone.txt" in text
        assert not f.exists()

    def test_eof_marker_in_update(self, tmp_path):
        from openclaw.agents.tools.patch import apply_patch
        f = tmp_path / "file.txt"
        f.write_text("line1\nline2\nline3\n")
        patch = self._make_patch(
            "*** Update File: file.txt\n@@\n line2\n-line3\n+replaced\n*** End of File"
        )
        text, summary = apply_patch(patch, str(tmp_path))
        assert "replaced" in f.read_text()

    def test_tool_schema_uses_input_param(self):
        from openclaw.agents.tools.patch import ApplyPatchTool
        t = ApplyPatchTool()
        schema = t.get_schema()
        assert "input" in schema["properties"]
        assert "required" in schema
        assert "input" in schema["required"]
        assert "patch" not in schema["properties"]  # old field name must be gone

    def test_apply_patch_constants_match_ts(self):
        from openclaw.agents.tools.patch import BEGIN_PATCH_MARKER, END_PATCH_MARKER
        assert BEGIN_PATCH_MARKER == "*** Begin Patch"
        assert END_PATCH_MARKER == "*** End Patch"

    def test_heredoc_wrapping_lenient(self):
        from openclaw.agents.tools.patch import parse_patch_text, DeleteFileHunk
        patch = "<<EOF\n*** Begin Patch\n*** Delete File: x.txt\n*** End Patch\nEOF"
        hunks = parse_patch_text(patch)
        assert len(hunks) == 1
        assert isinstance(hunks[0], DeleteFileHunk)


# ===========================================================================
# 2. /tools/invoke
# ===========================================================================

class TestToolsInvoke:
    """Tests for tools_invoke.py."""

    def test_default_deny_list(self):
        from openclaw.gateway.http.tools_invoke import DEFAULT_GATEWAY_HTTP_TOOL_DENY
        assert "sessions_spawn" in DEFAULT_GATEWAY_HTTP_TOOL_DENY
        assert "sessions_send" in DEFAULT_GATEWAY_HTTP_TOOL_DENY
        assert "gateway" in DEFAULT_GATEWAY_HTTP_TOOL_DENY
        assert "whatsapp_login" in DEFAULT_GATEWAY_HTTP_TOOL_DENY

    def test_denied_tool_returns_forbidden(self):
        from openclaw.gateway.http.tools_invoke import check_tool_policy
        allowed, reason = check_tool_policy("sessions_spawn", config=None)
        assert not allowed
        assert "deny list" in reason

    def test_allowed_tool_passes(self):
        from openclaw.gateway.http.tools_invoke import check_tool_policy
        allowed, reason = check_tool_policy("memory_search", config=None)
        assert allowed
        assert reason is None

    def test_parse_request_basic(self):
        from openclaw.gateway.http.tools_invoke import ToolInvokeRequest
        req = ToolInvokeRequest({"tool": "exec", "args": {"command": "ls"}})
        assert req.tool == "exec"
        assert req.args == {"command": "ls"}
        assert req.action is None
        assert req.session_key is None
        assert req.dry_run is False

    def test_parse_request_with_session_key(self):
        from openclaw.gateway.http.tools_invoke import ToolInvokeRequest
        req = ToolInvokeRequest({"tool": "exec", "sessionKey": "  main  ", "args": {}})
        assert req.session_key == "main"

    def test_parse_request_with_action(self):
        from openclaw.gateway.http.tools_invoke import ToolInvokeRequest
        req = ToolInvokeRequest({"tool": "process", "action": "poll", "args": {}})
        assert req.action == "poll"

    def test_parse_request_with_dry_run(self):
        from openclaw.gateway.http.tools_invoke import ToolInvokeRequest
        req = ToolInvokeRequest({"tool": "exec", "dryRun": True, "args": {}})
        assert req.dry_run is True

    def test_merge_action_into_args(self):
        from openclaw.gateway.http.tools_invoke import _merge_action_into_args
        schema = {"properties": {"action": {"type": "string"}, "id": {"type": "string"}}}
        result = _merge_action_into_args(schema, "poll", {"id": "123"})
        assert result["action"] == "poll"
        assert result["id"] == "123"

    def test_merge_action_not_applied_if_no_schema_property(self):
        from openclaw.gateway.http.tools_invoke import _merge_action_into_args
        schema = {"properties": {"command": {"type": "string"}}}
        result = _merge_action_into_args(schema, "poll", {"command": "ls"})
        assert "action" not in result

    def test_response_to_dict(self):
        from openclaw.gateway.http.tools_invoke import ToolInvokeResponse
        r = ToolInvokeResponse(ok=True, result="data", status=200)
        d = r.to_dict()
        assert d["ok"] is True
        assert d["result"] == "data"
        assert "error" not in d

    def test_response_error_to_dict(self):
        from openclaw.gateway.http.tools_invoke import ToolInvokeResponse
        r = ToolInvokeResponse(ok=False, error={"code": "NOT_FOUND"}, status=404)
        d = r.to_dict()
        assert not d["ok"]
        assert d["error"]["code"] == "NOT_FOUND"

    def test_tool_not_found_returns_404(self):
        import asyncio
        from openclaw.gateway.http.tools_invoke import handle_tool_invoke_request
        resp = asyncio.run(
            handle_tool_invoke_request({"tool": "nonexistent", "args": {}}, tool_registry={}, gateway=None)
        )
        assert resp.status == 404
        assert not resp.ok

    def test_denied_tool_returns_403_via_handler(self):
        import asyncio
        from openclaw.gateway.http.tools_invoke import handle_tool_invoke_request
        resp = asyncio.run(
            handle_tool_invoke_request({"tool": "whatsapp_login", "args": {}}, tool_registry={}, gateway=None)
        )
        assert resp.status == 403

    def test_invalid_request_returns_400(self):
        import asyncio
        from openclaw.gateway.http.tools_invoke import handle_tool_invoke_request
        resp = asyncio.run(
            handle_tool_invoke_request({"args": {}}, tool_registry={}, gateway=None)
        )
        assert resp.status == 400


# ===========================================================================
# 3. model-failover / auth profile cooldown
# ===========================================================================

class TestCalculateAuthProfileCooldownMs:
    """Tests for exponential cooldown schedule."""

    def test_cooldown_schedule_matches_ts(self):
        from openclaw.agents.auth.profile import calculate_auth_profile_cooldown_ms
        # TS schedule: 1min, 5min, 25min, 1h
        assert calculate_auth_profile_cooldown_ms(1) == 60_000        # 1 min
        assert calculate_auth_profile_cooldown_ms(2) == 300_000       # 5 min
        assert calculate_auth_profile_cooldown_ms(3) == 1_500_000     # 25 min
        assert calculate_auth_profile_cooldown_ms(4) == 3_600_000     # 1 hour (cap)
        assert calculate_auth_profile_cooldown_ms(10) == 3_600_000    # still capped at 1h

    def test_zero_error_count_treated_as_one(self):
        from openclaw.agents.auth.profile import calculate_auth_profile_cooldown_ms
        assert calculate_auth_profile_cooldown_ms(0) == 60_000

    def test_negative_error_count_treated_as_one(self):
        from openclaw.agents.auth.profile import calculate_auth_profile_cooldown_ms
        assert calculate_auth_profile_cooldown_ms(-5) == 60_000


class TestAuthProfileBillingDisable:
    """Tests for billing disable / disabledUntil fields."""

    def test_profile_has_disabled_until_field(self):
        from openclaw.agents.auth.profile import AuthProfile
        p = AuthProfile(id="x", provider="anthropic", api_key="k")
        assert hasattr(p, "disabled_until")
        assert p.disabled_until is None

    def test_profile_has_disabled_reason_field(self):
        from openclaw.agents.auth.profile import AuthProfile
        p = AuthProfile(id="x", provider="anthropic", api_key="k")
        assert hasattr(p, "disabled_reason")
        assert p.disabled_reason is None

    def test_is_billing_disabled_false_when_no_disable(self):
        from openclaw.agents.auth.profile import AuthProfile
        p = AuthProfile(id="x", provider="anthropic", api_key="k")
        assert not p.is_billing_disabled()

    def test_is_billing_disabled_true_when_disabled(self):
        from openclaw.agents.auth.profile import AuthProfile
        from datetime import datetime, timezone, timedelta
        future = datetime.now(timezone.utc) + timedelta(hours=5)
        p = AuthProfile(id="x", provider="anthropic", api_key="k", disabled_until=future)
        assert p.is_billing_disabled()
        assert not p.is_available()

    def test_to_dict_includes_disabled_fields(self):
        from openclaw.agents.auth.profile import AuthProfile
        from datetime import datetime, timezone, timedelta
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        p = AuthProfile(id="x", provider="openai", api_key="k", disabled_until=future, disabled_reason="billing")
        d = p.to_dict()
        assert "disabledUntil" in d
        assert "disabledReason" in d
        assert d["disabledReason"] == "billing"


class TestRotationManagerCooldown:
    """Tests for RotationManager.mark_failure with exponential cooldown."""

    def _make_store_with_profile(self, profile_id="p1", provider="anthropic"):
        from openclaw.agents.auth.profile import AuthProfile, ProfileStore
        store = ProfileStore()
        profile = AuthProfile(id=profile_id, provider=provider, api_key="test-key")
        store.add_profile(profile)
        return store

    def test_mark_failure_applies_exponential_cooldown(self):
        from openclaw.agents.auth.rotation import RotationManager
        from openclaw.agents.auth.profile import calculate_auth_profile_cooldown_ms
        store = self._make_store_with_profile()
        mgr = RotationManager(store)
        mgr.mark_failure("p1", reason="test")
        profile = store.get_profile("p1")
        assert profile.cooldown_until is not None
        assert profile.error_count == 1

    def test_mark_failure_billing_sets_disabled_until(self):
        from openclaw.agents.auth.rotation import RotationManager
        store = self._make_store_with_profile()
        mgr = RotationManager(store)
        mgr.mark_failure("p1", reason="billing", is_billing_error=True)
        profile = store.get_profile("p1")
        assert profile.disabled_until is not None

    def test_clear_expired_cooldowns(self):
        from openclaw.agents.auth.rotation import RotationManager
        from openclaw.agents.auth.profile import AuthProfile
        from datetime import datetime, timezone, timedelta
        store = self._make_store_with_profile()
        profile = store.get_profile("p1")
        profile.cooldown_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        profile.error_count = 3
        store.add_profile(profile)
        mgr = RotationManager(store)
        cleared = mgr.clear_expired_cooldowns()
        assert cleared == 1
        updated = store.get_profile("p1")
        assert updated.cooldown_until is None
        assert updated.error_count == 0


# ===========================================================================
# 4. loop-detection
# ===========================================================================

class TestLoopDetectionHashToolOutcome:
    """Tests for hash_tool_outcome function."""

    def test_hash_tool_outcome_with_error(self):
        from openclaw.agents.tool_loop_detection import hash_tool_outcome
        h = hash_tool_outcome("exec", {}, None, Exception("failed"))
        assert h is not None
        assert h.startswith("error:")

    def test_hash_tool_outcome_two_errors_same(self):
        from openclaw.agents.tool_loop_detection import hash_tool_outcome
        h1 = hash_tool_outcome("exec", {}, None, Exception("same"))
        h2 = hash_tool_outcome("exec", {}, None, Exception("same"))
        assert h1 == h2

    def test_hash_tool_outcome_two_errors_different(self):
        from openclaw.agents.tool_loop_detection import hash_tool_outcome
        h1 = hash_tool_outcome("exec", {}, None, Exception("err-a"))
        h2 = hash_tool_outcome("exec", {}, None, Exception("err-b"))
        assert h1 != h2

    def test_hash_tool_outcome_process_poll_action(self):
        from openclaw.agents.tool_loop_detection import hash_tool_outcome
        result = {
            "content": [{"type": "text", "text": "output"}],
            "details": {"status": "running", "exitCode": None, "aggregated": "log"},
        }
        h = hash_tool_outcome("process", {"action": "poll"}, result)
        assert h is not None
        assert len(h) > 8

    def test_hash_tool_outcome_same_process_poll_same_hash(self):
        from openclaw.agents.tool_loop_detection import hash_tool_outcome
        r = {
            "content": [{"type": "text", "text": "still running"}],
            "details": {"status": "running", "exitCode": None, "aggregated": None},
        }
        h1 = hash_tool_outcome("process", {"action": "poll"}, r)
        h2 = hash_tool_outcome("process", {"action": "poll"}, r)
        assert h1 == h2

    def test_hash_tool_outcome_undefined_returns_none(self):
        from openclaw.agents.tool_loop_detection import hash_tool_outcome
        h = hash_tool_outcome("exec", {}, None)
        assert h is None


class TestIsKnownPollToolCall:
    """Tests for _is_known_poll_tool_call."""

    def test_command_status_is_poll(self):
        from openclaw.agents.tool_loop_detection import _is_known_poll_tool_call
        assert _is_known_poll_tool_call("command_status", {})

    def test_process_poll_is_poll(self):
        from openclaw.agents.tool_loop_detection import _is_known_poll_tool_call
        assert _is_known_poll_tool_call("process", {"action": "poll"})

    def test_process_log_is_poll(self):
        from openclaw.agents.tool_loop_detection import _is_known_poll_tool_call
        assert _is_known_poll_tool_call("process", {"action": "log"})

    def test_process_spawn_not_poll(self):
        from openclaw.agents.tool_loop_detection import _is_known_poll_tool_call
        assert not _is_known_poll_tool_call("process", {"action": "spawn"})

    def test_exec_not_poll(self):
        from openclaw.agents.tool_loop_detection import _is_known_poll_tool_call
        assert not _is_known_poll_tool_call("exec", {})

    def test_memory_search_not_poll(self):
        from openclaw.agents.tool_loop_detection import _is_known_poll_tool_call
        assert not _is_known_poll_tool_call("memory_search", {})


class TestKnownPollNoProgressDetector:
    """Test known_poll_no_progress detector triggers correctly."""

    def _make_state_with_poll_history(self, tool: str, params: dict, same_result_count: int):
        from openclaw.agents.tool_loop_detection import (
            SessionState, ToolCallRecord, hash_tool_call,
        )
        from collections import deque
        state = SessionState()
        h = hash_tool_call(tool, params)
        result_hash = "stable_hash_abc"
        for i in range(same_result_count):
            r = ToolCallRecord(
                tool_name=tool,
                hash=h,
                timestamp=i * 1000,
                outcome="success",
                result_hash=result_hash,
            )
            state.tool_call_history.append(r)
        return state

    def test_poll_no_progress_warning_at_threshold(self):
        from openclaw.agents.tool_loop_detection import detect_tool_call_loop, WARNING_THRESHOLD
        state = self._make_state_with_poll_history("command_status", {}, WARNING_THRESHOLD)
        result = detect_tool_call_loop(
            state, "command_status", {}, config={"enabled": True}
        )
        assert result.stuck
        assert result.detector == "known_poll_no_progress"
        assert result.level == "warning"

    def test_poll_no_progress_critical_at_critical_threshold(self):
        from openclaw.agents.tool_loop_detection import detect_tool_call_loop, CRITICAL_THRESHOLD
        state = self._make_state_with_poll_history("command_status", {}, CRITICAL_THRESHOLD)
        result = detect_tool_call_loop(
            state, "command_status", {}, config={"enabled": True}
        )
        assert result.stuck
        assert result.level == "critical"


# ===========================================================================
# 5. discovery
# ===========================================================================

class TestGatewayDiscovery:
    """Tests for discovery.py Bonjour service type and TXT record alignment."""

    def test_service_type_is_openclaw_gw(self):
        from openclaw.gateway.discovery import GATEWAY_BONJOUR_SERVICE_TYPE
        assert GATEWAY_BONJOUR_SERVICE_TYPE == "_openclaw-gw._tcp.local."

    def test_build_txt_records_required_fields(self):
        from openclaw.gateway.discovery import GatewayBonjourOpts, _build_txt_records
        opts = GatewayBonjourOpts(gateway_port=18789)
        txt = _build_txt_records(opts, "myhost", "My Host (OpenClaw)")
        assert txt["role"] == "gateway"
        assert txt["gatewayPort"] == "18789"
        assert txt["lanHost"] == "myhost.local"
        assert txt["transport"] == "gateway"

    def test_build_txt_records_ssh_port_omitted_in_minimal(self):
        from openclaw.gateway.discovery import GatewayBonjourOpts, _build_txt_records
        opts = GatewayBonjourOpts(gateway_port=18789, minimal=True)
        txt = _build_txt_records(opts, "host", "Host")
        assert "sshPort" not in txt

    def test_build_txt_records_ssh_port_included_non_minimal(self):
        from openclaw.gateway.discovery import GatewayBonjourOpts, _build_txt_records
        opts = GatewayBonjourOpts(gateway_port=18789, ssh_port=2222)
        txt = _build_txt_records(opts, "host", "Host")
        assert txt["sshPort"] == "2222"

    def test_build_txt_records_tls_fields(self):
        from openclaw.gateway.discovery import GatewayBonjourOpts, _build_txt_records
        opts = GatewayBonjourOpts(
            gateway_port=18789,
            gateway_tls_enabled=True,
            gateway_tls_fingerprint_sha256="abc123",
        )
        txt = _build_txt_records(opts, "host", "Host")
        assert txt.get("gatewayTls") == "1"
        assert txt.get("gatewayTlsSha256") == "abc123"

    def test_build_txt_records_canvas_port(self):
        from openclaw.gateway.discovery import GatewayBonjourOpts, _build_txt_records
        opts = GatewayBonjourOpts(gateway_port=18789, canvas_port=8888)
        txt = _build_txt_records(opts, "host", "Host")
        assert txt.get("canvasPort") == "8888"

    def test_build_txt_records_tailnet_dns(self):
        from openclaw.gateway.discovery import GatewayBonjourOpts, _build_txt_records
        opts = GatewayBonjourOpts(gateway_port=18789, tailnet_dns="mymachine.ts.net")
        txt = _build_txt_records(opts, "host", "Host")
        assert txt.get("tailnetDns") == "mymachine.ts.net"

    def test_build_txt_records_cli_path_omitted_in_minimal(self):
        from openclaw.gateway.discovery import GatewayBonjourOpts, _build_txt_records
        opts = GatewayBonjourOpts(gateway_port=18789, cli_path="/usr/local/bin/openclaw", minimal=True)
        txt = _build_txt_records(opts, "host", "Host")
        assert "cliPath" not in txt

    def test_build_txt_records_cli_path_included_non_minimal(self):
        from openclaw.gateway.discovery import GatewayBonjourOpts, _build_txt_records
        opts = GatewayBonjourOpts(gateway_port=18789, cli_path="/usr/local/bin/openclaw")
        txt = _build_txt_records(opts, "host", "Host")
        assert txt.get("cliPath") == "/usr/local/bin/openclaw"

    def test_bonjour_disabled_by_env(self, monkeypatch):
        """When OPENCLAW_DISABLE_BONJOUR=1, start() should return immediately."""
        import asyncio
        from openclaw.gateway.discovery import GatewayDiscovery
        monkeypatch.setenv("OPENCLAW_DISABLE_BONJOUR", "1")
        gw = GatewayDiscovery()
        asyncio.run(gw.start())
        assert gw.zeroconf is None  # Should not have started


# ===========================================================================
# 6. subagents sessions_spawn tool schema
# ===========================================================================

class TestSessionsSpawnToolSchema:
    """Tests for updated sessions_spawn schema: task/label/agentId/model/etc."""

    def _get_tool(self):
        from openclaw.agents.tools.sessions import SessionsSpawnTool
        return SessionsSpawnTool()

    def test_schema_has_task_field(self):
        tool = self._get_tool()
        schema = tool.get_schema()
        assert "task" in schema["properties"]
        assert "task" in schema["required"]

    def test_schema_has_label_field(self):
        tool = self._get_tool()
        schema = tool.get_schema()
        assert "label" in schema["properties"]

    def test_schema_has_agent_id_field(self):
        tool = self._get_tool()
        schema = tool.get_schema()
        assert "agentId" in schema["properties"]

    def test_schema_has_model_field(self):
        tool = self._get_tool()
        schema = tool.get_schema()
        assert "model" in schema["properties"]

    def test_schema_has_cleanup_enum(self):
        tool = self._get_tool()
        schema = tool.get_schema()
        assert "cleanup" in schema["properties"]
        assert schema["properties"]["cleanup"].get("enum") == ["delete", "keep"]

    def test_schema_has_run_timeout_seconds(self):
        tool = self._get_tool()
        schema = tool.get_schema()
        assert "runTimeoutSeconds" in schema["properties"]
        assert schema["properties"]["runTimeoutSeconds"]["type"] == "number"

    def test_schema_has_thinking_field(self):
        tool = self._get_tool()
        schema = tool.get_schema()
        assert "thinking" in schema["properties"]

    def test_schema_does_not_have_session_id_or_initial_message(self):
        """Old schema fields should be replaced by new ones."""
        tool = self._get_tool()
        schema = tool.get_schema()
        # Old fields removed
        assert "session_id" not in schema["properties"]
        assert "initial_message" not in schema["properties"]

    @pytest.mark.asyncio
    async def test_execute_requires_task(self):
        tool = self._get_tool()
        result = await tool.execute({"label": "test"})
        assert not result.success
        assert "task" in result.error

    @pytest.mark.asyncio
    async def test_execute_succeeds_with_task(self):
        tool = self._get_tool()
        result = await tool.execute({"task": "Do something useful"})
        assert result.success
        meta = result.metadata or {}
        assert "sessionKey" in meta


# ===========================================================================
# 7. system_presence (TTL, max entries, normalize_presence_key)
# ===========================================================================

class TestSystemPresence:
    """Tests for system_presence.py TTL and max entries alignment."""

    def setup_method(self):
        """Clear registry before each test."""
        from openclaw.infra.system_presence import get_raw_presence_entries
        get_raw_presence_entries().clear()

    def test_ttl_ms_is_5_minutes(self):
        from openclaw.infra.system_presence import TTL_MS
        assert TTL_MS == 5 * 60 * 1000

    def test_max_entries_is_200(self):
        from openclaw.infra.system_presence import MAX_ENTRIES
        assert MAX_ENTRIES == 200

    def test_normalize_presence_key_lowercase(self):
        from openclaw.infra.system_presence import normalize_presence_key
        assert normalize_presence_key("MyDevice") == "mydevice"

    def test_normalize_presence_key_strips_whitespace(self):
        from openclaw.infra.system_presence import normalize_presence_key
        assert normalize_presence_key("  host  ") == "host"

    def test_normalize_presence_key_none_returns_none(self):
        from openclaw.infra.system_presence import normalize_presence_key
        assert normalize_presence_key(None) is None
        assert normalize_presence_key("") is None
        assert normalize_presence_key("   ") is None

    def test_update_system_presence_creates_entry(self):
        from openclaw.infra.system_presence import update_system_presence, get_raw_presence_entries
        update_system_presence("host1", {"host": "host1", "version": "1.0"})
        assert "host1" in get_raw_presence_entries()

    def test_update_system_presence_merges_fields(self):
        from openclaw.infra.system_presence import update_system_presence, get_raw_presence_entries
        update_system_presence("host1", {"host": "host1", "version": "1.0"})
        update_system_presence("host1", {"mode": "gateway"})
        entry = get_raw_presence_entries()["host1"]
        assert entry.host == "host1"
        assert entry.mode == "gateway"

    def test_update_system_presence_tracks_changes(self):
        from openclaw.infra.system_presence import update_system_presence
        update_system_presence("host1", {"host": "host1", "version": "1.0"})
        result = update_system_presence("host1", {"host": "host1", "version": "2.0"})
        assert "version" in result.changed_keys

    def test_list_system_presence_prunes_expired(self):
        from openclaw.infra.system_presence import (
            update_system_presence, list_system_presence, get_raw_presence_entries, TTL_MS
        )
        update_system_presence("old", {"host": "old"})
        # Manually set ts to expired
        entry = get_raw_presence_entries()["old"]
        entry.ts = entry.ts - TTL_MS - 1000
        result = list_system_presence()
        assert not any(e.get("id") == "old" for e in result)

    def test_list_system_presence_sorted_by_ts_desc(self):
        from openclaw.infra.system_presence import update_system_presence, list_system_presence
        import time
        update_system_presence("a", {"host": "a"})
        time.sleep(0.01)
        update_system_presence("b", {"host": "b"})
        result = list_system_presence()
        if len(result) >= 2:
            assert result[0]["ts"] >= result[1]["ts"]

    def test_max_entries_pruned_lru(self):
        from openclaw.infra.system_presence import (
            get_raw_presence_entries, _prune_registry, MAX_ENTRIES, SystemPresence
        )
        reg = get_raw_presence_entries()
        reg.clear()
        # Add MAX_ENTRIES + 5 entries with different ts values
        import time
        now_ms = int(time.time() * 1000)
        for i in range(MAX_ENTRIES + 5):
            p = SystemPresence(id=f"h{i}", ts=now_ms + i)
            reg[f"h{i}"] = p
        _prune_registry()
        assert len(reg) <= MAX_ENTRIES
        # The oldest (lowest ts, i.e. h0..h4) should be pruned
        assert "h0" not in reg
        assert f"h{MAX_ENTRIES + 4}" in reg
