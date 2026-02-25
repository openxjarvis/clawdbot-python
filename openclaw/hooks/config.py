"""Hook configuration and eligibility checking.

Aligned with TypeScript openclaw/src/hooks/config.ts
"""

from __future__ import annotations

import logging
import os
import platform
import shutil
from typing import Any

from .types import HookEntry

logger = logging.getLogger(__name__)


def resolve_hook_config(cfg: dict[str, Any] | None, hook_name: str) -> dict[str, Any] | None:
    """Resolve hook-specific configuration from OpenClaw config.
    
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


def should_include_hook(
    entry: HookEntry,
    config: dict[str, Any] | None = None,
    eligibility: dict[str, Any] | None = None
) -> bool:
    """Check if a hook should be included based on eligibility requirements.
    
    Args:
        entry: Hook entry to check
        config: OpenClaw configuration
        eligibility: Additional eligibility context
    
    Returns:
        True if hook is eligible
    """
    # If hook has 'always' flag, include it
    if entry.metadata and entry.metadata.always:
        return True
    
    # If explicitly disabled in config, exclude it
    hook_config = resolve_hook_config(config, entry.hook.name)
    if hook_config and hook_config.get("enabled") is False:
        return False
    
    # Check requirements
    if not entry.metadata or not entry.metadata.requires:
        return True
    
    requires = entry.metadata.requires
    
    # Check binary requirements
    bins = requires.get("bins", [])
    for bin_name in bins:
        if not shutil.which(bin_name):
            logger.debug(f"Hook '{entry.hook.name}' missing required binary: {bin_name}")
            return False
    
    # Check anyBins (at least one must be present)
    any_bins = requires.get("anyBins", [])
    if any_bins:
        if not any(shutil.which(bin_name) for bin_name in any_bins):
            logger.debug(f"Hook '{entry.hook.name}' missing any required binary: {any_bins}")
            return False
    
    # Check environment variables
    env_vars = requires.get("env", [])
    for env_var in env_vars:
        if not os.getenv(env_var):
            logger.debug(f"Hook '{entry.hook.name}' missing required env var: {env_var}")
            return False
    
    # Check config paths
    config_paths = requires.get("config", [])
    for path in config_paths:
        if not config:
            logger.debug(f"Hook '{entry.hook.name}' missing config for path: {path}")
            return False
        
        # Navigate config path (e.g., "workspace.dir" or "agents.0.name")
        parts = path.split(".")
        current = config
        for part in parts:
            # Check if part is array index (numeric)
            if part.isdigit():
                index = int(part)
                if not isinstance(current, list) or index >= len(current):
                    logger.debug(f"Hook '{entry.hook.name}' missing config path: {path}")
                    return False
                current = current[index]
            else:
                if not isinstance(current, dict) or part not in current:
                    logger.debug(f"Hook '{entry.hook.name}' missing config path: {path}")
                    return False
                current = current[part]
    
    # Check OS requirements
    os_reqs = requires.get("os")
    if os_reqs:
        current_os = platform.system().lower()
        # Map platform.system() output to expected values
        os_map = {
            "darwin": "darwin",
            "linux": "linux",
            "windows": "win32"
        }
        mapped_os = os_map.get(current_os, current_os)
        if mapped_os not in os_reqs:
            logger.debug(f"Hook '{entry.hook.name}' not compatible with OS: {current_os}")
            return False
    
    return True


__all__ = [
    "resolve_hook_config",
    "should_include_hook",
]
