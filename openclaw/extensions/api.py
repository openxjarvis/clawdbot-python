"""Extension API passed to extension register().

Extensions use this to register tools, channels, providers, CLI commands,
HTTP handlers, background services, and lifecycle hooks.

Matches the TypeScript OpenClawPluginApi surface from openclaw/plugin-sdk.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from .types import ExtensionContext

logger = logging.getLogger(__name__)


class ExtensionAPI:
    """
    API passed to each extension's ``register(api)`` function.

    Mirrors the TypeScript ``OpenClawPluginApi`` interface:
    - ``register_tool()``       → ``api.registerTool()``
    - ``register_channel()``    → ``api.registerChannel()``
    - ``register_provider()``   → ``api.registerProvider()``
    - ``register_cli()``        → ``api.registerCli()``
    - ``register_http_handler()`` / ``register_http_route()``
                                → ``api.registerHttpHandler()``
    - ``register_service()``    → ``api.registerService()``
    - ``register_command()``    → ``api.registerCommand()``
    - ``on()``                  → ``api.on()`` / ``api.registerHook()``
    """

    def __init__(self, extension_id: str, context: ExtensionContext):
        self._extension_id = extension_id
        self._context = context
        self._tools: list[dict[str, Any]] = []
        self._channels: list[Any] = []
        self._providers: list[dict[str, Any]] = []
        self._cli_registrations: list[dict[str, Any]] = []
        self._http_routes: list[dict[str, Any]] = []
        self._services: list[dict[str, Any]] = []
        self._handlers: dict[str, list[Callable[..., Any]]] = {}
        self._commands: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Context
    # ------------------------------------------------------------------

    @property
    def context(self) -> ExtensionContext:
        return self._context

    # ------------------------------------------------------------------
    # Tools  (api.registerTool)
    # ------------------------------------------------------------------

    def register_tool(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        execute: Callable[..., Any],
    ) -> None:
        """Register a tool that the agent can call.

        Args:
            name: Tool name (used in LLM tool calls).
            description: Description shown to the LLM.
            parameters: JSON schema for the tool parameters.
            execute: Async callable(tool_call_id, params, signal, ctx) -> result.
        """
        self._tools.append({
            "name": name,
            "description": description,
            "parameters": parameters,
            "execute": execute,
            "extension_id": self._extension_id,
        })
        logger.debug("Extension %s registered tool %s", self._extension_id, name)

    # ------------------------------------------------------------------
    # Channels  (api.registerChannel)
    # ------------------------------------------------------------------

    def register_channel(self, channel: Any) -> None:
        """Register a messaging channel plugin.

        Args:
            channel: A ``ChannelPlugin`` instance (from openclaw.channels.base).
        """
        self._channels.append(channel)
        logger.debug(
            "Extension %s registered channel %s",
            self._extension_id,
            getattr(channel, "id", repr(channel)),
        )

    # ------------------------------------------------------------------
    # Providers  (api.registerProvider)
    # ------------------------------------------------------------------

    def register_provider(self, provider: dict[str, Any]) -> None:
        """Register an LLM provider.

        The ``provider`` dict mirrors the TS ``ProviderPlugin`` shape::

            {
                "id": "my-provider",
                "label": "My Provider",
                "base_url": "https://api.example.com/v1",
                "api_key": "...",          # or env var name
                "default_model_ids": [...],
                "context_window": 128_000,
                "max_tokens": 8192,
            }
        """
        self._providers.append({**provider, "extension_id": self._extension_id})
        logger.debug(
            "Extension %s registered provider %s",
            self._extension_id,
            provider.get("id", "?"),
        )

    # ------------------------------------------------------------------
    # CLI commands  (api.registerCli)
    # ------------------------------------------------------------------

    def register_cli(
        self,
        name: str,
        description: str,
        handler: Callable[..., Any],
        *,
        commands: list[str] | None = None,
    ) -> None:
        """Register a CLI command exposed via the OpenClaw CLI.

        Args:
            name: Command name (e.g. ``"memory"``).
            description: Short description for ``--help``.
            handler: Callable invoked when the command runs.
            commands: Optional list of sub-command names.
        """
        self._cli_registrations.append({
            "name": name,
            "description": description,
            "handler": handler,
            "commands": commands or [name],
            "extension_id": self._extension_id,
        })
        logger.debug("Extension %s registered CLI command %s", self._extension_id, name)

    # ------------------------------------------------------------------
    # HTTP routes  (api.registerHttpHandler / api.registerHttpRoute)
    # ------------------------------------------------------------------

    def register_http_handler(
        self,
        method: str,
        path: str,
        handler: Callable[..., Any],
        *,
        auth_required: bool = False,
    ) -> None:
        """Register an HTTP route on the gateway web server.

        Args:
            method: HTTP method (``"GET"``, ``"POST"``, …).
            path: URL path pattern (e.g. ``"/webhooks/twilio"``).
            handler: Async callable(request) -> response.
            auth_required: Whether the route requires authentication.
        """
        self._http_routes.append({
            "method": method.upper(),
            "path": path,
            "handler": handler,
            "auth_required": auth_required,
            "extension_id": self._extension_id,
        })
        logger.debug(
            "Extension %s registered HTTP %s %s",
            self._extension_id,
            method.upper(),
            path,
        )

    # Alias matching TS api.registerHttpRoute
    def register_http_route(
        self,
        method: str,
        path: str,
        handler: Callable[..., Any],
        *,
        auth_required: bool = False,
    ) -> None:
        """Alias for :meth:`register_http_handler`."""
        self.register_http_handler(method, path, handler, auth_required=auth_required)

    # ------------------------------------------------------------------
    # Background services  (api.registerService)
    # ------------------------------------------------------------------

    def register_service(
        self,
        name: str,
        start: Callable[..., Any],
        stop: Callable[..., Any] | None = None,
    ) -> None:
        """Register a long-running background service.

        Args:
            name: Service identifier.
            start: Async callable invoked at gateway startup.
            stop: Optional async callable invoked at gateway shutdown.
        """
        self._services.append({
            "name": name,
            "start": start,
            "stop": stop,
            "extension_id": self._extension_id,
        })
        logger.debug("Extension %s registered service %s", self._extension_id, name)

    # ------------------------------------------------------------------
    # Slash commands  (api.registerCommand)
    # ------------------------------------------------------------------

    def register_command(
        self,
        name: str,
        description: str,
        handler: Callable[..., Any],
    ) -> None:
        """Register a slash command (e.g. ``/mycommand``)."""
        self._commands[name] = {
            "name": name,
            "description": description,
            "handler": handler,
            "extension_id": self._extension_id,
        }
        logger.debug("Extension %s registered command /%s", self._extension_id, name)

    # ------------------------------------------------------------------
    # Lifecycle hooks  (api.on / api.registerHook)
    # ------------------------------------------------------------------

    def on(
        self,
        event: str,
        handler: Callable[..., Any] | None = None,
    ) -> Callable[..., Any] | None:
        """Subscribe to a lifecycle event.

        Supported events: ``agent_start``, ``agent_end``, ``turn_start``,
        ``turn_end``, ``before_agent_start``, ``tool_call``, ``tool_result``,
        ``session_start``, ``session_end``, ``message_received``.

        Can be used as a decorator::

            @api.on("before_agent_start")
            async def handler(event, context):
                ...

        Or called directly::

            api.on("before_agent_start", handler)
        """
        if handler is None:
            def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
                self._handlers.setdefault(event, []).append(fn)
                logger.debug(
                    "Extension %s registered hook for %s",
                    self._extension_id,
                    event,
                )
                return fn
            return decorator
        else:
            self._handlers.setdefault(event, []).append(handler)
            logger.debug(
                "Extension %s registered hook for %s", self._extension_id, event
            )
            return None

    # Alias matching TS api.registerHook
    def register_hook(
        self,
        event: str,
        handler: Callable[..., Any],
        *,
        priority: int = 0,
    ) -> None:
        """Alias for :meth:`on` with optional priority (higher = earlier)."""
        self._handlers.setdefault(event, []).append(handler)
        logger.debug(
            "Extension %s registered hook for %s (priority=%d)",
            self._extension_id,
            event,
            priority,
        )

    # ------------------------------------------------------------------
    # Accessors used by runner / loader
    # ------------------------------------------------------------------

    def get_tools(self) -> list[dict[str, Any]]:
        return self._tools.copy()

    def get_channels(self) -> list[Any]:
        return self._channels.copy()

    def get_providers(self) -> list[dict[str, Any]]:
        return self._providers.copy()

    def get_cli_registrations(self) -> list[dict[str, Any]]:
        return self._cli_registrations.copy()

    def get_http_routes(self) -> list[dict[str, Any]]:
        return self._http_routes.copy()

    def get_services(self) -> list[dict[str, Any]]:
        return self._services.copy()

    def get_handlers(self) -> dict[str, list[Callable[..., Any]]]:
        return self._handlers.copy()

    def get_commands(self) -> dict[str, dict[str, Any]]:
        return self._commands.copy()
