"""Plugin type definitions — mirrors src/plugins/types.ts"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Literal, Protocol


# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

class PluginLogger(Protocol):
    def info(self, message: str) -> None: ...
    def warn(self, message: str) -> None: ...
    def error(self, message: str) -> None: ...
    def debug(self, message: str) -> None: ...


# ---------------------------------------------------------------------------
# Basic types
# ---------------------------------------------------------------------------

PluginKind = Literal["memory"]
PluginOrigin = Literal["bundled", "global", "workspace", "config"]


@dataclass
class PluginConfigUiHint:
    label: str | None = None
    help: str | None = None
    advanced: bool = False
    sensitive: bool = False
    placeholder: str | None = None


@dataclass
class PluginDiagnostic:
    level: Literal["warn", "error"]
    message: str
    plugin_id: str | None = None
    source: str | None = None


# ---------------------------------------------------------------------------
# Config schema
# ---------------------------------------------------------------------------

class PluginConfigValidationOk:
    ok: bool = True
    value: Any = None


class PluginConfigValidationFail:
    ok: bool = False
    errors: list[str] = field(default_factory=list)


PluginConfigValidation = PluginConfigValidationOk | PluginConfigValidationFail


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

@dataclass
class OpenClawPluginToolContext:
    config: Any = None
    workspace_dir: str | None = None
    agent_dir: str | None = None
    agent_id: str | None = None
    session_key: str | None = None
    message_channel: str | None = None
    agent_account_id: str | None = None
    sandboxed: bool = False


OpenClawPluginToolFactory = Callable[[OpenClawPluginToolContext], Any]


@dataclass
class OpenClawPluginToolOptions:
    name: str | None = None
    names: list[str] | None = None
    optional: bool = False


# ---------------------------------------------------------------------------
# Hook options
# ---------------------------------------------------------------------------

@dataclass
class OpenClawPluginHookOptions:
    entry: Any = None
    name: str | None = None
    description: str | None = None
    register: bool = True


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------

ProviderAuthKind = Literal["oauth", "api_key", "token", "device_code", "custom"]


@dataclass
class ProviderAuthResult:
    profiles: list[dict] = field(default_factory=list)
    config_patch: dict | None = None
    default_model: str | None = None
    notes: list[str] | None = None


@dataclass
class ProviderAuthMethod:
    id: str
    label: str
    kind: ProviderAuthKind
    run: Callable[..., Awaitable[ProviderAuthResult]] = field(default=None)  # type: ignore[assignment]
    hint: str | None = None


@dataclass
class ProviderPlugin:
    id: str
    label: str
    auth: list[ProviderAuthMethod] = field(default_factory=list)
    docs_path: str | None = None
    aliases: list[str] | None = None
    env_vars: list[str] | None = None
    models: dict | None = None


# ---------------------------------------------------------------------------
# Gateway method
# ---------------------------------------------------------------------------

@dataclass
class OpenClawPluginGatewayMethod:
    method: str
    handler: Callable[..., Any]


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@dataclass
class PluginCommandContext:
    channel: str
    is_authorized_sender: bool
    command_body: str
    config: Any = None
    sender_id: str | None = None
    channel_id: str | None = None
    args: str | None = None
    from_: str | None = None
    to: str | None = None
    account_id: str | None = None
    message_thread_id: int | None = None


PluginCommandHandler = Callable[[PluginCommandContext], Any]


@dataclass
class OpenClawPluginCommandDefinition:
    name: str
    description: str
    handler: PluginCommandHandler
    accepts_args: bool = False
    require_auth: bool = True


# ---------------------------------------------------------------------------
# HTTP / CLI / Service
# ---------------------------------------------------------------------------

OpenClawPluginHttpHandler = Callable[..., Any]
OpenClawPluginHttpRouteHandler = Callable[..., Any]
OpenClawPluginCliRegistrar = Callable[..., Any]


@dataclass
class OpenClawPluginServiceContext:
    config: Any
    state_dir: str
    workspace_dir: str | None = None
    logger: PluginLogger | None = None  # type: ignore[assignment]


@dataclass
class OpenClawPluginService:
    id: str
    start: Callable[[OpenClawPluginServiceContext], Any]
    stop: Callable[[OpenClawPluginServiceContext], Any] | None = None


@dataclass
class OpenClawPluginChannelRegistration:
    plugin: Any  # ChannelPlugin
    dock: Any | None = None  # ChannelDock


# ---------------------------------------------------------------------------
# Plugin definition and API
# ---------------------------------------------------------------------------

@dataclass
class OpenClawPluginDefinition:
    id: str | None = None
    name: str | None = None
    description: str | None = None
    version: str | None = None
    kind: PluginKind | None = None
    config_schema: Any = None
    register: Callable[..., Any] | None = None
    activate: Callable[..., Any] | None = None


class OpenClawPluginApi(Protocol):
    """API object passed to plugin activate() — mirrors TS OpenClawPluginApi."""

    id: str
    name: str
    version: str | None
    description: str | None
    source: str
    config: Any
    plugin_config: dict | None
    runtime: Any  # PluginRuntime
    logger: PluginLogger

    def register_tool(self, tool: Any, opts: OpenClawPluginToolOptions | None = None) -> None: ...
    def register_hook(self, events: str | list[str], handler: Any, opts: OpenClawPluginHookOptions | None = None) -> None: ...
    def register_http_handler(self, handler: OpenClawPluginHttpHandler) -> None: ...
    def register_http_route(self, path: str, handler: OpenClawPluginHttpRouteHandler) -> None: ...
    def register_channel(self, registration: OpenClawPluginChannelRegistration | Any) -> None: ...
    def register_gateway_method(self, method: str, handler: Any) -> None: ...
    def register_cli(self, registrar: OpenClawPluginCliRegistrar, opts: dict | None = None) -> None: ...
    def register_service(self, service: OpenClawPluginService) -> None: ...
    def register_provider(self, provider: ProviderPlugin) -> None: ...
    def register_command(self, command: OpenClawPluginCommandDefinition) -> None: ...
    def resolve_path(self, input: str) -> str: ...
    def on(self, hook_name: "PluginHookName", handler: Any, opts: dict | None = None) -> None: ...


# ---------------------------------------------------------------------------
# Hook names and event types  (mirrors PluginHookName union)
# ---------------------------------------------------------------------------

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

PLUGIN_HOOK_NAMES: tuple[str, ...] = (
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
)

# --- Agent context ---

@dataclass
class PluginHookAgentContext:
    agent_id: str | None = None
    session_key: str | None = None
    session_id: str | None = None
    workspace_dir: str | None = None
    message_provider: str | None = None


# --- before_model_resolve ---

@dataclass
class PluginHookBeforeModelResolveEvent:
    prompt: str


@dataclass
class PluginHookBeforeModelResolveResult:
    model_override: str | None = None
    provider_override: str | None = None


# --- before_prompt_build ---

@dataclass
class PluginHookBeforePromptBuildEvent:
    prompt: str
    messages: list[Any] = field(default_factory=list)


@dataclass
class PluginHookBeforePromptBuildResult:
    system_prompt: str | None = None
    prepend_context: str | None = None


# --- before_agent_start ---

@dataclass
class PluginHookBeforeAgentStartEvent:
    prompt: str
    messages: list[Any] | None = None


@dataclass
class PluginHookBeforeAgentStartResult:
    system_prompt: str | None = None
    prepend_context: str | None = None
    model_override: str | None = None
    provider_override: str | None = None


# --- llm_input ---

@dataclass
class PluginHookLlmInputEvent:
    run_id: str
    session_id: str
    provider: str
    model: str
    prompt: str
    history_messages: list[Any] = field(default_factory=list)
    images_count: int = 0
    system_prompt: str | None = None


# --- llm_output ---

@dataclass
class PluginHookLlmOutputEvent:
    run_id: str
    session_id: str
    provider: str
    model: str
    assistant_texts: list[str] = field(default_factory=list)
    last_assistant: Any = None
    usage: dict | None = None


# --- agent_end ---

@dataclass
class PluginHookAgentEndEvent:
    messages: list[Any] = field(default_factory=list)
    success: bool = True
    error: str | None = None
    duration_ms: int | None = None


# --- before_compaction ---

@dataclass
class PluginHookBeforeCompactionEvent:
    message_count: int
    compacting_count: int | None = None
    token_count: int | None = None
    messages: list[Any] | None = None
    session_file: str | None = None


# --- after_compaction ---

@dataclass
class PluginHookAfterCompactionEvent:
    message_count: int
    compacted_count: int
    token_count: int | None = None
    session_file: str | None = None


# --- before_reset ---

@dataclass
class PluginHookBeforeResetEvent:
    session_file: str | None = None
    messages: list[Any] | None = None
    reason: str | None = None


# --- Message context ---

@dataclass
class PluginHookMessageContext:
    channel_id: str
    account_id: str | None = None
    conversation_id: str | None = None


# --- message_received ---

@dataclass
class PluginHookMessageReceivedEvent:
    from_: str
    content: str
    timestamp: int | None = None
    metadata: dict | None = None


# --- message_sending ---

@dataclass
class PluginHookMessageSendingEvent:
    to: str
    content: str
    metadata: dict | None = None


@dataclass
class PluginHookMessageSendingResult:
    content: str | None = None
    cancel: bool | None = None


# --- message_sent ---

@dataclass
class PluginHookMessageSentEvent:
    to: str
    content: str
    success: bool
    error: str | None = None


# --- Tool context ---

@dataclass
class PluginHookToolContext:
    tool_name: str
    agent_id: str | None = None
    session_key: str | None = None


# --- before_tool_call ---

@dataclass
class PluginHookBeforeToolCallEvent:
    tool_name: str
    params: dict = field(default_factory=dict)


@dataclass
class PluginHookBeforeToolCallResult:
    params: dict | None = None
    block: bool | None = None
    block_reason: str | None = None


# --- after_tool_call ---

@dataclass
class PluginHookAfterToolCallEvent:
    tool_name: str
    params: dict = field(default_factory=dict)
    result: Any = None
    error: str | None = None
    duration_ms: int | None = None


# --- tool_result_persist ---

@dataclass
class PluginHookToolResultPersistContext:
    agent_id: str | None = None
    session_key: str | None = None
    tool_name: str | None = None
    tool_call_id: str | None = None


@dataclass
class PluginHookToolResultPersistEvent:
    message: Any  # AgentMessage
    tool_name: str | None = None
    tool_call_id: str | None = None
    is_synthetic: bool = False


@dataclass
class PluginHookToolResultPersistResult:
    message: Any | None = None  # AgentMessage


# --- before_message_write ---

@dataclass
class PluginHookBeforeMessageWriteEvent:
    message: Any  # AgentMessage
    session_key: str | None = None
    agent_id: str | None = None


@dataclass
class PluginHookBeforeMessageWriteResult:
    block: bool | None = None
    message: Any | None = None  # AgentMessage


# --- Session context ---

@dataclass
class PluginHookSessionContext:
    session_id: str
    agent_id: str | None = None


@dataclass
class PluginHookSessionStartEvent:
    session_id: str
    resumed_from: str | None = None


@dataclass
class PluginHookSessionEndEvent:
    session_id: str
    message_count: int
    duration_ms: int | None = None


# --- Gateway context ---

@dataclass
class PluginHookGatewayContext:
    port: int | None = None


@dataclass
class PluginHookGatewayStartEvent:
    port: int


@dataclass
class PluginHookGatewayStopEvent:
    reason: str | None = None


# ---------------------------------------------------------------------------
# Hook registration
# ---------------------------------------------------------------------------

@dataclass
class PluginHookRegistration:
    plugin_id: str
    hook_name: str  # PluginHookName
    handler: Callable[..., Any]
    source: str
    priority: int = 0


# ---------------------------------------------------------------------------
# Manifest types (kept for backward compat from original types.py)
# ---------------------------------------------------------------------------

class PluginManifest:
    def __init__(
        self,
        id: str,
        name: str,
        version: str,
        description: str | None = None,
        author: str | None = None,
        main: str = "plugin.py",
        skills: list[str] | None = None,
        requires: list[str] | None = None,
    ):
        self.id = id
        self.name = name
        self.version = version
        self.description = description
        self.author = author
        self.main = main
        self.skills = skills or []
        self.requires = requires or []


class PluginAPI:
    """Concrete API object given to plugins that don't use the full OpenClawPluginApi."""

    def __init__(self, plugin_id: str):
        self.plugin_id = plugin_id
        self._tools: list[Any] = []
        self._channels: list[Any] = []
        self._hooks: list[tuple[str, Callable, int]] = []

    def register_tool(self, tool: Any) -> None:
        self._tools.append(tool)

    def register_channel(self, channel: Any) -> None:
        self._channels.append(channel)

    def register_hook(self, event: str, handler: Callable, priority: int = 0) -> None:
        self._hooks.append((event, handler, priority))

    def get_config(self) -> dict[str, Any]:
        return {}


class Plugin:
    """Base plugin class."""

    def __init__(self, manifest: PluginManifest, path: str):
        self.manifest = manifest
        self.path = path
        self.api: PluginAPI | None = None

    async def activate(self, api: PluginAPI) -> None:
        self.api = api

    async def deactivate(self) -> None:
        pass
