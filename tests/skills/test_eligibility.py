"""
Tests for skill eligibility checking.
"""
import platform

import pytest

from openclaw.agents.skills.types import (
    Skill,
    SkillEntry,
    OpenClawSkillMetadata,
    SkillRequires,
    SkillEligibilityContext
)
from openclaw.agents.skills.eligibility import (
    should_include_skill,
    check_skill_requirements,
    build_eligibility_context
)


def test_build_eligibility_context():
    """Test building eligibility context from environment"""
    ctx = build_eligibility_context()

    assert ctx.platform in ["darwin", "linux", "win32"]
    assert isinstance(ctx.available_bins, set)
    assert isinstance(ctx.env_vars, dict)


def test_skill_always_included():
    """Test that skills marked with 'always' are always included"""
    skill = Skill(
        name="test",
        description="Test",
        location="/test",
        metadata=OpenClawSkillMetadata(always=True),
    )

    entry = SkillEntry(skill=skill, source="test", source_dir="/test")

    ctx = SkillEligibilityContext(
        platform="darwin",
        available_bins=set(),
        env_vars={},
    )

    # Should be included even with no bins/env
    assert should_include_skill(entry, None, ctx)


def test_skill_os_requirement():
    """Test OS requirement checking"""
    skill = Skill(
        name="test",
        description="Test",
        location="/test",
        metadata=OpenClawSkillMetadata(os=["linux"]),
    )

    entry = SkillEntry(skill=skill, source="test", source_dir="/test")

    darwin_ctx = SkillEligibilityContext(
        platform="darwin",
        available_bins=set(),
        env_vars={},
    )

    linux_ctx = SkillEligibilityContext(
        platform="linux",
        available_bins=set(),
        env_vars={},
    )

    assert not should_include_skill(entry, None, darwin_ctx)
    assert should_include_skill(entry, None, linux_ctx)


def test_skill_bin_requirement():
    """Test binary requirement checking"""
    requires = SkillRequires(bins=["git", "gh"])

    ctx_missing = SkillEligibilityContext(
        platform="darwin",
        available_bins={"git"},
        env_vars={},
    )

    ctx_has_both = SkillEligibilityContext(
        platform="darwin",
        available_bins={"git", "gh"},
        env_vars={},
    )

    assert not check_skill_requirements(requires, ctx_missing, None)
    assert check_skill_requirements(requires, ctx_has_both, None)


def test_skill_any_bins_requirement():
    """Test any_bins requirement (at least one must exist)"""
    requires = SkillRequires(any_bins=["npm", "yarn", "pnpm"])

    ctx_none = SkillEligibilityContext(
        platform="darwin",
        available_bins=set(),
        env_vars={},
    )

    ctx_has_one = SkillEligibilityContext(
        platform="darwin",
        available_bins={"yarn"},
        env_vars={},
    )

    assert not check_skill_requirements(requires, ctx_none, None)
    assert check_skill_requirements(requires, ctx_has_one, None)


def test_skill_env_requirement():
    """Test environment variable requirement checking"""
    requires = SkillRequires(env=["OPENAI_API_KEY"])

    ctx_no_env = SkillEligibilityContext(
        platform="darwin",
        available_bins=set(),
        env_vars={},
    )

    ctx_has_env = SkillEligibilityContext(
        platform="darwin",
        available_bins=set(),
        env_vars={"OPENAI_API_KEY": "sk-xxx"},
    )

    assert not check_skill_requirements(requires, ctx_no_env, None)
    assert check_skill_requirements(requires, ctx_has_env, None)


def test_skill_config_requirement():
    """Test config path requirement checking"""
    requires = SkillRequires(config=["api.keys.openai"])

    ctx = SkillEligibilityContext(
        platform="darwin",
        available_bins=set(),
        env_vars={},
    )

    config_missing = {"api": {"keys": {}}}
    config_has = {"api": {"keys": {"openai": "sk-xxx"}}}

    assert not check_skill_requirements(requires, ctx, config_missing)
    assert check_skill_requirements(requires, ctx, config_has)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
