"""Skill snapshot resolution for cron isolated agent runs.

Mirrors TypeScript: openclaw/src/cron/isolated-agent/skills-snapshot.ts
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def resolve_cron_skills_snapshot(
    workspace_dir: str,
    config: Any,
    agent_id: str,
    existing_snapshot: Any | None = None,
    is_fast_test_env: bool = False,
) -> Any:
    """Resolve and (if stale) rebuild the workspace skills snapshot for a cron job run.

    Mirrors TS resolveCronSkillsSnapshot.  Returns a SkillSnapshot object.

    Args:
        workspace_dir: Path to the workspace root directory.
        config: OpenClaw configuration object/dict.
        agent_id: Agent ID whose skill filter should be applied.
        existing_snapshot: Previously built snapshot to compare against.
        is_fast_test_env: When True, skip filesystem scans (used in unit tests).

    Returns:
        SkillSnapshot (from openclaw.agents.skills.types).
    """
    from openclaw.agents.skills import SkillSnapshot, build_workspace_skill_snapshot
    from openclaw.agents.skills.refresh import get_skills_snapshot_version

    if is_fast_test_env:
        return existing_snapshot or SkillSnapshot(prompt="", skills=[])

    snapshot_version = get_skills_snapshot_version()

    # Determine whether a refresh is needed
    if existing_snapshot is not None:
        existing_version = getattr(existing_snapshot, "version", None)
        if existing_version == snapshot_version:
            return existing_snapshot

    try:
        return build_workspace_skill_snapshot(workspace_dir, config)
    except Exception as exc:
        logger.warning(
            f"resolve_cron_skills_snapshot: failed to build skill snapshot "
            f"for agent {agent_id!r}: {exc}"
        )
        return existing_snapshot or SkillSnapshot(prompt="", skills=[])
