"""
Bootstrap file loading and injection

Automatically loads workspace context files (AGENTS.md, SOUL.md, etc.)
and formats them for injection into the system prompt.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, NamedTuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Bootstrap size constants — aligned with TS DEFAULT_BOOTSTRAP_MAX_CHARS
# ---------------------------------------------------------------------------

DEFAULT_BOOTSTRAP_MAX_CHARS: int = 20_000
DEFAULT_BOOTSTRAP_TOTAL_MAX_CHARS: int = 150_000


def resolve_bootstrap_max_chars(cfg: Any = None) -> int:
    """Return bootstrapMaxChars from config, or the default 20000.

    Mirrors TS resolveBootstrapMaxChars(cfg?: OpenClawConfig): number.
    Config key: agents.defaults.bootstrapMaxChars
    """
    try:
        if cfg and isinstance(cfg, dict):
            raw = cfg.get("agents", {}).get("defaults", {}).get("bootstrapMaxChars")
            if isinstance(raw, (int, float)) and raw > 0:
                return int(raw)
    except Exception:
        pass
    return DEFAULT_BOOTSTRAP_MAX_CHARS


def resolve_bootstrap_total_max_chars(cfg: Any = None) -> int:
    """Return bootstrapTotalMaxChars from config, or the default 150000.

    Mirrors TS resolveBootstrapTotalMaxChars(cfg?: OpenClawConfig): number.
    Config key: agents.defaults.bootstrapTotalMaxChars
    """
    try:
        if cfg and isinstance(cfg, dict):
            raw = cfg.get("agents", {}).get("defaults", {}).get("bootstrapTotalMaxChars")
            if isinstance(raw, (int, float)) and raw > 0:
                return int(raw)
    except Exception:
        pass
    return DEFAULT_BOOTSTRAP_TOTAL_MAX_CHARS


class BootstrapFile(NamedTuple):
    """Bootstrap file with metadata"""
    path: str
    content: str
    truncated: bool = False


def resolve_memory_bootstrap_entries(workspace_dir: Path) -> list[tuple[str, Path]]:
    """Resolve memory bootstrap files injected into the system prompt.

    Scans:
    1. Root-level MEMORY.md / memory.md
    2. All *.md files inside the memory/ subdirectory (mirrors TS workspace.ts)

    Deduplicates symlinks and case-insensitive filesystem duplicates (macOS/Windows).

    Args:
        workspace_dir: Workspace directory

    Returns:
        List of (filename, path) tuples for memory files found, sorted alphabetically
    """
    raw_entries: list[tuple[str, Path]] = []

    # 1. Root-level MEMORY.md / memory.md
    for filename in ("MEMORY.md", "memory.md"):
        path = workspace_dir / filename
        if path.exists():
            raw_entries.append((filename, path))

    # 2. memory/ subdirectory — all *.md files (matches TS)
    memory_dir = workspace_dir / "memory"
    if memory_dir.is_dir():
        for md_file in sorted(memory_dir.glob("*.md")):
            if md_file.is_file():
                raw_entries.append((f"memory/{md_file.name}", md_file))

    if not raw_entries:
        return []

    # Deduplicate symlinks and case-insensitive filesystem duplicates
    seen: set[str] = set()
    deduped: list[tuple[str, Path]] = []

    for filename, path in raw_entries:
        try:
            real_path = path.resolve()
            real_path_lower = str(real_path).lower()
        except Exception:
            real_path = path
            real_path_lower = str(path).lower()

        if real_path_lower not in seen:
            seen.add(real_path_lower)
            deduped.append((filename, path))
        else:
            logger.debug(
                f"Skipping duplicate memory file {filename} "
                f"(duplicate or symlink to {real_path})"
            )

    return deduped


def load_bootstrap_files(
    workspace_dir: Path,
    max_chars_per_file: int | None = None,
    cfg: Any = None,
) -> list[BootstrapFile]:
    """
    Load workspace bootstrap files

    Files loaded (in order):
    - AGENTS.md: Project guidelines and conventions
    - SOUL.md: Persona definition
    - TOOLS.md: Tool usage instructions
    - IDENTITY.md: Identity configuration
    - USER.md: User information
    - HEARTBEAT.md: Heartbeat configuration
    - BOOTSTRAP.md: Bootstrap instructions (for new workspaces)

    Args:
        workspace_dir: Workspace directory
        max_chars_per_file: Maximum characters per file (truncate if exceeded).
            Defaults to ``resolve_bootstrap_max_chars(cfg)``.
        cfg: Optional config dict for resolving bootstrap max chars.
    
    Returns:
        List of BootstrapFile objects
    """
    if max_chars_per_file is None:
        max_chars_per_file = resolve_bootstrap_max_chars(cfg)

    bootstrap_files = [
        "AGENTS.md",
        "SOUL.md",
        "TOOLS.md",
        "IDENTITY.md",
        "USER.md",
        "HEARTBEAT.md",
        "BOOTSTRAP.md",
    ]
    # Note: BOOT.md is loaded separately (not via this list) — it has special
    # execution semantics distinct from the regular bootstrap context.
    
    results = []
    
    # Load standard bootstrap files
    for filename in bootstrap_files:
        file_path = workspace_dir / filename
        
        if not file_path.exists():
            # Inject missing file marker
            results.append(BootstrapFile(
                path=filename,
                content=f"(File {filename} not found in workspace)",
                truncated=False
            ))
            continue
        
        try:
            content = file_path.read_text(encoding="utf-8")
            
            # Truncate if too long (matching TypeScript behavior: 70% head + 20% tail)
            truncated = False
            if len(content) > max_chars_per_file:
                head_chars = int(max_chars_per_file * 0.7)
                tail_chars = int(max_chars_per_file * 0.2)
                
                head = content[:head_chars]
                tail = content[-tail_chars:]
                
                # Add truncation marker
                truncation_marker = (
                    f"\n\n... (truncated: file exceeded {max_chars_per_file} chars; "
                    f"showing first {head_chars} + last {tail_chars} chars) ...\n\n"
                )
                
                content = head + truncation_marker + tail
                truncated = True
            
            results.append(BootstrapFile(
                path=filename,
                content=content,
                truncated=truncated
            ))
            
            if truncated:
                logger.warning(
                    f"Bootstrap file {filename} truncated "
                    f"(exceeded {max_chars_per_file} chars)"
                )
            else:
                logger.debug(f"Loaded bootstrap file {filename} ({len(content)} chars)")
        
        except Exception as e:
            logger.error(f"Failed to read bootstrap file {filename}: {e}")
            results.append(BootstrapFile(
                path=filename,
                content=f"(Error reading {filename}: {e})",
                truncated=False
            ))
    
    # Load memory files (MEMORY.md or memory.md with symlink deduplication)
    memory_entries = resolve_memory_bootstrap_entries(workspace_dir)
    
    for filename, file_path in memory_entries:
        try:
            content = file_path.read_text(encoding="utf-8")
            
            # Apply same truncation logic
            truncated = False
            if len(content) > max_chars_per_file:
                head_chars = int(max_chars_per_file * 0.7)
                tail_chars = int(max_chars_per_file * 0.2)
                
                head = content[:head_chars]
                tail = content[-tail_chars:]
                
                truncation_marker = (
                    f"\n\n... (truncated: file exceeded {max_chars_per_file} chars; "
                    f"showing first {head_chars} + last {tail_chars} chars) ...\n\n"
                )
                
                content = head + truncation_marker + tail
                truncated = True
            
            results.append(BootstrapFile(
                path=filename,
                content=content,
                truncated=truncated
            ))
            
            if truncated:
                logger.warning(
                    f"Bootstrap file {filename} truncated "
                    f"(exceeded {max_chars_per_file} chars)"
                )
            else:
                logger.debug(f"Loaded bootstrap file {filename} ({len(content)} chars)")
        
        except Exception as e:
            logger.error(f"Failed to read memory file {filename}: {e}")
            results.append(BootstrapFile(
                path=filename,
                content=f"(Error reading {filename}: {e})",
                truncated=False
            ))
    
    return results


def format_bootstrap_context(files: list[BootstrapFile]) -> list[dict]:
    """
    Format bootstrap files as context_files list for system prompt injection
    
    Args:
        files: List of BootstrapFile objects
    
    Returns:
        List of dicts with 'path' and 'content' keys (ready for system prompt)
    """
    if not files:
        return []
    
    context_files = []
    
    for file in files:
        # Skip missing files (unless we want to show the marker)
        if "(File" in file.content and "not found" in file.content:
            # Optionally skip missing files, or include the marker
            continue
        
        context_files.append({
            "path": file.path,
            "content": file.content
        })
    
    return context_files


def format_bootstrap_context_string(files: list[BootstrapFile]) -> str:
    """
    Format bootstrap files as a complete string for legacy injection
    
    This formats the files the same way as TypeScript's buildBootstrapContextFiles.
    
    Args:
        files: List of BootstrapFile objects
    
    Returns:
        Formatted Project Context section as a string
    """
    if not files:
        return ""
    
    lines = [
        "# Project Context",
        "",
        "The following project context files have been loaded:",
        "",
    ]
    
    # Check if SOUL.md is present (and not missing)
    has_soul = any(
        f.path == "SOUL.md" and "(File" not in f.content
        for f in files
    )
    
    if has_soul:
        lines.extend([
            "If SOUL.md is present, embody its persona and tone.",
            "Avoid stiff, generic replies; follow its guidance unless higher-priority instructions override it.",
            "",
        ])
    
    # Add each file
    for file in files:
        lines.extend([
            f"## {file.path}",
            "",
            file.content,
            "",
        ])
    
    return "\n".join(lines)
