"""
Bootstrap file loading and injection

Automatically loads workspace context files (AGENTS.md, SOUL.md, etc.)
and formats them for injection into the system prompt.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import NamedTuple

logger = logging.getLogger(__name__)


class BootstrapFile(NamedTuple):
    """Bootstrap file with metadata"""
    path: str
    content: str
    truncated: bool = False


def resolve_memory_bootstrap_entries(workspace_dir: Path) -> list[tuple[str, Path]]:
    """
    Resolve memory bootstrap files (MEMORY.md or memory.md).
    
    Matches TypeScript workspace.ts#L375-409 (resolveMemoryBootstrapEntries).
    Checks both uppercase and lowercase variants, deduplicates symlinks and
    case-insensitive filesystem duplicates (macOS/Windows).
    
    Args:
        workspace_dir: Workspace directory
    
    Returns:
        List of (filename, path) tuples for memory files found
    """
    candidates = ["MEMORY.md", "memory.md"]
    entries = []
    
    for filename in candidates:
        path = workspace_dir / filename
        if path.exists():
            entries.append((filename, path))
    
    # If only one or no memory files found, return as-is
    if len(entries) <= 1:
        return entries
    
    # Deduplicate symlinks and case-insensitive duplicates
    seen = set()
    deduped = []
    
    for filename, path in entries:
        try:
            # Resolve to real path and normalize case
            real_path = path.resolve()
            
            # Use case-insensitive comparison for deduplication
            # (handles macOS/Windows case-insensitive filesystems)
            real_path_lower = str(real_path).lower()
        except Exception:
            # If resolution fails, use original path
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
    max_chars_per_file: int = 20000
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
        max_chars_per_file: Maximum characters per file (truncate if exceeded)
    
    Returns:
        List of BootstrapFile objects
    """
    bootstrap_files = [
        "AGENTS.md",
        "SOUL.md",
        "TOOLS.md",
        "IDENTITY.md",
        "USER.md",
        "HEARTBEAT.md",
        "BOOTSTRAP.md",
    ]
    
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
