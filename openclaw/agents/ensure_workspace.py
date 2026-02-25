"""Workspace initialization and bootstrap file management.

Matches TypeScript src/agents/workspace.ts ensureAgentWorkspace()
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

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


def strip_frontmatter(content: str) -> str:
    """Strip YAML frontmatter from markdown content.
    
    Args:
        content: Markdown content potentially with frontmatter
        
    Returns:
        Content without frontmatter
    """
    if not content.startswith("---\n"):
        return content
    
    # Find end of frontmatter
    lines = content.split("\n")
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i] == "---":
            end_idx = i
            break
    
    if end_idx is None:
        return content
    
    # Return content after frontmatter
    return "\n".join(lines[end_idx + 1:]).lstrip()


def load_template(template_name: str) -> str:
    """Load a workspace template file.
    
    Args:
        template_name: Name of template file (e.g. "SOUL.md")
        
    Returns:
        Template content with frontmatter stripped
        
    Raises:
        FileNotFoundError: If template file not found
    """
    # Templates are in openclaw/agents/templates/
    templates_dir = Path(__file__).parent / "templates"
    template_path = templates_dir / template_name
    
    if not template_path.exists():
        raise FileNotFoundError(
            f"Missing workspace template: {template_name} ({template_path}). "
            "Ensure templates are packaged."
        )
    
    content = template_path.read_text(encoding="utf-8")
    return strip_frontmatter(content)


def write_file_if_missing(file_path: Path, content: str) -> bool:
    """Write content to file only if it doesn't exist.
    
    Args:
        file_path: Path to file
        content: Content to write
        
    Returns:
        True if file was created, False if it already existed
    """
    if file_path.exists():
        return False
    
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        logger.info(f"Created workspace file: {file_path.name}")
        return True
    except Exception as e:
        logger.warning(f"Failed to create {file_path.name}: {e}")
        return False


def is_brand_new_workspace(workspace_dir: Path) -> bool:
    """Check if workspace is brand new (no bootstrap files exist).
    
    Args:
        workspace_dir: Workspace directory path
        
    Returns:
        True if none of the bootstrap files exist
    """
    bootstrap_files = [
        DEFAULT_AGENTS_FILENAME,
        DEFAULT_SOUL_FILENAME,
        DEFAULT_TOOLS_FILENAME,
        DEFAULT_IDENTITY_FILENAME,
        DEFAULT_USER_FILENAME,
        DEFAULT_HEARTBEAT_FILENAME,
    ]
    
    for filename in bootstrap_files:
        if (workspace_dir / filename).exists():
            return False
    
    return True


def ensure_agent_workspace(
    workspace_dir: str | Path,
    ensure_bootstrap_files: bool = True,
    skip_bootstrap: bool = False,
) -> dict[str, Path]:
    """Ensure agent workspace exists and has necessary bootstrap files.
    
    Matches TypeScript ensureAgentWorkspace() behavior:
    - Creates workspace directory if missing
    - Writes template files if they don't exist
    - BOOTSTRAP.md only created for brand new workspaces
    
    Args:
        workspace_dir: Workspace directory path
        ensure_bootstrap_files: Whether to create bootstrap files
        skip_bootstrap: Skip bootstrap file creation entirely
        
    Returns:
        Dict with paths to workspace and bootstrap files
        
    Example:
        >>> paths = ensure_agent_workspace("~/.openclaw/workspace")
        >>> print(paths["dir"])
        PosixPath('/Users/user/.openclaw/workspace')
    """
    # Resolve and create workspace directory
    if isinstance(workspace_dir, str):
        workspace_dir = Path(workspace_dir).expanduser().resolve()
    
    workspace_dir.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Workspace directory: {workspace_dir}")
    
    result = {"dir": workspace_dir}
    
    if skip_bootstrap or not ensure_bootstrap_files:
        return result
    
    # Define file paths
    agents_path = workspace_dir / DEFAULT_AGENTS_FILENAME
    soul_path = workspace_dir / DEFAULT_SOUL_FILENAME
    tools_path = workspace_dir / DEFAULT_TOOLS_FILENAME
    identity_path = workspace_dir / DEFAULT_IDENTITY_FILENAME
    user_path = workspace_dir / DEFAULT_USER_FILENAME
    heartbeat_path = workspace_dir / DEFAULT_HEARTBEAT_FILENAME
    bootstrap_path = workspace_dir / DEFAULT_BOOTSTRAP_FILENAME
    boot_path = workspace_dir / DEFAULT_BOOT_FILENAME
    
    # Check if this is a brand new workspace
    is_new = is_brand_new_workspace(workspace_dir)
    
    # Load templates
    try:
        agents_template = load_template(DEFAULT_AGENTS_FILENAME)
        soul_template = load_template(DEFAULT_SOUL_FILENAME)
        tools_template = load_template(DEFAULT_TOOLS_FILENAME)
        identity_template = load_template(DEFAULT_IDENTITY_FILENAME)
        user_template = load_template(DEFAULT_USER_FILENAME)
        heartbeat_template = load_template(DEFAULT_HEARTBEAT_FILENAME)
        bootstrap_template = load_template(DEFAULT_BOOTSTRAP_FILENAME)
        boot_template = load_template(DEFAULT_BOOT_FILENAME)
    except FileNotFoundError as e:
        logger.error(f"Failed to load templates: {e}")
        return result
    
    # Write files if missing
    write_file_if_missing(agents_path, agents_template)
    write_file_if_missing(soul_path, soul_template)
    write_file_if_missing(tools_path, tools_template)
    write_file_if_missing(identity_path, identity_template)
    write_file_if_missing(user_path, user_template)
    write_file_if_missing(heartbeat_path, heartbeat_template)
    write_file_if_missing(boot_path, boot_template)
    
    # BOOTSTRAP.md only for brand new workspaces
    if is_new:
        write_file_if_missing(bootstrap_path, bootstrap_template)
    
    # Return all paths
    result.update({
        "agents_path": agents_path,
        "soul_path": soul_path,
        "tools_path": tools_path,
        "identity_path": identity_path,
        "user_path": user_path,
        "heartbeat_path": heartbeat_path,
        "bootstrap_path": bootstrap_path,
        "boot_path": boot_path,
    })
    
    return result


__all__ = [
    "ensure_agent_workspace",
    "load_template",
    "write_file_if_missing",
    "is_brand_new_workspace",
    "DEFAULT_AGENTS_FILENAME",
    "DEFAULT_SOUL_FILENAME",
    "DEFAULT_TOOLS_FILENAME",
    "DEFAULT_IDENTITY_FILENAME",
    "DEFAULT_USER_FILENAME",
    "DEFAULT_HEARTBEAT_FILENAME",
    "DEFAULT_BOOTSTRAP_FILENAME",
    "DEFAULT_BOOT_FILENAME",
]
