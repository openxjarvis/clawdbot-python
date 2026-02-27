"""Hook loading from directories.

Loads HOOK.md files and their handlers.
Aligned with TypeScript src/hooks/loader.ts
"""

from __future__ import annotations

import importlib.util
import logging
import sys
import time
from pathlib import Path
from typing import Optional, Any
import yaml

from .types import Hook, HookEntry, HookSource, OpenClawHookMetadata, HookInvocationPolicy
from .internal_hooks import register_internal_hook, InternalHookHandler

logger = logging.getLogger(__name__)


def parse_hook_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter from HOOK.md.
    
    Args:
        content: Full file content
    
    Returns:
        Tuple of (frontmatter dict, body content)
    """
    if not content.startswith("---"):
        return {}, content
    
    # Find end of frontmatter
    end_index = content.find("---", 3)
    if end_index == -1:
        return {}, content
    
    # Extract frontmatter and body
    frontmatter_text = content[3:end_index].strip()
    body = content[end_index + 3:].strip()
    
    try:
        frontmatter = yaml.safe_load(frontmatter_text) or {}
    except yaml.YAMLError:
        frontmatter = {}
    
    return frontmatter, body


def extract_hook_metadata(frontmatter: dict) -> Optional[OpenClawHookMetadata]:
    """Extract OpenClaw hook metadata from frontmatter.
    
    Args:
        frontmatter: Parsed frontmatter dictionary
    
    Returns:
        OpenClawHookMetadata if metadata found, None otherwise
        
    Supports three formats:
    1. Nested: metadata.openclaw.events (bundled hooks)
    2. openclaw: events at frontmatter.openclaw (some hooks)
    3. Top-level: events/requires/emoji/homepage at root (simple hooks)
    """
    # Try nested openclaw metadata first (metadata.openclaw.*)
    openclaw_data = frontmatter.get("metadata", {}).get("openclaw") if "metadata" in frontmatter else frontmatter.get("openclaw")
    
    if openclaw_data and isinstance(openclaw_data, dict):
        events = openclaw_data.get("events", [])
        if not isinstance(events, list):
            events = [events] if events else []
        
        return OpenClawHookMetadata(
            events=events,
            always=openclaw_data.get("always", False),
            hook_key=openclaw_data.get("hookKey"),
            emoji=openclaw_data.get("emoji"),
            homepage=openclaw_data.get("homepage"),
            export=openclaw_data.get("export", "default"),
            os=openclaw_data.get("os"),
            requires=openclaw_data.get("requires"),
            install=openclaw_data.get("install")
        )
    
    # Fallback: try top-level fields (simple format)
    events = frontmatter.get("events", [])
    if events:
        if not isinstance(events, list):
            events = [events]
        return OpenClawHookMetadata(
            events=events,
            always=frontmatter.get("always", False),
            hook_key=frontmatter.get("hookKey"),
            emoji=frontmatter.get("emoji"),
            homepage=frontmatter.get("homepage"),
            export=frontmatter.get("export", "default"),
            os=frontmatter.get("os"),
            requires=frontmatter.get("requires"),
            install=frontmatter.get("install")
        )
    
    return None


def load_hook_from_dir(hook_dir: Path, source: HookSource) -> Optional[HookEntry]:
    """Load a hook from a directory containing HOOK.md.
    
    Args:
        hook_dir: Directory containing HOOK.md
        source: Hook source
    
    Returns:
        HookEntry if valid hook found, None otherwise
    """
    hook_md_path = hook_dir / "HOOK.md"
    if not hook_md_path.exists():
        return None
    
    try:
        content = hook_md_path.read_text(encoding="utf-8")
    except Exception:
        return None
    
    # Parse frontmatter
    frontmatter, body = parse_hook_frontmatter(content)
    
    # Extract name and description
    name = frontmatter.get("name", hook_dir.name)
    description = frontmatter.get("description", "")
    
    # If no description in frontmatter, try to extract from body
    if not description and body:
        lines = body.split("\n")
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#"):
                description = line
                break
    
    # Find handler file
    handler_path = ""
    for handler_file in ["handler.py", "handler.js", "handler.ts"]:
        handler_file_path = hook_dir / handler_file
        if handler_file_path.exists():
            handler_path = str(handler_file_path)
            break
    
    # Skip hooks without a handler file
    if not handler_path:
        return None
    
    # Create hook
    hook = Hook(
        name=name,
        description=description,
        source=source,
        file_path=str(hook_md_path),
        base_dir=str(hook_dir),
        handler_path=handler_path
    )
    
    # Extract metadata
    metadata = extract_hook_metadata(frontmatter)
    
    # Create entry
    entry = HookEntry(
        hook=hook,
        frontmatter=frontmatter,
        metadata=metadata,
        invocation=HookInvocationPolicy(enabled=True)
    )
    
    return entry


def load_hooks_from_dir(
    directory: Path,
    source: HookSource = "openclaw-workspace"
) -> list[HookEntry]:
    """Load all hooks from a directory.
    
    Scans for subdirectories containing HOOK.md files.
    
    Args:
        directory: Directory to scan
        source: Hook source
    
    Returns:
        List of HookEntry objects
    """
    if not directory.exists() or not directory.is_dir():
        return []
    
    hooks: list[HookEntry] = []
    
    # Scan subdirectories
    for subdir in directory.iterdir():
        if not subdir.is_dir():
            continue
        
        # Try to load hook from this directory
        entry = load_hook_from_dir(subdir, source)
        if entry:
            hooks.append(entry)
    
    return hooks


def format_hooks_for_display(hooks: list[HookEntry]) -> str:
    """Format hooks for human-readable display.
    
    Args:
        hooks: List of hook entries
    
    Returns:
        Formatted string
    """
    if not hooks:
        return "No hooks available."
    
    lines = []
    for entry in hooks:
        hook = entry.hook
        emoji = entry.metadata.emoji if entry.metadata else ""
        events = entry.metadata.events if entry.metadata else []
        events_str = ", ".join(events) if events else "no events"
        
        prefix = f"{emoji} " if emoji else ""
        lines.append(f"{prefix}**{hook.name}**")
        lines.append(f"  {hook.description}")
        lines.append(f"  Events: {events_str}")
        lines.append("")
    
    return "\n".join(lines)


def _import_handler_module(handler_path: str) -> Any:
    """Dynamically import a handler module.
    
    Args:
        handler_path: Path to handler module
    
    Returns:
        Imported module
    
    Raises:
        ImportError: If module cannot be imported
    """
    handler_path_obj = Path(handler_path)
    
    # Create a unique module name with timestamp for cache-busting
    module_name = f"openclaw_hook_{handler_path_obj.stem}_{int(time.time() * 1000)}"
    
    # Load the module
    spec = importlib.util.spec_from_file_location(module_name, handler_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load spec for {handler_path}")
    
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    
    return module


async def load_internal_hooks(
    cfg: dict[str, Any],
    workspace_dir: str,
    opts: dict[str, Any] | None = None,
) -> int:
    """Load and register all hook handlers.
    
    Loads hooks from both:
    1. Directory-based discovery (bundled, managed, workspace)
    2. Legacy config handlers (backwards compatibility)
    
    Args:
        cfg: OpenClaw configuration
        workspace_dir: Workspace directory for hook discovery
        opts: Optional options (managedHooksDir, bundledHooksDir)
    
    Returns:
        Number of handlers successfully loaded
    
    Example:
        >>> config = await load_config()
        >>> workspace_dir = resolve_agent_workspace_dir(config, agent_id)
        >>> count = await load_internal_hooks(config, workspace_dir)
        >>> print(f"Loaded {count} hook handlers")
    """
    opts = opts or {}
    
    # Ensure cfg is not None
    if cfg is None:
        cfg = {}
    
    # Check if hooks are enabled
    hooks_config = cfg.get("hooks", {})
    internal_config = hooks_config.get("internal", {})
    if not internal_config.get("enabled"):
        return 0
    
    loaded_count = 0
    
    # 1. Load hooks from directories (new system)
    try:
        from .workspace import load_workspace_hook_entries
        
        hook_entries = load_workspace_hook_entries(
            workspace_dir,
            config=cfg,
            managed_hooks_dir=opts.get("managed_hooks_dir") or opts.get("managedHooksDir"),
            bundled_hooks_dir=opts.get("bundled_hooks_dir") or opts.get("bundledHooksDir"),
        )
        
        # Ensure hook_entries is not None (Bug fix for NoneType iteration)
        if hook_entries is None:
            hook_entries = []
        
        # Filter by eligibility (we'll implement this in config.py)
        # For now, accept all hooks
        try:
            from .config import should_include_hook, resolve_hook_config
            eligible = [entry for entry in hook_entries if should_include_hook(entry=entry, config=cfg)]
        except ImportError:
            # config.py not yet implemented, accept all
            eligible = hook_entries
            internal_config = cfg.get("hooks", {}).get("internal", {}) if cfg else {}
            resolve_hook_config = lambda cfg, name: internal_config.get("entries", {}).get(name)
        
        for entry in eligible:
            hook_config = resolve_hook_config(cfg, entry.hook.name)
            
            # Skip if explicitly disabled in config
            if hook_config and hook_config.get("enabled") is False:
                continue
            
            try:
                # Import handler module
                if not entry.hook.handler_path:
                    logger.warning(f"Hook '{entry.hook.name}' has no handler path")
                    continue
                
                mod = _import_handler_module(entry.hook.handler_path)
                
                # Get handler function (default or named export)
                export_name = entry.metadata.export if entry.metadata else "default"
                handler = getattr(mod, export_name, None)
                
                if handler is None:
                    logger.error(f"Handler '{export_name}' from {entry.hook.name} not found")
                    continue
                
                if not callable(handler):
                    logger.error(f"Handler '{export_name}' from {entry.hook.name} is not callable")
                    continue
                
                # Register for all events listed in metadata
                events = entry.metadata.events if entry.metadata else []
                if not events:
                    logger.warning(f"Hook '{entry.hook.name}' has no events defined in metadata")
                    continue
                
                for event in events:
                    register_internal_hook(event, handler)
                
                export_suffix = f" (export: {export_name})" if export_name != "default" else ""
                logger.info(
                    f"Registered hook: {entry.hook.name} -> {', '.join(events)}{export_suffix}"
                )
                loaded_count += 1
            except Exception as err:
                logger.error(
                    f"Failed to load hook {entry.hook.name}: {err}",
                    exc_info=True
                )
    except Exception as err:
        logger.error(
            f"Failed to load directory-based hooks: {err}",
            exc_info=True
        )
    
    # 2. Load legacy config handlers (backwards compatibility)
    handlers_config = internal_config.get("handlers") or []
    for handler_config in handlers_config:
        try:
            # Legacy handler paths: keep them workspace-relative
            raw_module = handler_config.get("module", "").strip()
            if not raw_module:
                logger.error("Handler module path is empty")
                continue
            
            # Convert to Path for validation
            workspace_path = Path(workspace_dir).resolve()
            if Path(raw_module).is_absolute():
                logger.error(
                    f"Handler module path must be workspace-relative (got absolute path): {raw_module}"
                )
                continue
            
            module_path = (workspace_path / raw_module).resolve()
            
            # Check that module_path is within workspace_dir
            try:
                module_path.relative_to(workspace_path)
            except ValueError:
                logger.error(f"Handler module path must stay within workspaceDir: {raw_module}")
                continue
            
            # Import the module
            mod = _import_handler_module(str(module_path))
            
            # Get the handler function
            export_name = handler_config.get("export", "default")
            handler = getattr(mod, export_name, None)
            
            if handler is None:
                logger.error(f"Handler '{export_name}' from {module_path} not found")
                continue
            
            if not callable(handler):
                logger.error(f"Handler '{export_name}' from {module_path} is not callable")
                continue
            
            event = handler_config.get("event")
            if not event:
                logger.error(f"Handler from {module_path} has no event defined")
                continue
            
            register_internal_hook(event, handler)
            
            export_suffix = f"#{export_name}" if export_name != "default" else ""
            logger.info(
                f"Registered hook (legacy): {event} -> {module_path}{export_suffix}"
            )
            loaded_count += 1
        except Exception as err:
            module_ref = handler_config.get("module", "unknown")
            logger.error(
                f"Failed to load hook handler from {module_ref}: {err}",
                exc_info=True
            )
    
    return loaded_count


__all__ = [
    "parse_hook_frontmatter",
    "extract_hook_metadata",
    "load_hook_from_dir",
    "load_hooks_from_dir",
    "format_hooks_for_display",
    "load_internal_hooks",
]
