"""Tests for tool policy system (matching TS tool-policy.ts)"""

import pytest
from openclaw.security.tool_policy import (
    OWNER_ONLY_TOOL_NAMES,
    TOOL_GROUPS,
    TOOL_NAME_ALIASES,
    TOOL_PROFILES,
    SandboxMode,
    ToolPolicy,
    ToolPolicyResolver,
    ToolProfilePolicy,
    apply_owner_only_tool_policy,
    expand_tool_groups,
    is_owner_only_tool_name,
    normalize_tool_list,
    normalize_tool_name,
    resolve_tool_profile_policy,
    get_profile_policy,
)


class TestToolNameAliases:
    def test_bash_to_exec(self):
        # TS ground truth: TOOL_NAME_ALIASES = {bash: "exec", "apply-patch": "apply_patch"}
        assert normalize_tool_name("bash") == "exec"

    def test_apply_dash_patch(self):
        assert normalize_tool_name("apply-patch") == "apply_patch"

    def test_no_alias_read(self):
        # TS canonical name for file read is "read" (no alias)
        assert normalize_tool_name("read") == "read"

    def test_no_alias_write(self):
        assert normalize_tool_name("write") == "write"

    def test_no_alias_edit(self):
        assert normalize_tool_name("edit") == "edit"

    def test_no_alias_exec(self):
        # "exec" is already canonical — no reverse alias
        assert normalize_tool_name("exec") == "exec"

    def test_no_alias_web_search(self):
        assert normalize_tool_name("web_search") == "web_search"

    def test_case_insensitive(self):
        # BASH → exec (bash alias, case-insensitive)
        assert normalize_tool_name("BASH") == "exec"
        # READ → read (no alias)
        assert normalize_tool_name("Read") == "read"


class TestNormalizeToolList:
    def test_basic(self):
        # bash→exec, read→read (no alias), exec→exec (no alias)
        result = normalize_tool_list(["bash", "read", "exec"])
        assert result == ["exec", "read", "exec"]

    def test_none(self):
        assert normalize_tool_list(None) == []

    def test_empty(self):
        assert normalize_tool_list([]) == []


class TestToolGroups:
    def test_all_groups_present(self):
        expected = [
            "group:memory", "group:web", "group:fs", "group:runtime",
            "group:sessions", "group:ui", "group:automation",
            "group:messaging", "group:nodes", "group:openclaw",
        ]
        for group in expected:
            assert group in TOOL_GROUPS, f"Missing group: {group}"

    def test_fs_group(self):
        # TS canonical names: read, write, edit, apply_patch
        assert "read" in TOOL_GROUPS["group:fs"]
        assert "write" in TOOL_GROUPS["group:fs"]
        assert "edit" in TOOL_GROUPS["group:fs"]
        assert "apply_patch" in TOOL_GROUPS["group:fs"]

    def test_runtime_group(self):
        # TS canonical: exec (not bash), process
        assert "exec" in TOOL_GROUPS["group:runtime"]
        assert "process" in TOOL_GROUPS["group:runtime"]

    def test_sessions_group(self):
        assert "sessions_list" in TOOL_GROUPS["group:sessions"]
        assert "sessions_spawn" in TOOL_GROUPS["group:sessions"]
        assert "session_status" in TOOL_GROUPS["group:sessions"]


class TestExpandToolGroups:
    def test_expand_fs(self):
        result = expand_tool_groups(["group:fs"])
        assert "read" in result
        assert "write" in result
        assert "edit" in result
        assert "apply_patch" in result

    def test_expand_mixed(self):
        result = expand_tool_groups(["group:fs", "group:runtime", "image"])
        assert "read" in result
        assert "exec" in result
        assert "image" in result

    def test_dedup(self):
        result = expand_tool_groups(["group:fs", "read"])
        assert result.count("read") == 1

    def test_none(self):
        assert expand_tool_groups(None) == []

    def test_alias_in_group(self):
        # "bash" normalizes to "exec", which is not a group, so stays as "exec"
        result = expand_tool_groups(["bash"])
        assert "exec" in result


class TestToolProfiles:
    def test_minimal(self):
        p = TOOL_PROFILES["minimal"]
        assert p.allow == ["session_status"]

    def test_coding(self):
        p = TOOL_PROFILES["coding"]
        assert "group:fs" in p.allow
        assert "group:runtime" in p.allow
        assert "image" in p.allow

    def test_messaging(self):
        p = TOOL_PROFILES["messaging"]
        assert "group:messaging" in p.allow

    def test_full(self):
        p = TOOL_PROFILES["full"]
        assert p.allow is None
        assert p.deny is None


