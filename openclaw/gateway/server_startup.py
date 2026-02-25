"""Gateway sidecar services startup

Coordinates startup of all sidecar services.
Matches TypeScript openclaw/src/gateway/server-startup.ts
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from .server_browser import start_browser_control_server_if_enabled
from .server_canvas import start_canvas_host_server
from ..hooks.gmail_watcher import start_gmail_watcher
from ..hooks.loader import load_internal_hooks
from ..hooks.internal_hooks import clear_internal_hooks, create_internal_hook_event, trigger_internal_hook
from ..plugins.services import start_plugin_services

logger = logging.getLogger(__name__)


async def start_gateway_sidecars(params: dict) -> dict:
    """
    Start all Gateway sidecar services
    
    Sidecars:
    0. Internal Hooks
    1. Browser Control Server
    2. Gmail Watcher
    3. Plugin Services
    4. Canvas Host Server
    
    Args:
        params: Dict containing:
            - cfg: Gateway config
            - plugin_registry: Plugin registry
            - workspace_dir: Workspace directory
            - default_workspace_dir: Default workspace directory
            - log_browser: Browser logger
            - log_hooks: Hooks logger
            - deps: CLI dependencies (optional)
            
    Returns:
        Dict with sidecar info
    """
    cfg = params.get("cfg", {})
    plugin_registry = params.get("plugin_registry", {})
    workspace_dir = params.get("workspace_dir", Path.home())
    default_workspace_dir = params.get("default_workspace_dir") or str(workspace_dir)
    log_browser = params.get("log_browser", logger)
    log_hooks = params.get("log_hooks", logger)
    deps = params.get("deps")
    
    results = {
        "browser_control": None,
        "gmail_watcher": None,
        "plugin_services": None,
        "canvas_host": None,
        "hooks_loaded": 0,
    }
    
    # 0. Load internal hook handlers from configuration and directory discovery
    try:
        # Clear any previously registered hooks to ensure fresh loading
        clear_internal_hooks()
        loaded_count = await load_internal_hooks(cfg, default_workspace_dir)
        results["hooks_loaded"] = loaded_count
        if loaded_count > 0:
            log_hooks.info(f"loaded {loaded_count} internal hook handler{'s' if loaded_count > 1 else ''}")
    except Exception as e:
        log_hooks.error(f"failed to load hooks: {e}")
    
    # 1. Start Browser Control Server
    try:
        browser_control = await start_browser_control_server_if_enabled(cfg)
        results["browser_control"] = browser_control
        if browser_control:
            log_browser.info(f"Browser Control Server started on port {browser_control['port']}")
    except Exception as e:
        log_browser.error(f"Browser Control Server failed to start: {e}")
    
    # 2. Start Gmail Watcher
    try:
        gmail_result = await start_gmail_watcher(cfg)
        results["gmail_watcher"] = gmail_result
        if gmail_result.get("started"):
            log_hooks.info("Gmail watcher started")
        elif gmail_result.get("reason") not in ("hooks not enabled", "no gmail account configured"):
            log_hooks.warn(f"Gmail watcher not started: {gmail_result.get('reason')}")
    except Exception as e:
        log_hooks.error(f"Gmail watcher failed to start: {e}")
    
    # 3. Start Plugin Services
    if plugin_registry:
        try:
            plugin_services = await start_plugin_services(plugin_registry, workspace_dir)
            results["plugin_services"] = plugin_services
            logger.info("Plugin services started")
        except Exception as e:
            logger.error(f"Plugin services failed to start: {e}")
    
    # 4. Start Canvas Host Server
    try:
        canvas_host = await start_canvas_host_server(cfg)
        results["canvas_host"] = canvas_host
        if canvas_host:
            logger.info(f"Canvas Host Server started on port {canvas_host['port']}")
    except Exception as e:
        logger.error(f"Canvas Host Server failed to start: {e}")
    
    # 5. Trigger gateway:startup hook event
    if cfg.get("hooks", {}).get("internal", {}).get("enabled"):
        # Small delay to let services fully initialize
        async def trigger_startup_hook():
            await asyncio.sleep(0.25)
            hook_event = create_internal_hook_event(
                "gateway",
                "startup",
                "gateway:startup",
                {
                    "cfg": cfg,
                    "deps": deps,
                    "workspaceDir": default_workspace_dir,
                    "workspace_dir": default_workspace_dir,
                }
            )
            await trigger_internal_hook(hook_event)
        
        # Create task to trigger hook in background
        asyncio.create_task(trigger_startup_hook())
    
    return results
