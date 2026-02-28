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


def create_plugin_registry() -> PluginRegistry:
    """Create a new empty PluginRegistry. Alias for create_empty_plugin_registry."""
    return create_empty_plugin_registry()


class ConcretePluginApi:
    """Concrete implementation stub for backward-compat.

    New code should use PluginApi from api.py instead.
    """

    def __init__(self, plugin_id: str, registry: PluginRegistry) -> None:
        self.id = plugin_id
        self._registry = registry


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
]
