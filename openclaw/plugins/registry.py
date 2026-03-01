"""Plugin registry module.

Re-exports PluginRegistry and create_empty_plugin_registry from types.py,
and provides backward-compat aliases for existing code that imports from this module.

Matches TypeScript src/plugins/registry.ts structure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .types import (
    PluginRegistry,
    PluginRecord,
    PluginDiagnostic,
    PluginToolRegistration,
    PluginHookRegistration,
    TypedPluginHookRegistration,
    PluginChannelRegistration,
    PluginProviderRegistration,
    PluginHttpRegistration,
    PluginHttpRouteRegistration,
    PluginCliRegistration,
    PluginServiceRegistration,
    PluginCommandRegistration,
    PluginGatewayMethodRegistration,
    create_empty_plugin_registry,
)

# =============================================================================
# Backward-compat stubs for imports that expect the old registry module interface
# =============================================================================

# PluginRegistryData: the data portion that typed_hooks / tools / etc. live in
# For new code use PluginRegistry directly. This alias helps old imports compile.
PluginRegistryData = PluginRegistry


@dataclass
class PluginRegistryApi:
    """Accessor API over a PluginRegistry. Used by legacy code."""
    _data: PluginRegistry = field(default_factory=create_empty_plugin_registry)

    @property
    def plugins(self) -> list:
        return self._data.plugins

    @property
    def tools(self) -> list:
        return self._data.tools

    @property
    def typed_hooks(self) -> list:
        return self._data.typed_hooks

    @property
    def channels(self) -> list:
        return self._data.channels

    @property
    def providers(self) -> list:
        return self._data.providers

    @property
    def services(self) -> list:
        return self._data.services

    @property
    def commands(self) -> list:
        return self._data.commands

    @property
    def hooks(self) -> list:
        return self._data.hooks


def create_plugin_registry(plugin_logger=None) -> "ConcretePluginApi":
    """Create a new empty plugin registry API.

    Args:
        plugin_logger: Optional logger; accepted for API compatibility but unused
                       (logging uses the module logger internally).
    """
    return ConcretePluginApi(create_empty_plugin_registry())


def clear_plugin_commands() -> None:
    """Clear global plugin command registrations (used in tests)."""
    pass  # Commands live on the registry instance, not globally


class ConcretePluginApi:
    """Registry API for a single plugin instance.

    Returned by create_plugin_registry() — provides register_tool(),
    register_provider(), etc. methods that write into an underlying PluginRegistry.
    """

    def __init__(self, registry: PluginRegistry, plugin_id: str = "") -> None:
        self.id = plugin_id
        self._registry = registry

    @property
    def registry(self) -> PluginRegistry:
        return self._registry

    def create_api(self, record: "PluginRecord", config: Any = None) -> "ConcretePluginApi":
        """Return a plugin-scoped API sub-handle."""
        return ConcretePluginApi(self._registry, plugin_id=record.id)

    def register_tool(self, record: "PluginRecord", factory: Callable, names: list[str] | None = None) -> None:
        reg = PluginToolRegistration(plugin_id=record.id, factory=factory, names=names or [], source=record.source)
        self._registry.tools.append(reg)

    def register_provider(self, record: "PluginRecord", provider: Any) -> None:
        from .types import PluginProviderRegistration, PluginDiagnostic
        provider_id = getattr(provider, "id", str(id(provider)))
        # Duplicate check — add diagnostic instead of raising
        if any(getattr(r, "provider", None) is not None and getattr(r.provider, "id", None) == provider_id
               for r in self._registry.providers):
            self._registry.diagnostics.append(
                PluginDiagnostic(plugin_id=record.id, level="error",
                                 message=f"Provider '{provider_id}' already registered",
                                 source=record.source)
            )
            return
        reg = PluginProviderRegistration(plugin_id=record.id, provider=provider, source=record.source)
        self._registry.providers.append(reg)
        record.provider_ids.append(provider_id)

    def register_http_handler(self, record: "PluginRecord", handler: Callable) -> None:
        reg = PluginHttpRegistration(plugin_id=record.id, handler=handler, source=record.source)
        self._registry.http_handlers.append(reg)
        record.http_handlers += 1

    def register_http_route(self, record: "PluginRecord", path: str, handler: Callable) -> None:
        from .types import PluginDiagnostic
        if any(getattr(r, "path", None) == path for r in self._registry.http_routes):
            self._registry.diagnostics.append(
                PluginDiagnostic(plugin_id=record.id, level="error",
                                 message=f"HTTP route '{path}' already registered",
                                 source=record.source)
            )
            return
        reg = PluginHttpRouteRegistration(plugin_id=record.id, path=path, handler=handler, source=record.source)
        self._registry.http_routes.append(reg)

    def register_command(self, record: "PluginRecord", cmd: Any) -> None:
        reg = PluginCommandRegistration(plugin_id=record.id, command=cmd, source=record.source)
        self._registry.commands.append(reg)
        cmd_name = getattr(cmd, "name", "")
        if cmd_name and cmd_name not in record.commands:
            record.commands.append(cmd_name)


__all__ = [
    "PluginRegistry",
    "PluginRegistryData",
    "PluginRegistryApi",
    "ConcretePluginApi",
    "PluginRecord",
    "PluginDiagnostic",
    "PluginToolRegistration",
    "PluginHookRegistration",
    "TypedPluginHookRegistration",
    "PluginChannelRegistration",
    "PluginProviderRegistration",
    "PluginHttpRegistration",
    "PluginHttpRouteRegistration",
    "PluginCliRegistration",
    "PluginServiceRegistration",
    "PluginCommandRegistration",
    "PluginGatewayMethodRegistration",
    "create_empty_plugin_registry",
    "create_plugin_registry",
    "clear_plugin_commands",
]
