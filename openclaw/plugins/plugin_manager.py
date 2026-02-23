"""Plugin system for extensibility"""

import importlib
import json
import logging
from pathlib import Path
import shutil
from datetime import datetime, UTC
from typing import Any

logger = logging.getLogger(__name__)


class Plugin:
    """Base class for plugins"""
    
    name: str = "unnamed"
    version: str = "0.0.0"
    description: str = ""
    
    async def initialize(self, config: dict[str, Any]) -> None:
        """Initialize plugin with configuration"""
        pass
    
    async def shutdown(self) -> None:
        """Shutdown plugin"""
        pass


class PluginManager:
    """
    Plugin manager for loading and managing plugins.
    
    Plugins can provide:
    - Custom tools
    - Custom channels
    - Custom skills
    - Custom hooks
    """
    
    def __init__(self, plugin_dirs: list[Path] | None = None):
        self.plugins: dict[str, Plugin] = {}
        self.plugin_dirs = plugin_dirs or [
            Path.home() / ".openclaw" / "plugins",
        ]
        for d in self.plugin_dirs:
            d.mkdir(parents=True, exist_ok=True)
        self._installs_path = self.plugin_dirs[0] / ".installs.json"
        self.install_records: dict[str, dict[str, Any]] = self._load_installs()

    def _load_installs(self) -> dict[str, dict[str, Any]]:
        if not self._installs_path.exists():
            return {}
        try:
            data = json.loads(self._installs_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_installs(self) -> None:
        try:
            self._installs_path.write_text(
                json.dumps(self.install_records, indent=2),
                encoding="utf-8",
            )
        except Exception:
            logger.debug("Failed to persist plugin install records", exc_info=True)

    def install_from_path(
        self,
        plugin_path: str,
        *,
        plugin_id: str | None = None,
        link: bool = False,
    ) -> dict[str, Any]:
        """Install plugin source from local path into plugin dir."""
        src = Path(plugin_path).expanduser().resolve()
        if not src.exists():
            raise ValueError(f"Plugin path not found: {src}")
        inferred = plugin_id or (src.stem if src.is_file() else src.name)
        dst_base = self.plugin_dirs[0]
        dst = dst_base / (f"{inferred}.py" if src.is_file() else inferred)
        if dst.exists() or dst.is_symlink():
            if dst.is_dir() and not dst.is_symlink():
                shutil.rmtree(dst)
            else:
                dst.unlink()
        if link:
            dst.symlink_to(src, target_is_directory=src.is_dir())
        else:
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
        source = "path"
        self.install_records[inferred] = {
            "source": source,
            "linked": bool(link),
            "sourcePath": str(src),
            "installPath": str(dst),
            "installedAt": datetime.now(UTC).isoformat(),
        }
        self._save_installs()
        return {"pluginId": inferred, "installPath": str(dst), "source": source}

    def remove_installed_files(self, plugin_name: str) -> bool:
        """Remove installed plugin files when tracked."""
        rec = self.install_records.get(plugin_name) or {}
        install_path = rec.get("installPath")
        if not install_path:
            return False
        p = Path(install_path)
        if not p.exists() and not p.is_symlink():
            return False
        if p.is_dir() and not p.is_symlink():
            shutil.rmtree(p)
        else:
            p.unlink()
        return True
    
    def discover_plugins(self) -> list[str]:
        """
        Discover available plugins in plugin directories.
        
        Returns:
            List of plugin names
        """
        discovered = []
        
        for plugin_dir in self.plugin_dirs:
            if not plugin_dir.exists():
                continue
            
            for item in plugin_dir.iterdir():
                if item.is_dir() and (item / "__init__.py").exists():
                    discovered.append(item.name)
                elif item.is_file() and item.suffix == ".py" and item.stem != "__init__":
                    discovered.append(item.stem)
        
        return discovered
    
    async def load_plugin(self, plugin_name: str, config: dict[str, Any] | None = None) -> Plugin:
        """
        Load a plugin by name.
        
        Args:
            plugin_name: Name of plugin to load
            config: Configuration dict for plugin
        
        Returns:
            Loaded plugin instance
        """
        if plugin_name in self.plugins:
            logger.warning(f"Plugin {plugin_name} already loaded")
            return self.plugins[plugin_name]
        
        # Try to import plugin
        for plugin_dir in self.plugin_dirs:
            plugin_path = plugin_dir / plugin_name
            
            if plugin_path.is_dir():
                # Package plugin
                try:
                    spec = importlib.util.spec_from_file_location(
                        f"openclaw_plugin_{plugin_name}",
                        plugin_path / "__init__.py"
                    )
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    # Look for Plugin class
                    if hasattr(module, "Plugin"):
                        plugin_class = module.Plugin
                        plugin = plugin_class()
                        
                        # Initialize
                        await plugin.initialize(config or {})
                        
                        self.plugins[plugin_name] = plugin
                        logger.info(f"Loaded plugin: {plugin_name} v{plugin.version}")
                        
                        return plugin
                    else:
                        logger.error(f"Plugin {plugin_name} has no Plugin class")
                
                except Exception as e:
                    logger.error(f"Failed to load plugin {plugin_name}: {e}")
            
            elif (plugin_dir / f"{plugin_name}.py").exists():
                # Single file plugin
                try:
                    spec = importlib.util.spec_from_file_location(
                        f"openclaw_plugin_{plugin_name}",
                        plugin_dir / f"{plugin_name}.py"
                    )
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    if hasattr(module, "Plugin"):
                        plugin_class = module.Plugin
                        plugin = plugin_class()
                        
                        await plugin.initialize(config or {})
                        
                        self.plugins[plugin_name] = plugin
                        logger.info(f"Loaded plugin: {plugin_name} v{plugin.version}")
                        
                        return plugin
                
                except Exception as e:
                    logger.error(f"Failed to load plugin {plugin_name}: {e}")
        
        raise ValueError(f"Plugin not found: {plugin_name}")
    
    async def unload_plugin(self, plugin_name: str) -> None:
        """Unload a plugin"""
        if plugin_name not in self.plugins:
            logger.warning(f"Plugin {plugin_name} not loaded")
            return
        
        plugin = self.plugins[plugin_name]
        await plugin.shutdown()
        
        del self.plugins[plugin_name]
        logger.info(f"Unloaded plugin: {plugin_name}")
    
    async def shutdown_all(self) -> None:
        """Shutdown all plugins"""
        for plugin_name in list(self.plugins.keys()):
            await self.unload_plugin(plugin_name)
    
    def list_loaded(self) -> list[str]:
        """List loaded plugin names"""
        return list(self.plugins.keys())