class TestResolveToolProfilePolicy:
    def test_minimal(self):
        policy = resolve_tool_profile_policy("minimal")
        assert policy is not None
        assert "session_status" in policy.allow

    def test_full(self):
        policy = resolve_tool_profile_policy("full")
        assert policy is None  # No restrictions

    def test_unknown(self):
        assert resolve_tool_profile_policy("nonexistent") is None

    def test_none(self):
        assert resolve_tool_profile_policy(None) is None


class TestOwnerOnlyTools:
    def test_whatsapp_login(self):
        assert is_owner_only_tool_name("whatsapp_login")

    def test_cron_owner_only(self):
        assert is_owner_only_tool_name("cron")

    def test_gateway_owner_only(self):
        assert is_owner_only_tool_name("gateway")

    def test_regular_tool(self):
        # exec (bash) is NOT owner-only at the openclaw admin level
        assert not is_owner_only_tool_name("bash")
        assert not is_owner_only_tool_name("exec")
        assert not is_owner_only_tool_name("read")


class TestApplyOwnerOnlyToolPolicy:
    class FakeTool:
        def __init__(self, name):
            self.name = name

    def test_owner_keeps_all(self):
        tools = [self.FakeTool("bash"), self.FakeTool("whatsapp_login")]
        result = apply_owner_only_tool_policy(tools, True)
        assert len(result) == 2

    def test_non_owner_filters(self):
        tools = [self.FakeTool("bash"), self.FakeTool("whatsapp_login")]
        result = apply_owner_only_tool_policy(tools, False)
        assert len(result) == 1
        assert result[0].name == "bash"


class TestToolPolicy:
    def test_allow_all(self):
        p = ToolPolicy()
        assert p.is_allowed("anything")

    def test_deny(self):
        # deny=["bash"] → self.deny=["exec"] (bash→exec alias)
        p = ToolPolicy(deny=["bash"])
        assert not p.is_allowed("bash")   # bash→exec in deny
        assert not p.is_allowed("exec")   # exec directly in deny
        assert p.is_allowed("read")

    def test_allow_list(self):
        p = ToolPolicy(allow=["bash", "read"])
        assert p.is_allowed("bash")   # bash→exec, exec in allow
        assert p.is_allowed("exec")   # exec in allow
        assert not p.is_allowed("web_search")

    def test_deny_precedence(self):
        # allow=["bash"] → allow=["exec"], deny=["bash"] → deny=["exec"]
        # deny takes precedence → exec denied
        p = ToolPolicy(allow=["bash"], deny=["bash"])
        assert not p.is_allowed("bash")
        assert not p.is_allowed("exec")

    def test_wildcard(self):
        p = ToolPolicy(allow=["*"])
        assert p.is_allowed("anything")

    def test_group_expansion(self):
        # group:fs = [read, write, edit, apply_patch]
        p = ToolPolicy(allow=["group:fs"])
        assert p.is_allowed("read")
        assert p.is_allowed("write")
        assert not p.is_allowed("exec")

    def test_alias_resolution(self):
        # deny=["bash"] → deny=["exec"]; checking "exec" should be denied
        p = ToolPolicy(deny=["bash"])
        assert not p.is_allowed("exec")


class TestToolPolicyResolver:
    def test_global_deny(self):
        resolver = ToolPolicyResolver({
            "tools": {"deny": ["browser"]},
        })
        allowed, reason = resolver.is_tool_allowed("browser", "main")
        assert not allowed
        assert "denied" in reason

    def test_global_allow(self):
        resolver = ToolPolicyResolver({
            "tools": {"allow": ["bash"]},
        })
        allowed, _ = resolver.is_tool_allowed("bash", "main")
        assert allowed

    def test_agent_specific(self):
        resolver = ToolPolicyResolver({
            "agents": {
                "myagent": {"tools": {"deny": ["web_search"]}},
            },
        })
        allowed, _ = resolver.is_tool_allowed("web_search", "myagent")
        assert not allowed

    def test_sandbox_mode(self):
        resolver = ToolPolicyResolver({
            "agents": {
                "defaults": {
                    "sandbox": {
                        "mode": "non-main",
                        "tools": {"allow": ["bash"]},
                    },
                },
            },
        })
        # Main session: no sandbox
        allowed, _ = resolver.is_tool_allowed("web_search", "agent", is_main_session=True)
        assert allowed

        # Non-main session: sandbox applies
        allowed, _ = resolver.is_tool_allowed("web_search", "agent", is_main_session=False)
        assert not allowed


class TestGetProfilePolicy:
    def test_ts_profiles(self):
        for name in ("minimal", "coding", "messaging"):
            p = get_profile_policy(name)
            assert p is not None

    def test_full_returns_none_restriction(self):
        # "full" has no restrictions, so expanded policy is empty
        p = get_profile_policy("full")
        assert p is None  # full → resolve returns None

    def test_legacy_profiles(self):
        for name in ("safe", "restricted"):
            p = get_profile_policy(name)
            assert p is not None

    def test_unknown(self):
        assert get_profile_policy("nonexistent") is None
