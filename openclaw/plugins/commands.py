"""Plugin Command Registry.

Manages commands registered by plugins that bypass the LLM agent.
These commands are processed before built-in commands and before agent invocation.

Fully aligned with TypeScript openclaw/src/plugins/commands.ts
"""
from __future__ import annotations

import logging
import re
from typing import Any, Awaitable, Callable, TypedDict

logger = logging.getLogger(__name__)


class PluginCommandContext(TypedDict, total=False):
    """Context passed to plugin command handlers."""
    sender_id: str | None
    channel: str
    channel_id: str | None
    is_authorized_sender: bool
    args: str | None
    command_body: str
    config: dict[str, Any]
    from_: str | None
    to: str | None
    account_id: str | None
    message_thread_id: str | None


class PluginCommandResult(TypedDict, total=False):
    """Result from a plugin command handler."""
    text: str
    markdown: bool
    html: bool


class OpenClawPluginCommandDefinition(TypedDict, total=False):
    """Plugin command definition."""
    name: str
    description: str
    accepts_args: bool
    require_auth: bool
    handler: Callable[[PluginCommandContext], Awaitable[PluginCommandResult]]


class RegisteredPluginCommand(TypedDict):
    """Registered plugin command with plugin ID."""
    plugin_id: str
    name: str
    description: str
    accepts_args: bool
    require_auth: bool
    handler: Callable[[PluginCommandContext], Awaitable[PluginCommandResult]]


RESERVED_COMMANDS = {
    "help",
    "commands",
    "status",
    "whoami",
    "context",
    "stop",
    "restart",
    "reset",
    "new",
    "compact",
    "config",
    "debug",
    "allowlist",
    "activation",
    "skill",
    "subagents",
    "kill",
    "steer",
    "tell",
    "model",
    "models",
    "queue",
    "send",
    "bash",
    "exec",
    "think",
    "verbose",
    "reasoning",
    "elevated",
    "usage",
}

MAX_ARGS_LENGTH = 4096

_plugin_commands: dict[str, RegisteredPluginCommand] = {}
_registry_locked = False


def validate_command_name(name: str) -> str | None:
    """Validate a command name (mirrors TS validateCommandName).
    
    Returns:
        Error message if invalid, None if valid
    """
    trimmed = name.strip().lower()
    
    if not trimmed:
        return "Command name cannot be empty"
    
    if not re.match(r"^[a-z][a-z0-9_-]*$", trimmed):
        return "Command name must start with a letter and contain only letters, numbers, hyphens, and underscores"
    
    if trimmed in RESERVED_COMMANDS:
        return f'Command name "{trimmed}" is reserved by a built-in command'
    
    return None


class CommandRegistrationResult(TypedDict):
    """Result of command registration."""
    ok: bool
    error: str | None


def register_plugin_command(
    plugin_id: str,
    command: OpenClawPluginCommandDefinition,
) -> CommandRegistrationResult:
    """Register a plugin command (mirrors TS registerPluginCommand).
    
    Args:
        plugin_id: ID of the plugin registering the command
        command: Command definition
        
    Returns:
        Registration result with ok status and optional error
    """
    global _registry_locked
    
    if _registry_locked:
        return CommandRegistrationResult(
            ok=False,
            error="Cannot register commands while processing is in progress",
        )
    
    if not callable(command.get("handler")):
        return CommandRegistrationResult(
            ok=False,
            error="Command handler must be a function",
        )
    
    validation_error = validate_command_name(command["name"])
    if validation_error:
        return CommandRegistrationResult(
            ok=False,
            error=validation_error,
        )
    
    key = f"/{command['name'].lower()}"
    
    if key in _plugin_commands:
        existing = _plugin_commands[key]
        return CommandRegistrationResult(
            ok=False,
            error=f"Command \"{command['name']}\" already registered by plugin \"{existing['plugin_id']}\"",
        )
    
    _plugin_commands[key] = RegisteredPluginCommand(
        plugin_id=plugin_id,
        name=command["name"],
        description=command.get("description", ""),
        accepts_args=command.get("accepts_args", True),
        require_auth=command.get("require_auth", True),
        handler=command["handler"],
    )
    
    logger.debug(f"Registered plugin command: {key} (plugin: {plugin_id})")
    return CommandRegistrationResult(ok=True, error=None)


def clear_plugin_commands() -> None:
    """Clear all registered plugin commands (mirrors TS clearPluginCommands)."""
    _plugin_commands.clear()


def clear_plugin_commands_for_plugin(plugin_id: str) -> None:
    """Clear plugin commands for a specific plugin (mirrors TS clearPluginCommandsForPlugin)."""
    keys_to_remove = [
        key for key, cmd in _plugin_commands.items()
        if cmd["plugin_id"] == plugin_id
    ]
    for key in keys_to_remove:
        del _plugin_commands[key]


class PluginCommandMatch(TypedDict):
    """Result of matching a plugin command."""
    command: RegisteredPluginCommand
    args: str | None


