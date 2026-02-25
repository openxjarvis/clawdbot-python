"""Boot checklist hook handler.

Runs BOOT.md every time the gateway starts.

Aligned with TypeScript openclaw/src/hooks/bundled/boot-md/handler.ts
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def run_boot_checklist(event: Any) -> None:
    """Run BOOT.md on gateway startup.
    
    Args:
        event: The hook event
    """
    if event.type != "gateway" or event.action != "startup":
        return
    
    context = event.context or {}
    cfg = context.get("cfg")
    workspace_dir = context.get("workspaceDir") or context.get("workspace_dir")
    
    if not cfg or not workspace_dir:
        return
    
    try:
        # Import run_boot_once from gateway module
        from openclaw.gateway.boot import run_boot_once
        
        # Create deps if not provided
        deps = context.get("deps")
        if not deps:
            try:
                from openclaw.cli.deps import create_default_deps
                deps = create_default_deps()
            except ImportError:
                logger.debug("Could not create default deps for boot-md hook")
                deps = None
        
        await run_boot_once(cfg=cfg, deps=deps, workspace_dir=workspace_dir)
    except ImportError as err:
        logger.debug(f"boot-md hook: run_boot_once not available: {err}")
    except Exception as err:
        logger.warning(f"boot-md hook failed: {err}")


# Default export (matches TS pattern)
default = run_boot_checklist
