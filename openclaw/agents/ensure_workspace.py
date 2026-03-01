"""Workspace initialization and bootstrap file management.

Matches TypeScript src/agents/workspace.ts ensureAgentWorkspace() including:
- Template file creation (write-if-missing)
- workspace-state.json auto-detection (bootstrapSeededAt, onboardingCompletedAt)
- Legacy migration: USER/IDENTITY divergence from template → onboarding complete
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Bootstrap file names (matching TypeScript constants)
DEFAULT_AGENTS_FILENAME = "AGENTS.md"
DEFAULT_SOUL_FILENAME = "SOUL.md"
DEFAULT_TOOLS_FILENAME = "TOOLS.md"
DEFAULT_IDENTITY_FILENAME = "IDENTITY.md"
DEFAULT_USER_FILENAME = "USER.md"
DEFAULT_HEARTBEAT_FILENAME = "HEARTBEAT.md"
DEFAULT_BOOTSTRAP_FILENAME = "BOOTSTRAP.md"
DEFAULT_BOOT_FILENAME = "BOOT.md"

# Workspace state — mirrors TS workspace.ts constants
WORKSPACE_STATE_DIRNAME = ".openclaw"
WORKSPACE_STATE_FILENAME = "workspace-state.json"
WORKSPACE_STATE_VERSION = 1


# ---------------------------------------------------------------------------
# Frontmatter / template helpers
# ---------------------------------------------------------------------------

def strip_frontmatter(content: str) -> str:
    """Strip YAML frontmatter from markdown content."""
    if not content.startswith("---\n"):
        return content
    lines = content.split("\n")
    for i in range(1, len(lines)):
        if lines[i] == "---":
            return "\n".join(lines[i + 1:]).lstrip()
    return content


def load_template(template_name: str) -> str:
    """Load a workspace template file with frontmatter stripped.

    Args:
        template_name: Name of template file (e.g. "SOUL.md")

    Returns:
        Template content with frontmatter stripped

    Raises:
        FileNotFoundError: If template file not found
    """
    templates_dir = Path(__file__).parent / "templates"
    template_path = templates_dir / template_name
    if not template_path.exists():
        raise FileNotFoundError(
            f"Missing workspace template: {template_name} ({template_path}). "
            "Ensure templates are packaged."
        )
    content = template_path.read_text(encoding="utf-8")
    return strip_frontmatter(content)


def _ensure_git_repo(workspace_dir: Path) -> None:
    """Initialize git repository in workspace if not present (TS alignment)"""
    git_dir = workspace_dir / ".git"
    if git_dir.exists():
        return
    
    # Check if git is available
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.debug("git not available, skipping workspace git init")
        return
    
    try:
        subprocess.run(["git", "init"], cwd=workspace_dir, capture_output=True, check=True)
        logger.info("Initialized git repository in workspace")
    except subprocess.CalledProcessError as e:
        logger.debug(f"Failed to init git: {e}")


def write_file_if_missing(file_path: Path, content: str) -> bool:
    """Write content to file only if it doesn't exist.

    Returns:
        True if file was created, False if it already existed.
    """
    if file_path.exists():
        return False
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        logger.info("Created workspace file: %s", file_path.name)
        return True
    except Exception as exc:
        logger.warning("Failed to create %s: %s", file_path.name, exc)
        return False


def is_brand_new_workspace(workspace_dir: Path) -> bool:
    """Return True if none of the core bootstrap files exist."""
    for filename in [
        DEFAULT_AGENTS_FILENAME, DEFAULT_SOUL_FILENAME, DEFAULT_TOOLS_FILENAME,
        DEFAULT_IDENTITY_FILENAME, DEFAULT_USER_FILENAME, DEFAULT_HEARTBEAT_FILENAME,
    ]:
        if (workspace_dir / filename).exists():
            return False
    return True


# ---------------------------------------------------------------------------
# workspace-state.json helpers — mirrors TS workspace.ts lines 143-213
# ---------------------------------------------------------------------------

def _resolve_workspace_state_path(workspace_dir: Path) -> Path:
    """Return {workspaceDir}/.openclaw/workspace-state.json."""
    return workspace_dir / WORKSPACE_STATE_DIRNAME / WORKSPACE_STATE_FILENAME


def _read_workspace_onboarding_state(state_path: Path) -> dict:
    """Read workspace-state.json; return empty state if missing/invalid."""
    try:
        raw = state_path.read_text(encoding="utf-8")
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return {"version": WORKSPACE_STATE_VERSION}
        return {
            "version": WORKSPACE_STATE_VERSION,
            "bootstrapSeededAt": parsed.get("bootstrapSeededAt")
                if isinstance(parsed.get("bootstrapSeededAt"), str) else None,
            "onboardingCompletedAt": parsed.get("onboardingCompletedAt")
                if isinstance(parsed.get("onboardingCompletedAt"), str) else None,
        }
    except FileNotFoundError:
        return {"version": WORKSPACE_STATE_VERSION}
    except Exception as exc:
        logger.debug("workspace-state.json read error: %s", exc)
        return {"version": WORKSPACE_STATE_VERSION}


def _write_workspace_onboarding_state(state_path: Path, state: dict) -> None:
    """Atomically write workspace-state.json (temp file + rename).

    Mirrors TS writeWorkspaceOnboardingState() atomic write pattern.
    """
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        {k: v for k, v in state.items() if v is not None},
        indent=2,
    ) + "\n"
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=state_path.parent,
        prefix=f"{state_path.name}.tmp-",
        suffix=".json",
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp_path, state_path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def is_workspace_onboarding_completed(workspace_dir: Path) -> bool:
    """Return True if workspace onboarding has been marked complete."""
    state_path = _resolve_workspace_state_path(workspace_dir)
    state = _read_workspace_onboarding_state(state_path)
    completed_at = state.get("onboardingCompletedAt")
    return isinstance(completed_at, str) and bool(completed_at.strip())


def read_workspace_state(workspace_dir: Path) -> dict:
    """Public helper — read workspace-state.json for the given dir."""
    return _read_workspace_onboarding_state(_resolve_workspace_state_path(workspace_dir))


def write_workspace_state(
    workspace_dir: Path,
    *,
    bootstrap_seeded_at: Optional[str] = None,
    onboarding_completed_at: Optional[str] = None,
) -> None:
    """Public helper — update workspace-state.json.

    Merges with existing state so callers only need to supply changed fields.
    Mirrors TypeScript onboarding.py write_workspace_state() but uses the
    correct .openclaw subdirectory path.
    """
    state_path = _resolve_workspace_state_path(workspace_dir)
    state = _read_workspace_onboarding_state(state_path)
    if bootstrap_seeded_at is not None:
        state["bootstrapSeededAt"] = bootstrap_seeded_at
    if onboarding_completed_at is not None:
        state["onboardingCompletedAt"] = onboarding_completed_at
    _write_workspace_onboarding_state(state_path, state)
    logger.debug("Updated workspace-state.json: %s", state_path)


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------

def ensure_agent_workspace(
    workspace_dir: str | Path,
    ensure_bootstrap_files: bool = True,
    skip_bootstrap: bool = False,
) -> dict[str, Any]:
    """Ensure agent workspace exists and has necessary bootstrap files.

    Matches TypeScript ensureAgentWorkspace() (workspace.ts lines 258-373):
    - Creates workspace directory if missing.
    - Writes template files only if they don't exist (write-if-missing).
    - BOOTSTRAP.md only created for brand-new workspaces.
    - Auto-detects and persists onboarding state in workspace-state.json:
      * bootstrapSeededAt  — set when BOOTSTRAP.md first exists
      * onboardingCompletedAt — set when BOOTSTRAP.md is deleted (or USER/IDENTITY
        diverge from templates — legacy migration path)

    Args:
        workspace_dir: Workspace directory path
        ensure_bootstrap_files: Whether to create bootstrap files
        skip_bootstrap: Skip bootstrap file creation entirely

    Returns:
        Dict with 'dir' key and optional per-file path keys.
    """
    if isinstance(workspace_dir, str):
        workspace_dir = Path(workspace_dir).expanduser().resolve()

    workspace_dir.mkdir(parents=True, exist_ok=True)
    logger.debug("Workspace directory: %s", workspace_dir)

    result: dict[str, Any] = {"dir": workspace_dir}

    if skip_bootstrap or not ensure_bootstrap_files:
        return result

    agents_path = workspace_dir / DEFAULT_AGENTS_FILENAME
    soul_path = workspace_dir / DEFAULT_SOUL_FILENAME
    tools_path = workspace_dir / DEFAULT_TOOLS_FILENAME
    identity_path = workspace_dir / DEFAULT_IDENTITY_FILENAME
    user_path = workspace_dir / DEFAULT_USER_FILENAME
    heartbeat_path = workspace_dir / DEFAULT_HEARTBEAT_FILENAME
    bootstrap_path = workspace_dir / DEFAULT_BOOTSTRAP_FILENAME
    boot_path = workspace_dir / DEFAULT_BOOT_FILENAME

    # Load templates
    try:
        agents_template = load_template(DEFAULT_AGENTS_FILENAME)
        soul_template = load_template(DEFAULT_SOUL_FILENAME)
        tools_template = load_template(DEFAULT_TOOLS_FILENAME)
        identity_template = load_template(DEFAULT_IDENTITY_FILENAME)
        user_template = load_template(DEFAULT_USER_FILENAME)
        heartbeat_template = load_template(DEFAULT_HEARTBEAT_FILENAME)
        bootstrap_template = load_template(DEFAULT_BOOTSTRAP_FILENAME)
    except FileNotFoundError as exc:
        logger.error("Failed to load templates: %s", exc)
        return result

    # Load BOOT.md template (non-fatal if missing)
    try:
        boot_template: str | None = load_template(DEFAULT_BOOT_FILENAME)
    except FileNotFoundError:
        boot_template = None

    # Write standard bootstrap files (write-if-missing)
    write_file_if_missing(agents_path, agents_template)
    write_file_if_missing(soul_path, soul_template)
    write_file_if_missing(tools_path, tools_template)
    write_file_if_missing(identity_path, identity_template)
    write_file_if_missing(user_path, user_template)
    write_file_if_missing(heartbeat_path, heartbeat_template)
    if boot_template is not None:
        write_file_if_missing(boot_path, boot_template)

    # -----------------------------------------------------------------------
    # workspace-state.json auto-detection — port of TS lines 316-360
    # -----------------------------------------------------------------------
    state_path = _resolve_workspace_state_path(workspace_dir)
    state = _read_workspace_onboarding_state(state_path)
    state_dirty = False

    def _mark_state(**kwargs: str) -> None:
        nonlocal state_dirty
        state.update(kwargs)
        state_dirty = True

    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    bootstrap_exists = bootstrap_path.exists()

    # Case 1: BOOTSTRAP.md exists but not yet tracked → record seed time
    if not state.get("bootstrapSeededAt") and bootstrap_exists:
        _mark_state(bootstrapSeededAt=_now_iso())

    # Case 2: Was seeded but BOOTSTRAP.md has been deleted → onboarding complete
    if not state.get("onboardingCompletedAt") and state.get("bootstrapSeededAt") and not bootstrap_exists:
        _mark_state(onboardingCompletedAt=_now_iso())

    # Case 3: No seed record and no BOOTSTRAP.md → legacy migration path
    if not state.get("bootstrapSeededAt") and not state.get("onboardingCompletedAt") and not bootstrap_exists:
        # If AGENTS.md, USER.md, or IDENTITY.md differ from their templates the
        # workspace was already personalised — treat as onboarding complete.
        try:
            agents_content = agents_path.read_text(encoding="utf-8") if agents_path.exists() else ""
            identity_content = identity_path.read_text(encoding="utf-8") if identity_path.exists() else ""
            user_content = user_path.read_text(encoding="utf-8") if user_path.exists() else ""
            legacy_completed = (
                agents_content != agents_template
                or identity_content != identity_template
                or user_content != user_template
            )
        except Exception:
            legacy_completed = False

        if legacy_completed:
            _mark_state(onboardingCompletedAt=_now_iso())
        else:
            # Brand-new workspace — create BOOTSTRAP.md and record seed time
            wrote = write_file_if_missing(bootstrap_path, bootstrap_template)
            if not wrote:
                bootstrap_exists = bootstrap_path.exists()
            else:
                bootstrap_exists = True
            if bootstrap_exists and not state.get("bootstrapSeededAt"):
                _mark_state(bootstrapSeededAt=_now_iso())

    if state_dirty:
        try:
            _write_workspace_onboarding_state(state_path, state)
        except Exception as exc:
            logger.warning("Failed to write workspace-state.json: %s", exc)

    # -----------------------------------------------------------------------
    # Git repository initialization (TS alignment)
    # -----------------------------------------------------------------------
    # Only initialize git for brand-new workspaces (matches TS workspace.ts lines 361-373)
    if not state.get("onboardingCompletedAt"):
        _ensure_git_repo(workspace_dir)

    result.update({
        "agents_path": agents_path,
        "soul_path": soul_path,
        "tools_path": tools_path,
        "identity_path": identity_path,
        "user_path": user_path,
        "heartbeat_path": heartbeat_path,
        "bootstrap_path": bootstrap_path,
        "boot_path": boot_path if boot_path.exists() else None,
    })
    return result


__all__ = [
    "ensure_agent_workspace",
    "load_template",
    "write_file_if_missing",
    "is_brand_new_workspace",
    "is_workspace_onboarding_completed",
    "read_workspace_state",
    "write_workspace_state",
    "DEFAULT_AGENTS_FILENAME",
    "DEFAULT_SOUL_FILENAME",
    "DEFAULT_TOOLS_FILENAME",
    "DEFAULT_IDENTITY_FILENAME",
    "DEFAULT_USER_FILENAME",
    "DEFAULT_HEARTBEAT_FILENAME",
    "DEFAULT_BOOTSTRAP_FILENAME",
    "DEFAULT_BOOT_FILENAME",
    "WORKSPACE_STATE_DIRNAME",
    "WORKSPACE_STATE_FILENAME",
]
