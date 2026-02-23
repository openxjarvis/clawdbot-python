"""Plugin registry — mirrors src/plugins/registry.ts"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Callable

from .types import (
    OpenClawPluginChannelRegistration,
    OpenClawPluginCliRegistrar,
    OpenClawPluginCommandDefinition,
    OpenClawPluginHookOptions,
    OpenClawPluginHttpHandler,
    OpenClawPluginHttpRouteHandler,
    OpenClawPluginService,
    OpenClawPluginToolFactory,
    OpenClawPluginToolOptions,
    PluginConfigUiHint,
    PluginDiagnostic,
    PluginHookName,
    PluginHookRegistration,
    PluginKind,
    PluginLogger,
    PluginOrigin,
    ProviderPlugin,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Registration data classes
# ---------------------------------------------------------------------------

@dataclass
class PluginToolRegistration:
    plugin_id: str
    factory: OpenClawPluginToolFactory
    names: list[str]
    optional: bool
    source: str


@dataclass
class PluginCliRegistration:
    plugin_id: str
    register: OpenClawPluginCliRegistrar
    commands: list[str]
    source: str


@dataclass
class PluginHttpRegistration:
    plugin_id: str
    handler: OpenClawPluginHttpHandler
    source: str


@dataclass
class PluginHttpRouteRegistration:
    path: str
    handler: OpenClawPluginHttpRouteHandler
    plugin_id: str | None = None
    source: str | None = None


@dataclass
class PluginChannelRegistration:
    plugin_id: str
    plugin: Any  # ChannelPlugin
    source: str
    dock: Any | None = None  # ChannelDock


@dataclass
class PluginProviderRegistration:
    plugin_id: str
    provider: ProviderPlugin
    source: str


@dataclass
class PluginServiceRegistration:
    plugin_id: str
    service: OpenClawPluginService
    source: str


@dataclass
class PluginCommandRegistration:
    plugin_id: str
    command: OpenClawPluginCommandDefinition
    source: str


@dataclass
class PluginRecord:
    id: str
    name: str
    source: str
    origin: PluginOrigin
    enabled: bool
    status: str  # "loaded" | "disabled" | "error"
    version: str | None = None
    description: str | None = None
    kind: PluginKind | None = None
    workspace_dir: str | None = None
    error: str | None = None
    tool_names: list[str] = field(default_factory=list)
    hook_names: list[str] = field(default_factory=list)
    channel_ids: list[str] = field(default_factory=list)
    provider_ids: list[str] = field(default_factory=list)
    gateway_methods: list[str] = field(default_factory=list)
    cli_commands: list[str] = field(default_factory=list)
    services: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    http_handlers: int = 0
    hook_count: int = 0
    config_schema: bool = False
    config_ui_hints: dict[str, PluginConfigUiHint] | None = None
    config_json_schema: dict | None = None


# ---------------------------------------------------------------------------
# Registry data structure
# ---------------------------------------------------------------------------

@dataclass
class PluginRegistryData:
    plugins: list[PluginRecord] = field(default_factory=list)
    tools: list[PluginToolRegistration] = field(default_factory=list)
    hooks: list[Any] = field(default_factory=list)
    typed_hooks: list[PluginHookRegistration] = field(default_factory=list)
    channels: list[PluginChannelRegistration] = field(default_factory=list)
    providers: list[PluginProviderRegistration] = field(default_factory=list)
    gateway_handlers: dict[str, Any] = field(default_factory=dict)
    http_handlers: list[PluginHttpRegistration] = field(default_factory=list)
    http_routes: list[PluginHttpRouteRegistration] = field(default_factory=list)
    cli_registrars: list[PluginCliRegistration] = field(default_factory=list)
    services: list[PluginServiceRegistration] = field(default_factory=list)
    commands: list[PluginCommandRegistration] = field(default_factory=list)
    diagnostics: list[PluginDiagnostic] = field(default_factory=list)


def create_empty_plugin_registry() -> PluginRegistryData:
    return PluginRegistryData()


# ---------------------------------------------------------------------------
# Plugin commands registry (global, mirrors plugins/commands.ts)
# ---------------------------------------------------------------------------

_plugin_commands: dict[str, Any] = {}


def register_plugin_command(plugin_id: str, command: OpenClawPluginCommandDefinition) -> dict:
    """Register a command globally. Returns {ok, error}."""
    name = command.name.strip().lstrip("/")
    if not name:
        return {"ok": False, "error": "command name is empty"}
    key = f"/{name}"
    if key in _plugin_commands:
        existing = _plugin_commands[key]
        return {"ok": False, "error": f"command {key} already registered by {existing.get('plugin_id')}"}
    _plugin_commands[key] = {"plugin_id": plugin_id, "command": command}
    return {"ok": True}


def get_plugin_commands() -> dict[str, Any]:
    return dict(_plugin_commands)


def clear_plugin_commands() -> None:
    _plugin_commands.clear()


# ---------------------------------------------------------------------------
# HTTP path normalization (mirrors plugins/http-path.ts)
# ---------------------------------------------------------------------------

def normalize_plugin_http_path(path_str: str) -> str | None:
    stripped = path_str.strip()
    if not stripped:
        return None
    if not stripped.startswith("/"):
        stripped = f"/{stripped}"
    return stripped


# ---------------------------------------------------------------------------
# Registry factory
# ---------------------------------------------------------------------------

def create_plugin_registry(
    plugin_logger: PluginLogger,
    runtime: Any = None,
    core_gateway_handlers: dict[str, Any] | None = None,
):
    """Create a plugin registry. Mirrors createPluginRegistry() from registry.ts."""
    registry = create_empty_plugin_registry()
    core_gateway_methods = set(core_gateway_handlers.keys()) if core_gateway_handlers else set()

    def _push_diagnostic(diag: PluginDiagnostic) -> None:
        registry.diagnostics.append(diag)

    def _normalize_logger(lg: PluginLogger) -> PluginLogger:
        return lg

    # --- Tool ---

    def register_tool(
        record: PluginRecord,
        tool: Any,
        opts: OpenClawPluginToolOptions | None = None,
    ) -> None:
        from .types import OpenClawPluginToolContext
        names: list[str] = []
        if opts and opts.names:
            names.extend(opts.names)
        elif opts and opts.name:
            names.append(opts.name)
        optional = opts.optional if opts else False

        if callable(tool) and not hasattr(tool, "name"):
            factory = tool
        elif callable(tool):
            factory = tool
            # if it looks like a tool object with a name attr, use it
            if hasattr(tool, "name") and isinstance(getattr(tool, "name"), str):
                names.append(tool.name)
        else:
            actual_name = getattr(tool, "name", None)
            if actual_name:
                names.append(actual_name)
            factory = lambda ctx: tool  # noqa: E731

        normalized = [n.strip() for n in names if n.strip()]
        if normalized:
            record.tool_names.extend(normalized)
        registry.tools.append(PluginToolRegistration(
            plugin_id=record.id,
            factory=factory,
            names=normalized,
            optional=optional,
            source=record.source,
        ))

    # --- Hook ---

    def register_hook(
        record: PluginRecord,
        events: str | list[str],
        handler: Any,
        opts: OpenClawPluginHookOptions | None = None,
        config: Any = None,
    ) -> None:
        event_list = [events] if isinstance(events, str) else events
        normalized_events = [e.strip() for e in event_list if e.strip()]
        name = (opts.name.strip() if opts and opts.name else None) or (
            opts.entry.hook.name if opts and opts.entry and hasattr(opts.entry, "hook") else None
        )
        if not name:
            _push_diagnostic(PluginDiagnostic(
                level="warn",
                plugin_id=record.id,
                source=record.source,
                message="hook registration missing name",
            ))
            return
        record.hook_names.append(name)
        registry.hooks.append({
            "plugin_id": record.id,
            "events": normalized_events,
            "handler": handler,
            "name": name,
            "source": record.source,
        })

    # --- Typed hook (for .on()) ---

    def register_typed_hook(
        record: PluginRecord,
        hook_name: str,
        handler: Any,
        opts: dict | None = None,
    ) -> None:
        record.hook_count += 1
        registry.typed_hooks.append(PluginHookRegistration(
            plugin_id=record.id,
            hook_name=hook_name,
            handler=handler,
            source=record.source,
            priority=opts.get("priority", 0) if opts else 0,
        ))

    # --- Gateway ---

    def register_gateway_method(record: PluginRecord, method: str, handler: Any) -> None:
        trimmed = method.strip()
        if not trimmed:
            return
        if trimmed in core_gateway_methods or trimmed in registry.gateway_handlers:
            _push_diagnostic(PluginDiagnostic(
                level="error",
                plugin_id=record.id,
                source=record.source,
                message=f"gateway method already registered: {trimmed}",
            ))
            return
        registry.gateway_handlers[trimmed] = handler
        record.gateway_methods.append(trimmed)

    # --- HTTP ---

    def register_http_handler(record: PluginRecord, handler: OpenClawPluginHttpHandler) -> None:
        record.http_handlers += 1
        registry.http_handlers.append(PluginHttpRegistration(
            plugin_id=record.id,
            handler=handler,
            source=record.source,
        ))

    def register_http_route(record: PluginRecord, path_str: str, handler: OpenClawPluginHttpRouteHandler) -> None:
        normalized = normalize_plugin_http_path(path_str)
        if not normalized:
            _push_diagnostic(PluginDiagnostic(
                level="warn",
                plugin_id=record.id,
                source=record.source,
                message="http route registration missing path",
            ))
            return
        if any(r.path == normalized for r in registry.http_routes):
            _push_diagnostic(PluginDiagnostic(
                level="error",
                plugin_id=record.id,
                source=record.source,
                message=f"http route already registered: {normalized}",
            ))
            return
        record.http_handlers += 1
        registry.http_routes.append(PluginHttpRouteRegistration(
            plugin_id=record.id,
            path=normalized,
            handler=handler,
            source=record.source,
        ))

    # --- Channel ---

    def register_channel(
        record: PluginRecord,
        registration: Any,
    ) -> None:
        if hasattr(registration, "plugin") and registration.plugin:
            normalized = registration
            plugin_obj = registration.plugin
            dock = getattr(registration, "dock", None)
        else:
            plugin_obj = registration
            dock = None

        plugin_id_val = str(getattr(plugin_obj, "id", "")).strip()
        if not plugin_id_val:
            _push_diagnostic(PluginDiagnostic(
                level="error",
                plugin_id=record.id,
                source=record.source,
                message="channel registration missing id",
            ))
            return
        record.channel_ids.append(plugin_id_val)
        registry.channels.append(PluginChannelRegistration(
            plugin_id=record.id,
            plugin=plugin_obj,
            dock=dock,
            source=record.source,
        ))

    # --- Provider ---

    def register_provider(record: PluginRecord, provider: ProviderPlugin) -> None:
        pid = str(getattr(provider, "id", "")).strip()
        if not pid:
            _push_diagnostic(PluginDiagnostic(
                level="error",
                plugin_id=record.id,
                source=record.source,
                message="provider registration missing id",
            ))
            return
        existing = next((e for e in registry.providers if e.provider.id == pid), None)
        if existing:
            _push_diagnostic(PluginDiagnostic(
                level="error",
                plugin_id=record.id,
                source=record.source,
                message=f"provider already registered: {pid} ({existing.plugin_id})",
            ))
            return
        record.provider_ids.append(pid)
        registry.providers.append(PluginProviderRegistration(
            plugin_id=record.id,
            provider=provider,
            source=record.source,
        ))

    # --- CLI ---

    def register_cli(
        record: PluginRecord,
        registrar: OpenClawPluginCliRegistrar,
        opts: dict | None = None,
    ) -> None:
        commands = [c.strip() for c in (opts.get("commands") or [] if opts else []) if c.strip()]
        record.cli_commands.extend(commands)
        registry.cli_registrars.append(PluginCliRegistration(
            plugin_id=record.id,
            register=registrar,
            commands=commands,
            source=record.source,
        ))

    # --- Service ---

    def register_service(record: PluginRecord, service: OpenClawPluginService) -> None:
        sid = service.id.strip()
        if not sid:
            return
        record.services.append(sid)
        registry.services.append(PluginServiceRegistration(
            plugin_id=record.id,
            service=service,
            source=record.source,
        ))

    # --- Command ---

    def register_command(record: PluginRecord, command: OpenClawPluginCommandDefinition) -> None:
        name = command.name.strip()
        if not name:
            _push_diagnostic(PluginDiagnostic(
                level="error",
                plugin_id=record.id,
                source=record.source,
                message="command registration missing name",
            ))
            return
        result = register_plugin_command(record.id, command)
        if not result["ok"]:
            _push_diagnostic(PluginDiagnostic(
                level="error",
                plugin_id=record.id,
                source=record.source,
                message=f"command registration failed: {result['error']}",
            ))
            return
        record.commands.append(name)
        registry.commands.append(PluginCommandRegistration(
            plugin_id=record.id,
            command=command,
            source=record.source,
        ))

    # --- API factory ---

    def create_api(
        record: PluginRecord,
        config: Any = None,
        plugin_config: dict | None = None,
    ) -> Any:
        """Build an OpenClawPluginApi-compatible object for plugin activation."""
        return ConcretePluginApi(
            record=record,
            plugin_config=plugin_config,
            config=config,
            runtime=runtime,
            plugin_logger=_normalize_logger(plugin_logger),
            # bound methods
            _register_tool=register_tool,
            _register_hook=register_hook,
            _register_http_handler=register_http_handler,
            _register_http_route=register_http_route,
            _register_channel=register_channel,
            _register_gateway_method=register_gateway_method,
            _register_cli=register_cli,
            _register_service=register_service,
            _register_provider=register_provider,
            _register_command=register_command,
            _register_typed_hook=register_typed_hook,
        )

    return PluginRegistryApi(
        registry=registry,
        create_api=create_api,
        push_diagnostic=_push_diagnostic,
        register_tool=register_tool,
        register_channel=register_channel,
        register_provider=register_provider,
        register_gateway_method=register_gateway_method,
        register_http_handler=register_http_handler,
        register_http_route=register_http_route,
        register_cli=register_cli,
        register_service=register_service,
        register_command=register_command,
        register_hook=register_hook,
        register_typed_hook=register_typed_hook,
    )


@dataclass
class PluginRegistryApi:
    """Returned by create_plugin_registry — mirrors the return of createPluginRegistry."""
    registry: PluginRegistryData
    create_api: Any
    push_diagnostic: Any
    register_tool: Any
    register_channel: Any
    register_provider: Any
    register_gateway_method: Any
    register_http_handler: Any
    register_http_route: Any
    register_cli: Any
    register_service: Any
    register_command: Any
    register_hook: Any
    register_typed_hook: Any


# ---------------------------------------------------------------------------
# Concrete OpenClawPluginApi implementation
# ---------------------------------------------------------------------------

class ConcretePluginApi:
    """Concrete implementation of OpenClawPluginApi handed to plugins."""

    def __init__(
        self,
        record: PluginRecord,
        config: Any,
        plugin_logger: PluginLogger,
        _register_tool: Any,
        _register_hook: Any,
        _register_http_handler: Any,
        _register_http_route: Any,
        _register_channel: Any,
        _register_gateway_method: Any,
        _register_cli: Any,
        _register_service: Any,
        _register_provider: Any,
        _register_command: Any,
        _register_typed_hook: Any,
        plugin_config: dict | None = None,
        runtime: Any = None,
    ):
        self._record = record
        self._config = config
        self._plugin_logger = plugin_logger
        self._rt = _register_tool
        self._rh = _register_hook
        self._rhh = _register_http_handler
        self._rhr = _register_http_route
        self._rc = _register_channel
        self._rgm = _register_gateway_method
        self._rcli = _register_cli
        self._rs = _register_service
        self._rp = _register_provider
        self._rcmd = _register_command
        self._rth = _register_typed_hook

        self.id = record.id
        self.name = record.name
        self.version = record.version
        self.description = record.description
        self.source = record.source
        self.config = config
        self.plugin_config = plugin_config
        self.runtime = runtime
        self.logger = plugin_logger

    def register_tool(self, tool: Any, opts: Any = None) -> None:
        self._rt(self._record, tool, opts)

    def register_hook(self, events: Any, handler: Any, opts: Any = None) -> None:
        self._rh(self._record, events, handler, opts, self._config)

    def register_http_handler(self, handler: Any) -> None:
        self._rhh(self._record, handler)

    def register_http_route(self, path: str, handler: Any) -> None:
        self._rhr(self._record, path, handler)

    def register_channel(self, registration: Any) -> None:
        self._rc(self._record, registration)

    def register_gateway_method(self, method: str, handler: Any) -> None:
        self._rgm(self._record, method, handler)

    def register_cli(self, registrar: Any, opts: dict | None = None) -> None:
        self._rcli(self._record, registrar, opts)

    def register_service(self, service: Any) -> None:
        self._rs(self._record, service)

    def register_provider(self, provider: Any) -> None:
        self._rp(self._record, provider)

    def register_command(self, command: Any) -> None:
        self._rcmd(self._record, command)

    def resolve_path(self, input_path: str) -> str:
        return os.path.expanduser(input_path)

    def on(self, hook_name: str, handler: Any, opts: dict | None = None) -> None:
        self._rth(self._record, hook_name, handler, opts)
