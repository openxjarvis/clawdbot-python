"""Plugin type definitions.

Python equivalents of TypeScript src/plugins/types.ts and src/plugins/registry.ts.

Defines all plugin hook names, registration types, PluginRecord, PluginRegistry,
and the OpenClawPluginApi protocol.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import (
    Any,
    Awaitable,
    Callable,
    Literal,
    Protocol,
    TypedDict,
    runtime_checkable,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Plugin Hook Names (mirrors TS PluginHookName union)
# =============================================================================

PluginHookName = Literal[
    "before_model_resolve",
    "before_prompt_build",
    "before_agent_start",
    "llm_input",
    "llm_output",
    "agent_end",
    "before_compaction",
    "after_compaction",
    "before_reset",
    "message_received",
    "message_sending",
    "message_sent",
    "before_tool_call",
    "after_tool_call",
    "tool_result_persist",
    "before_message_write",
    "session_start",
    "session_end",
    "gateway_start",
    "gateway_stop",
]

PLUGIN_HOOK_NAMES: frozenset[str] = frozenset([
    "before_model_resolve",
    "before_prompt_build",
    "before_agent_start",
    "llm_input",
    "llm_output",
    "agent_end",
    "before_compaction",
    "after_compaction",
    "before_reset",
    "message_received",
    "message_sending",
    "message_sent",
    "before_tool_call",
    "after_tool_call",
    "tool_result_persist",
    "before_message_write",
    "session_start",
    "session_end",
    "gateway_start",
    "gateway_stop",
])

# Handler callable types
VoidHookHandler = Callable[[dict[str, Any], dict[str, Any]], Awaitable[None] | None]
ModifyingHookHandler = Callable[[dict[str, Any], dict[str, Any]], Awaitable[dict[str, Any] | None] | dict[str, Any] | None]
SyncHookHandler = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any] | None]

# =============================================================================
# Typed Hook Registration (mirrors TS TypedPluginHookRegistration)
# =============================================================================

@dataclass
class TypedPluginHookRegistration:
    """Typed plugin lifecycle hook registration."""
    plugin_id: str
    hook_name: str           # One of PluginHookName
    handler: Callable        # The handler function
    priority: int = 0        # Higher = runs first
    source: str = ""


# =============================================================================
# Plugin Registration Types
# =============================================================================

@dataclass
class PluginToolRegistration:
    """Tool registered by a plugin."""
    plugin_id: str
    factory: Callable        # Tool factory or tool object
    names: list[str] = field(default_factory=list)
    optional: bool = False
    source: str = ""


@dataclass
class PluginHookRegistration:
    """Internal hook registered by a plugin.

    Supports two calling conventions:
    - Legacy:  PluginHookRegistration(plugin_id, events=[...], handler=fn, source="")
    - New API: PluginHookRegistration(plugin_id, hook_name, handler, source, priority=0)
    """
    plugin_id: str
    hook_name: str = ""          # Single hook name (new API)
    handler: Callable = field(default=lambda e, ctx=None: None)
    source: str = ""
    priority: int = 0
    # Legacy fields kept for backward compat
    events: list[str] = field(default_factory=list)
    entry: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        # Sync events ↔ hook_name for cross-API compatibility
        if self.hook_name and not self.events:
            self.events = [self.hook_name]
        elif self.events and not self.hook_name:
            self.hook_name = self.events[0] if self.events else ""


@dataclass
class PluginChannelRegistration:
    """Channel plugin registered by a plugin."""
    plugin_id: str
    plugin: Any              # ChannelPlugin instance
    dock: Any | None = None  # ChannelDock
    source: str = ""


@dataclass
class PluginProviderRegistration:
    """Model provider registered by a plugin."""
    plugin_id: str
    provider: "ProviderPlugin"
    source: str = ""


@dataclass
class PluginHttpRegistration:
    """HTTP handler registered by a plugin."""
    plugin_id: str
    handler: Callable
    source: str = ""


@dataclass
class PluginHttpRouteRegistration:
    """HTTP route registered by a plugin."""
    plugin_id: str | None
    path: str
    handler: Callable
    source: str = ""


@dataclass
class PluginCliRegistration:
    """CLI registrar registered by a plugin."""
    plugin_id: str
    register: Callable
    commands: list[str] = field(default_factory=list)
    source: str = ""


@dataclass
class PluginServiceRegistration:
    """Background service registered by a plugin."""
    plugin_id: str
    service: "OpenClawPluginService"
    source: str = ""


@dataclass
class PluginCommandRegistration:
    """Custom command registered by a plugin."""
    plugin_id: str
    command: "OpenClawPluginCommandDefinition"
    source: str = ""


@dataclass
class PluginGatewayMethodRegistration:
    """Gateway RPC method registered by a plugin."""
    plugin_id: str
    method: str
    handler: Callable
    source: str = ""


# =============================================================================
# Plugin Record (mirrors TS PluginRecord)
# =============================================================================

@dataclass
class PluginRecord:
    """Metadata record for a loaded plugin."""
    id: str
    name: str
    version: str | None = None
    description: str | None = None
    kind: str | None = None             # e.g. "memory"
    source: str = ""
    origin: str = "global"              # "bundled" | "global" | "workspace" | "config"
    workspace_dir: str | None = None
    enabled: bool = True
    status: str = "loaded"             # "loaded" | "disabled" | "error"
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
    config_ui_hints: dict[str, Any] | None = None
    config_json_schema: dict[str, Any] | None = None


# =============================================================================
# Plugin Diagnostic
# =============================================================================

@dataclass
class PluginDiagnostic:
    """Plugin diagnostic message."""
    level: str           # "warn" | "error"
    message: str
    plugin_id: str | None = None
    source: str | None = None


# =============================================================================
# Plugin Registry (mirrors TS PluginRegistry)
# =============================================================================

@dataclass
class PluginRegistry:
    """Registry of all loaded plugins and their contributions."""
    plugins: list[PluginRecord] = field(default_factory=list)
    tools: list[PluginToolRegistration] = field(default_factory=list)
    hooks: list[PluginHookRegistration] = field(default_factory=list)
    typed_hooks: list[TypedPluginHookRegistration] = field(default_factory=list)
    channels: list[PluginChannelRegistration] = field(default_factory=list)
    providers: list[PluginProviderRegistration] = field(default_factory=list)
    gateway_handlers: dict[str, Callable] = field(default_factory=dict)
    http_handlers: list[PluginHttpRegistration] = field(default_factory=list)
    http_routes: list[PluginHttpRouteRegistration] = field(default_factory=list)
    cli_registrars: list[PluginCliRegistration] = field(default_factory=list)
    services: list[PluginServiceRegistration] = field(default_factory=list)
    commands: list[PluginCommandRegistration] = field(default_factory=list)
    diagnostics: list[PluginDiagnostic] = field(default_factory=list)


def create_empty_plugin_registry() -> PluginRegistry:
    """Create an empty plugin registry."""
    return PluginRegistry()


# =============================================================================
# Provider Plugin (mirrors TS ProviderPlugin)
# =============================================================================

@dataclass
class ProviderAuthMethod:
    """Auth method for a provider plugin."""
    id: str
    label: str
    kind: str           # "oauth" | "api_key" | "token" | "device_code" | "custom"
    hint: str | None = None
    run: Callable | None = None


@dataclass
class ProviderPlugin:
    """Model provider registered by a plugin."""
    id: str
    label: str
    auth: list[ProviderAuthMethod] = field(default_factory=list)
    docs_path: str | None = None
    aliases: list[str] = field(default_factory=list)
    env_vars: list[str] = field(default_factory=list)
    models: dict[str, Any] | None = None
    format_api_key: Callable | None = None
    refresh_oauth: Callable | None = None


# =============================================================================
# Plugin Service (mirrors TS OpenClawPluginService)
# =============================================================================

@dataclass
class OpenClawPluginService:
    """Background service registered by a plugin."""
    id: str
    start: Callable      # async (ctx) -> None
    stop: Callable | None = None   # async (ctx) -> None


# =============================================================================
# Plugin Command (mirrors TS OpenClawPluginCommandDefinition)
# =============================================================================

@dataclass
class OpenClawPluginCommandDefinition:
    """Custom command registered by a plugin."""
    name: str            # Command name without leading slash
    description: str
    handler: Callable
    accepts_args: bool = False
    require_auth: bool = True


# =============================================================================
# Plugin Logger
# =============================================================================

class PluginLogger(Protocol):
    """Logger interface for plugins."""

    def info(self, message: str) -> None: ...
    def warn(self, message: str) -> None: ...
    def error(self, message: str) -> None: ...
    def debug(self, message: str) -> None: ...


# =============================================================================
# OpenClawPluginApi Protocol (mirrors TS OpenClawPluginApi)
# =============================================================================

@runtime_checkable
class OpenClawPluginApiProtocol(Protocol):
    """Protocol for the plugin API object passed to plugin register() functions."""

    id: str
    name: str
    version: str | None
    description: str | None
    source: str
    config: dict[str, Any]
    plugin_config: dict[str, Any] | None
    logger: PluginLogger

    def register_tool(self, tool: Any, opts: dict[str, Any] | None = None) -> None: ...
    def register_hook(self, events: str | list[str], handler: Callable, opts: dict[str, Any] | None = None) -> None: ...
    def register_http_handler(self, handler: Callable) -> None: ...
    def register_http_route(self, path: str, handler: Callable) -> None: ...
    def register_channel(self, registration: Any) -> None: ...
    def register_gateway_method(self, method: str, handler: Callable) -> None: ...
    def register_cli(self, registrar: Callable, opts: dict[str, Any] | None = None) -> None: ...
    def register_service(self, service: OpenClawPluginService) -> None: ...
    def register_provider(self, provider: ProviderPlugin) -> None: ...
    def register_command(self, command: OpenClawPluginCommandDefinition) -> None: ...
    def on(self, hook_name: str, handler: Callable, opts: dict[str, Any] | None = None) -> None: ...
    def resolve_path(self, input: str) -> str: ...


# =============================================================================
# Typed Hook Event / Context / Result classes (used by hooks.py)
# Each class mirrors a TypeScript interface in src/plugins/hooks.ts
# =============================================================================

@dataclass
class PluginHookAgentContext:
    """Agent context shared across agent hooks. Mirrors TS PluginHookAgentContext."""
    agent_id: str | None = None
    session_key: str | None = None
    session_id: str | None = None
    workspace_dir: str | None = None
    message_provider: str | None = None


@dataclass
class PluginHookSessionContext:
    """Context passed to session lifecycle hooks. Mirrors TS PluginHookSessionContext."""
    agent_id: str | None = None
    session_id: str = ""


@dataclass
class PluginHookGatewayContext:
    """Context passed to gateway lifecycle hooks. Mirrors TS PluginHookGatewayContext."""
    port: int | None = None


@dataclass
class PluginHookMessageContext:
    """Context passed to message-related hooks. Mirrors TS PluginHookMessageContext."""
    channel_id: str = ""
    account_id: str | None = None
    conversation_id: str | None = None


@dataclass
class PluginHookToolContext:
    """Context passed to tool-related hooks. Mirrors TS PluginHookToolContext."""
    agent_id: str | None = None
    session_key: str | None = None
    tool_name: str = ""


@dataclass
class PluginHookToolResultPersistContext:
    """Context passed to tool_result_persist hook. Mirrors TS PluginHookToolResultPersistContext."""
    agent_id: str | None = None
    session_key: str | None = None
    tool_name: str | None = None
    tool_call_id: str | None = None


# =============================================================================
# Hook event / result dataclasses — mirrors TS src/plugins/types.ts exactly
# =============================================================================

@dataclass
class PluginHookBeforeModelResolveEvent:
    """Mirrors TS PluginHookBeforeModelResolveEvent.
    User prompt for this run. No session messages available yet.
    """
    prompt: str = ""


@dataclass
class PluginHookBeforeModelResolveResult:
    """Mirrors TS PluginHookBeforeModelResolveResult."""
    model_override: str | None = None
    provider_override: str | None = None


@dataclass
class PluginHookBeforePromptBuildEvent:
    """Mirrors TS PluginHookBeforePromptBuildEvent."""
    prompt: str = ""
    messages: list[Any] = field(default_factory=list)


@dataclass
class PluginHookBeforePromptBuildResult:
    """Mirrors TS PluginHookBeforePromptBuildResult."""
    system_prompt: str | None = None
    prepend_context: str | None = None


@dataclass
class PluginHookBeforeAgentStartEvent:
    """Mirrors TS PluginHookBeforeAgentStartEvent (combines both phases for legacy compat)."""
    prompt: str = ""
    messages: list[Any] | None = None


@dataclass
class PluginHookBeforeAgentStartResult:
    """Mirrors TS PluginHookBeforeAgentStartResult."""
    system_prompt: str | None = None
    prepend_context: str | None = None
    model_override: str | None = None
    provider_override: str | None = None


@dataclass
class PluginHookLlmInputEvent:
    """Mirrors TS PluginHookLlmInputEvent."""
    run_id: str = ""
    session_id: str = ""
    provider: str = ""
    model: str = ""
    system_prompt: str | None = None
    prompt: str = ""
    history_messages: list[Any] = field(default_factory=list)
    images_count: int = 0


@dataclass
class PluginHookLlmOutputEvent:
    """Mirrors TS PluginHookLlmOutputEvent."""
    run_id: str = ""
    session_id: str = ""
    provider: str = ""
    model: str = ""
    assistant_texts: list[str] = field(default_factory=list)
    last_assistant: Any = None
    usage: dict[str, Any] | None = None


@dataclass
class PluginHookAgentEndEvent:
    """Mirrors TS PluginHookAgentEndEvent."""
    messages: list[Any] = field(default_factory=list)
    success: bool = True
    error: str | None = None
    duration_ms: int | None = None


@dataclass
class PluginHookBeforeCompactionEvent:
    """Mirrors TS PluginHookBeforeCompactionEvent."""
    message_count: int = 0
    compacting_count: int | None = None
    token_count: int | None = None
    messages: list[Any] | None = None
    session_file: str | None = None


@dataclass
class PluginHookAfterCompactionEvent:
    """Mirrors TS PluginHookAfterCompactionEvent."""
    message_count: int = 0
    token_count: int | None = None
    compacted_count: int = 0
    session_file: str | None = None


@dataclass
class PluginHookBeforeResetEvent:
    """Mirrors TS PluginHookBeforeResetEvent."""
    session_file: str | None = None
    messages: list[Any] | None = None
    reason: str | None = None


@dataclass
class PluginHookMessageReceivedEvent:
    """Mirrors TS PluginHookMessageReceivedEvent."""
    from_: str = ""
    content: str = ""
    timestamp: int | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class PluginHookMessageSendingEvent:
    """Mirrors TS PluginHookMessageSendingEvent."""
    to: str = ""
    content: str = ""
    metadata: dict[str, Any] | None = None


@dataclass
class PluginHookMessageSendingResult:
    """Mirrors TS PluginHookMessageSendingResult."""
    content: str | None = None
    cancel: bool = False


@dataclass
class PluginHookMessageSentEvent:
    """Mirrors TS PluginHookMessageSentEvent."""
    to: str = ""
    content: str = ""
    success: bool = True
    error: str | None = None


@dataclass
class PluginHookBeforeToolCallEvent:
    """Mirrors TS PluginHookBeforeToolCallEvent."""
    tool_name: str = ""
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class PluginHookBeforeToolCallResult:
    """Mirrors TS PluginHookBeforeToolCallResult."""
    params: dict[str, Any] | None = None
    block: bool = False
    block_reason: str | None = None


@dataclass
class PluginHookAfterToolCallEvent:
    """Mirrors TS PluginHookAfterToolCallEvent."""
    tool_name: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    result: Any = None
    error: str | None = None
    duration_ms: int | None = None


@dataclass
class PluginHookToolResultPersistEvent:
    """Mirrors TS PluginHookToolResultPersistEvent."""
    tool_name: str | None = None
    tool_call_id: str | None = None
    message: Any = None
    is_synthetic: bool = False


@dataclass
class PluginHookToolResultPersistResult:
    """Mirrors TS PluginHookToolResultPersistResult."""
    message: Any = None


@dataclass
class PluginHookBeforeMessageWriteEvent:
    """Mirrors TS PluginHookBeforeMessageWriteEvent."""
    message: Any = None
    session_key: str | None = None
    agent_id: str | None = None


@dataclass
class PluginHookBeforeMessageWriteResult:
    """Mirrors TS PluginHookBeforeMessageWriteResult."""
    block: bool = False
    message: Any = None


@dataclass
class PluginHookSessionStartEvent:
    """Mirrors TS PluginHookSessionStartEvent."""
    session_id: str = ""
    resumed_from: str | None = None


@dataclass
class PluginHookSessionEndEvent:
    """Mirrors TS PluginHookSessionEndEvent."""
    session_id: str = ""
    message_count: int = 0
    duration_ms: int | None = None


@dataclass
class PluginHookGatewayStartEvent:
    """Mirrors TS PluginHookGatewayStartEvent."""
    port: int = 0


@dataclass
class PluginHookGatewayStopEvent:
    """Mirrors TS PluginHookGatewayStopEvent."""
    reason: str | None = None


# =============================================================================
# Additional types expected by __init__.py and other existing modules
# =============================================================================

@dataclass
class OpenClawPluginServiceContext:
    """Context passed to plugin service start/stop. Mirrors TS OpenClawPluginServiceContext."""
    config: dict[str, Any] = field(default_factory=dict)
    workspace_dir: str | None = None
    state_dir: str = ""
    logger: Any = None


@dataclass
class OpenClawPluginDefinition:
    """Plugin definition object. Mirrors TS OpenClawPluginDefinition."""
    id: str
    name: str
    version: str | None = None
    description: str | None = None
    kind: str | None = None
    register: Callable | None = None


@dataclass
class OpenClawPluginHookOptions:
    """Options for registering a plugin hook."""
    priority: int = 0
    entry: dict[str, Any] | None = None


@dataclass
class OpenClawPluginToolOptions:
    """Options for registering a plugin tool."""
    name: str | None = None
    names: list[str] | None = None
    optional: bool = False


PluginKind = Literal["memory", "search", "calendar", "contact", "custom"]
PluginOrigin = Literal["bundled", "global", "workspace", "config"]

# Aliases for backward-compat with existing modules
Plugin = OpenClawPluginDefinition
PluginAPI = "OpenClawPluginApiProtocol"  # string to avoid self-ref


@dataclass
class PluginConfigUiHint:
    """UI hint for a config field. Mirrors TS PluginConfigUiHint."""
    label: str | None = None
    help: str | None = None
    advanced: bool = False
    sensitive: bool = False
    placeholder: str | None = None


# PluginManifest type alias (for loader.py and manifest.py compatibility)
# The full PluginManifest is defined in manifest.py; this is a forward reference
PluginManifest = Any  # type: ignore[misc]


@dataclass
class OpenClawPluginApi:
    """Legacy alias — use PluginApi from api.py for new code."""
    id: str = ""
    name: str = ""


__all__ = [
    "PluginHookName",
    "PLUGIN_HOOK_NAMES",
    "TypedPluginHookRegistration",
    "PluginToolRegistration",
    "PluginHookRegistration",
    "PluginChannelRegistration",
    "PluginProviderRegistration",
    "PluginHttpRegistration",
    "PluginHttpRouteRegistration",
    "PluginCliRegistration",
    "PluginServiceRegistration",
    "PluginCommandRegistration",
    "PluginGatewayMethodRegistration",
    "PluginRecord",
    "PluginDiagnostic",
    "PluginRegistry",
    "create_empty_plugin_registry",
    "ProviderAuthMethod",
    "ProviderPlugin",
    "OpenClawPluginService",
    "OpenClawPluginServiceContext",
    "OpenClawPluginCommandDefinition",
    "PluginLogger",
    "OpenClawPluginApiProtocol",
    "PluginConfigUiHint",
    # Hook contexts
    "PluginHookAgentContext",
    "PluginHookSessionContext",
    "PluginHookGatewayContext",
    "PluginHookMessageContext",
    "PluginHookToolContext",
    "PluginHookToolResultPersistContext",
    # Hook events and results
    "PluginHookBeforeModelResolveEvent",
    "PluginHookBeforeModelResolveResult",
    "PluginHookBeforePromptBuildEvent",
    "PluginHookBeforePromptBuildResult",
    "PluginHookBeforeAgentStartEvent",
    "PluginHookBeforeAgentStartResult",
    "PluginHookLlmInputEvent",
    "PluginHookLlmOutputEvent",
    "PluginHookAgentEndEvent",
    "PluginHookBeforeCompactionEvent",
    "PluginHookAfterCompactionEvent",
    "PluginHookBeforeResetEvent",
    "PluginHookMessageReceivedEvent",
    "PluginHookMessageSendingEvent",
    "PluginHookMessageSendingResult",
    "PluginHookMessageSentEvent",
    "PluginHookBeforeToolCallEvent",
    "PluginHookBeforeToolCallResult",
    "PluginHookAfterToolCallEvent",
    "PluginHookToolResultPersistEvent",
    "PluginHookToolResultPersistResult",
    "PluginHookBeforeMessageWriteEvent",
    "PluginHookBeforeMessageWriteResult",
    "PluginHookSessionStartEvent",
    "PluginHookSessionEndEvent",
    "PluginHookGatewayStartEvent",
    "PluginHookGatewayStopEvent",
    # Backward-compat types
    "OpenClawPluginDefinition",
    "OpenClawPluginHookOptions",
    "OpenClawPluginToolOptions",
    "OpenClawPluginApi",
    "Plugin",
    "PluginKind",
    "PluginOrigin",
    "PluginManifest",
]
