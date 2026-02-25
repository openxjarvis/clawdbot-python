"""Bootstrap extra files hook handler.

Inject additional workspace bootstrap files via glob/path patterns.

Aligned with TypeScript openclaw/src/hooks/bundled/bootstrap-extra-files/handler.ts
"""

from __future__ import annotations

import logging
from typing import Any

from openclaw.hooks.internal_hooks import is_agent_bootstrap_event

logger = logging.getLogger(__name__)

HOOK_KEY = "bootstrap-extra-files"


def normalize_string_array(value: Any) -> list[str]:
    """Normalize value to list of strings.
    
    Args:
        value: Value to normalize
    
    Returns:
        List of non-empty strings
    """
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if v and str(v).strip()]


def resolve_extra_bootstrap_patterns(hook_config: dict[str, Any]) -> list[str]:
    """Resolve extra bootstrap file patterns from hook config.
    
    Args:
        hook_config: Hook configuration
    
    Returns:
        List of patterns
    """
    # Try paths first
    from_paths = normalize_string_array(hook_config.get("paths"))
    if from_paths:
        return from_paths
    
    # Try patterns
    from_patterns = normalize_string_array(hook_config.get("patterns"))
    if from_patterns:
        return from_patterns
    
    # Try files
    return normalize_string_array(hook_config.get("files"))


def resolve_hook_config_simple(cfg: dict[str, Any] | None, hook_name: str) -> dict[str, Any] | None:
    """Simple hook config resolver (placeholder until config.py is implemented).
    
    Args:
        cfg: OpenClaw configuration
        hook_name: Name of the hook
    
    Returns:
        Hook-specific configuration or None
    """
    if not cfg:
        return None
    
    hooks_config = cfg.get("hooks", {})
    internal_config = hooks_config.get("internal", {})
    entries = internal_config.get("entries", {})
    return entries.get(hook_name)


async def bootstrap_extra_files_hook(event: Any) -> None:
    """Load extra bootstrap files during agent:bootstrap.
    
    Args:
        event: The hook event
    """
    if not is_agent_bootstrap_event(event):
        return
    
    context = event.context
    hook_config = resolve_hook_config_simple(context.get("cfg"), HOOK_KEY)
    
    if not hook_config or hook_config.get("enabled") is False:
        return
    
    patterns = resolve_extra_bootstrap_patterns(hook_config)
    if not patterns:
        return
    
    try:
        # Import bootstrap file loading functions
        from openclaw.agents.workspace import load_extra_bootstrap_files, filter_bootstrap_files_for_session
        
        workspace_dir = context.get("workspace_dir") or context.get("workspaceDir")
        if not workspace_dir:
            logger.warning("bootstrap-extra-files: no workspace_dir in context")
            return
        
        extras = await load_extra_bootstrap_files(workspace_dir, patterns)
        if not extras:
            return
        
        # Merge with existing bootstrap files
        bootstrap_files = context.get("bootstrap_files") or context.get("bootstrapFiles") or []
        merged_files = [*bootstrap_files, *extras]
        
        # Filter for session
        session_key = context.get("session_key") or context.get("sessionKey")
        filtered_files = filter_bootstrap_files_for_session(merged_files, session_key)
        
        # Update context
        if "bootstrap_files" in context:
            context["bootstrap_files"] = filtered_files
        else:
            context["bootstrapFiles"] = filtered_files
    except ImportError as err:
        logger.debug(f"bootstrap-extra-files: bootstrap functions not available: {err}")
    except Exception as err:
        logger.warning(f"[bootstrap-extra-files] failed: {err}")


# Default export (matches TS pattern)
default = bootstrap_extra_files_hook
