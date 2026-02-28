"""Hook registry for managing and dispatching hooks.

Aligned with TypeScript hook registry pattern.
"""

from __future__ import annotations

from typing import Optional, Callable, Any, Awaitable
from collections import defaultdict
import asyncio

from .types import Hook, HookEntry, HookHandler


class HookRegistry:
    """Registry for hooks and event dispatch."""
    
    def __init__(self):
        """Initialize hook registry."""
        self._hooks: dict[str, HookEntry] = {}
        self._event_handlers: dict[str, list[HookHandler]] = defaultdict(list)
    
    def register_hook(
        self,
        events: list[str],
        handler: HookHandler,
        options: Optional[dict] = None
    ) -> None:
        """Register a hook handler for events.
        
        Args:
            events: List of event names
            handler: Async handler function
            options: Optional hook options
        """
        for event in events:
            self._event_handlers[event].append(handler)
    
    def register_hook_entry(self, entry: HookEntry) -> None:
        """Register a hook entry.
        
        Args:
            entry: HookEntry to register
        """
        self._hooks[entry.hook.name] = entry
        
        # Register handlers for events if metadata present
        if entry.metadata and entry.metadata.events:
            # In production, would load and register actual handler
            # For now, store the entry
            pass
    
    async def dispatch_event(
        self,
        event: str,
        context: Optional[dict[str, Any]] = None
    ) -> None:
        """Dispatch an event to all registered handlers.
        
        Args:
            event: Event name
            context: Optional event context
        """
        handlers = self._event_handlers.get(event, [])
        
        if not handlers:
            return
        
        # Execute all handlers
        tasks = []
        for handler in handlers:
            tasks.append(handler(context or {}))
        
        # Wait for all handlers to complete
        await asyncio.gather(*tasks, return_exceptions=True)
    
    def get_hook(self, name: str) -> Optional[HookEntry]:
        """Get hook entry by name.
        
        Args:
            name: Hook name
        
        Returns:
            HookEntry if found, None otherwise
        """
        return self._hooks.get(name)
    
    def list_hooks(self) -> list[HookEntry]:
        """List all registered hooks.
        
        Returns:
            List of all hook entries
        """
        return list(self._hooks.values())
    
    def list_events(self) -> list[str]:
        """List all registered events.
        
        Returns:
            List of event names
        """
        return list(self._event_handlers.keys())

    def register_plugin_hooks(
        self,
        plugin_id: str,
        hooks: list[tuple[str, HookHandler, Any]],
    ) -> None:
        """
        Register multiple hooks from a plugin in one call.

        Mirrors TS HookRegistry.registerPluginHooks().

        Args:
            plugin_id: Unique identifier for the plugin.
            hooks:     List of (event_name, handler, priority_or_options) tuples.
        """
        for event_name, handler, options in hooks:
            opts: dict | None = None
            if isinstance(options, dict):
                opts = options
            elif options is not None:
                opts = {"priority": options}
            self.register_hook([event_name], handler, opts)


# Global registry instance
_global_registry: Optional[HookRegistry] = None


def get_hook_registry() -> HookRegistry:
    """Get the global hook registry.
    
    Returns:
        Global HookRegistry instance
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = HookRegistry()
    return _global_registry
