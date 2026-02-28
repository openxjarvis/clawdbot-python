"""Plugin services

Manages plugin lifecycle and isolation.
Matches TypeScript openclaw/src/plugins/services.ts
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class PluginServicesHandle(Protocol):
    """Plugin services handle"""
    
    async def close(self): ...


class PluginServices:
    """Plugin services manager"""
    
    def __init__(self, plugin_registry: Any, workspace_dir: Path):
        """
        Initialize plugin services

        Args:
            plugin_registry: PluginRegistry dataclass or dict.
            workspace_dir: Workspace directory
        """
        self.plugin_registry = plugin_registry
        self.workspace_dir = workspace_dir
        self._processes: dict[str, asyncio.subprocess.Process] = {}

    def _iter_plugins(self):
        """Yield (plugin_id, plugin_info) pairs regardless of registry type."""
        if isinstance(self.plugin_registry, dict):
            yield from self.plugin_registry.items()
            return
        # PluginRegistry dataclass — iterate .plugins list
        plugins_list = getattr(self.plugin_registry, "plugins", None) or []
        for record in plugins_list:
            plugin_id = getattr(record, "id", None) or getattr(record, "plugin_id", str(record))
            yield plugin_id, record

    async def start(self):
        """Start plugin services"""
        logger.info("Starting plugin services")
        
        for plugin_id, plugin_info in self._iter_plugins():
            logger.info(f"Starting plugin: {plugin_id}")
            # TODO: Spawn plugin process in isolated environment
    
    async def close(self):
        """Close all plugin services"""
        logger.info("Stopping plugin services")
        
        for plugin_id, proc in self._processes.items():
            try:
                proc.terminate()
                await proc.wait()
            except Exception as e:
                logger.error(f"Error stopping plugin {plugin_id}: {e}")
        
        self._processes.clear()


async def start_plugin_services(
    plugin_registry: dict,
    workspace_dir: Path
) -> PluginServicesHandle:
    """
    Start plugin services
    
    Args:
        plugin_registry: Plugin registry
        workspace_dir: Workspace directory
        
    Returns:
        PluginServicesHandle
    """
    services = PluginServices(plugin_registry, workspace_dir)
    await services.start()
    return services