def match_plugin_command(command_body: str) -> PluginCommandMatch | None:
    """Check if a command body matches a registered plugin command (mirrors TS matchPluginCommand).
    
    Note: If a command has acceptsArgs=False and the user provides arguments,
    the command will not match. This allows the message to fall through to
    built-in handlers or the agent.
    
    Args:
        command_body: Raw command text (e.g., "/mycommand arg1 arg2")
        
    Returns:
        Match result with command and args, or None if no match
    """
    trimmed = command_body.strip()
    if not trimmed.startswith("/"):
        return None
    
    space_index = trimmed.find(" ")
    command_name = trimmed if space_index == -1 else trimmed[:space_index]
    args = None if space_index == -1 else trimmed[space_index + 1:].strip()
    
    key = command_name.lower()
    command = _plugin_commands.get(key)
    
    if not command:
        return None
    
    if args and not command["accepts_args"]:
        return None
    
    return PluginCommandMatch(
        command=command,
        args=args,
    )


def _sanitize_args(args: str | None) -> str | None:
    """Sanitize command arguments to prevent injection attacks (mirrors TS sanitizeArgs).
    
    Removes control characters and enforces length limits.
    """
    if not args:
        return None
    
    if len(args) > MAX_ARGS_LENGTH:
        args = args[:MAX_ARGS_LENGTH]
    
    sanitized = ""
    for char in args:
        code = ord(char)
        is_control = (code <= 0x1F and code not in (0x09, 0x0A)) or code == 0x7F
        if not is_control:
            sanitized += char
    
    return sanitized


async def execute_plugin_command(
    command: RegisteredPluginCommand,
    args: str | None = None,
    sender_id: str | None = None,
    channel: str = "",
    channel_id: str | None = None,
    is_authorized_sender: bool = False,
    command_body: str = "",
    config: dict[str, Any] | None = None,
    from_: str | None = None,
    to: str | None = None,
    account_id: str | None = None,
    message_thread_id: str | None = None,
) -> PluginCommandResult:
    """Execute a plugin command handler (mirrors TS executePluginCommand).
    
    Note: Plugin authors should still validate and sanitize ctx.args for their
    specific use case. This function provides basic defense-in-depth sanitization.
    
    Args:
        command: Registered plugin command
        args: Command arguments
        sender_id: ID of the sender
        channel: Channel name (e.g., "telegram")
        channel_id: Channel-specific ID
        is_authorized_sender: Whether sender is authorized
        command_body: Full command body
        config: OpenClaw configuration
        from_: Message from address
        to: Message to address
        account_id: Account ID
        message_thread_id: Thread ID (for forums)
        
    Returns:
        Command result
    """
    global _registry_locked
    
    require_auth = command.get("require_auth", True)
    if require_auth and not is_authorized_sender:
        logger.debug(
            f"Plugin command /{command['name']} blocked: "
            f"unauthorized sender {sender_id or '<unknown>'}"
        )
        return PluginCommandResult(text="⚠️ This command requires authorization.")
    
    sanitized_args = _sanitize_args(args)
    
    ctx = PluginCommandContext(
        sender_id=sender_id,
        channel=channel,
        channel_id=channel_id,
        is_authorized_sender=is_authorized_sender,
        args=sanitized_args,
        command_body=command_body,
        config=config or {},
        from_=from_,
        to=to,
        account_id=account_id,
        message_thread_id=message_thread_id,
    )
    
    _registry_locked = True
    try:
        result = await command["handler"](ctx)
        logger.debug(
            f"Plugin command /{command['name']} executed successfully "
            f"for {sender_id or 'unknown'}"
        )
        return result
    except Exception as exc:
        logger.warning(f"Plugin command /{command['name']} error: {exc}")
        return PluginCommandResult(text="⚠️ Command failed. Please try again later.")
    finally:
        _registry_locked = False


def list_plugin_commands() -> list[dict[str, str]]:
    """List all registered plugin commands (mirrors TS listPluginCommands).
    
    Used for /help and /commands output.
    
    Returns:
        List of command info dicts with name, description, plugin_id
    """
    return [
        {
            "name": cmd["name"],
            "description": cmd["description"],
            "plugin_id": cmd["plugin_id"],
        }
        for cmd in _plugin_commands.values()
    ]


def get_plugin_command_specs() -> list[dict[str, str]]:
    """Get plugin command specs for native command registration (mirrors TS getPluginCommandSpecs).
    
    Used for registering plugin commands with Telegram, Slack, etc.
    
    Returns:
        List of command specs with name and description
    """
    return [
        {
            "name": cmd["name"],
            "description": cmd["description"],
        }
        for cmd in _plugin_commands.values()
    ]


__all__ = [
    "PluginCommandContext",
    "PluginCommandResult",
    "OpenClawPluginCommandDefinition",
    "RegisteredPluginCommand",
    "CommandRegistrationResult",
    "PluginCommandMatch",
    "RESERVED_COMMANDS",
    "MAX_ARGS_LENGTH",
    "validate_command_name",
    "register_plugin_command",
    "clear_plugin_commands",
    "clear_plugin_commands_for_plugin",
    "match_plugin_command",
    "execute_plugin_command",
    "list_plugin_commands",
    "get_plugin_command_specs",
]
