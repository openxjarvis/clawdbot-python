"""Skills system — backward-compatibility shim.

The canonical skills implementation lives in ``openclaw.agents.skills``.
This package re-exports from there so existing callers keep working, while
also exposing the simpler ``SkillLoader`` / ``SkillMetadata`` API for tests
and lightweight consumers that do not need the full workspace resolver.
"""
from __future__ import annotations

# Re-export the full agents.skills public API so callers can do:
#   from openclaw.skills import Skill, load_skills_from_dir, ...
from openclaw.agents.skills import (  # noqa: F401
    OpenClawSkillMetadata,
    Skill as AgentSkill,
    SkillEntry,
    SkillRequires,
    SkillSnapshot,
    build_workspace_skill_snapshot,
    build_workspace_skills_prompt,
    load_skills_from_dir,
    load_workspace_skill_entries,
)

load_skill_entries = load_workspace_skill_entries  # noqa: F401

__all__ = [
    # agents.skills re-exports
    "AgentSkill",
    "SkillEntry",
    "SkillRequires",
    "SkillSnapshot",
    "OpenClawSkillMetadata",
    "load_skills_from_dir",
    "load_skill_entries",
    "load_workspace_skill_entries",
    "build_workspace_skills_prompt",
    "build_workspace_skill_snapshot",
    # Legacy simple API (loader, types, eligibility) — still importable via
    #   from openclaw.skills.loader import SkillLoader
    #   from openclaw.skills.types import Skill, SkillMetadata
]
