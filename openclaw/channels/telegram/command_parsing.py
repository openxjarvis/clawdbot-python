"""Telegram command parsing utilities.

Fully aligned with TypeScript openclaw/src/auto-reply/commands-registry.ts parseCommandArgs
"""
from __future__ import annotations

import logging
from typing import Any, TypedDict

logger = logging.getLogger(__name__)


class CommandArgs(TypedDict, total=False):
    """Parsed command arguments."""
    raw: str
    values: dict[str, Any]


def parse_positional_args(
    definitions: list[dict[str, Any]],
    raw: str,
) -> dict[str, Any]:
    """Parse positional arguments (mirrors TS parsePositionalArgs).
    
    Args:
        definitions: List of argument definitions
        raw: Raw argument string
        
    Returns:
        Dictionary of argument values
    """
    values: dict[str, Any] = {}
    trimmed = raw.strip()
    
    if not trimmed:
        return values
    
    tokens = [t for t in trimmed.split() if t]
    index = 0
    
    for definition in definitions:
        if index >= len(tokens):
            break
        
        # Check for captureRemaining flag
        if definition.get("capture_remaining") or definition.get("captureRemaining"):
            values[definition["name"]] = " ".join(tokens[index:])
            index = len(tokens)
            break
        
        values[definition["name"]] = tokens[index]
        index += 1
    
    return values


def parse_command_args(
    command: dict[str, Any],
    raw: str | None = None,
) -> CommandArgs | None:
    """Parse command arguments (mirrors TS parseCommandArgs).
    
    Args:
        command: Command definition
        raw: Raw argument string
        
    Returns:
        Parsed command args or None
    """
    trimmed = raw.strip() if raw else ""
    
    if not trimmed:
        return None
    
    # If no args or parsing mode is "none", just return raw
    if not command.get("args") or command.get("args_parsing") == "none":
        return CommandArgs(raw=trimmed)
    
    # Parse positional args
    return CommandArgs(
        raw=trimmed,
        values=parse_positional_args(command["args"], trimmed)
    )


def serialize_command_args(
    command: dict[str, Any],
    args: CommandArgs | None = None,
) -> str | None:
    """Serialize command arguments back to string (mirrors TS serializeCommandArgs).
    
    Args:
        command: Command definition
        args: Parsed command arguments
        
    Returns:
        Serialized argument string
    """
    if not args:
        return None
    
    # Prefer raw
    raw = args.get("raw", "").strip()
    if raw:
        return raw
    
    # Try to serialize from values
    values = args.get("values")
    if not values or not command.get("args"):
        return None
    
    # Use formatArgs if available
    format_args = command.get("format_args") or command.get("formatArgs")
    if format_args and callable(format_args):
        return format_args(values)
    
    # Default: format positional args
    return format_positional_args(command["args"], values)


def format_positional_args(
    definitions: list[dict[str, Any]],
    values: dict[str, Any],
) -> str | None:
    """Format positional arguments (mirrors TS formatPositionalArgs).
    
    Args:
        definitions: List of argument definitions
        values: Argument values
        
    Returns:
        Formatted argument string
    """
    parts: list[str] = []
    
    for definition in definitions:
        value = values.get(definition["name"])
        if value is None:
            continue
        
        if isinstance(value, str):
            rendered = value.strip()
        else:
            rendered = str(value)
        
        if not rendered:
            continue
        
        parts.append(rendered)
    
    return " ".join(parts) if parts else None


def build_command_text_from_args(
    command: dict[str, Any],
    args: CommandArgs | None = None,
) -> str:
    """Build command text from args (mirrors TS buildCommandTextFromArgs).
    
    Args:
        command: Command definition
        args: Parsed command arguments
        
    Returns:
        Full command text (e.g., "/model gpt-4")
    """
    command_name = command.get("native_name") or command.get("key", "")
    serialized = serialize_command_args(command, args)
    
    if serialized:
        return f"/{command_name} {serialized}"
    else:
        return f"/{command_name}"


__all__ = [
    "CommandArgs",
    "parse_positional_args",
    "parse_command_args",
    "serialize_command_args",
    "format_positional_args",
    "build_command_text_from_args",
]
