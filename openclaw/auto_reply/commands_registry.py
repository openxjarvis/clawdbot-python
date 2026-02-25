"""Command registry for managing commands.

Fully aligned with TypeScript openclaw/src/auto-reply/commands-registry.ts
"""
from __future__ import annotations

import logging
import re
from typing import Any, TypedDict

from openclaw.auto_reply.commands_registry_data import (
    ChatCommandDefinition,
    get_chat_commands,
    list_native_command_specs_for_config,
)

logger = logging.getLogger(__name__)


class CommandArgValues(TypedDict, total=False):
    """Parsed command argument values."""
    pass


class CommandArgs(TypedDict, total=False):
    """Parsed command arguments."""
    raw: str
    values: dict[str, Any]


class NativeCommandSpec(TypedDict):
    """Native command specification for provider registration."""
    name: str
    description: str
    acceptsArgs: bool
    args: list[Any] | None


class TextAliasSpec(TypedDict):
    """Text alias specification."""
    key: str
    canonical: str
    acceptsArgs: bool


class CommandDetection(TypedDict):
    """Command detection data."""
    exact: set[str]
    regex: re.Pattern[str]


_cached_text_alias_map: dict[str, TextAliasSpec] | None = None
_cached_text_alias_commands: list[ChatCommandDefinition] | None = None
_cached_detection: CommandDetection | None = None
_cached_detection_commands: list[ChatCommandDefinition] | None = None


def _get_text_alias_map() -> dict[str, TextAliasSpec]:
    """Build text alias map (mirrors TS getTextAliasMap)."""
    global _cached_text_alias_map, _cached_text_alias_commands
    
    commands = get_chat_commands()
    if _cached_text_alias_map and _cached_text_alias_commands is commands:
        return _cached_text_alias_map
    
    alias_map = {}
    for command in commands:
        canonical = command.text_aliases[0].strip() if command.text_aliases else f"/{command.key}"
        accepts_args = command.accepts_args
        
        for alias in command.text_aliases:
            normalized = alias.strip().lower()
            if not normalized:
                continue
            
            if normalized not in alias_map:
                alias_map[normalized] = TextAliasSpec(
                    key=command.key,
                    canonical=canonical,
                    acceptsArgs=accepts_args,
                )
    
    _cached_text_alias_map = alias_map
    _cached_text_alias_commands = commands
    return alias_map


def list_chat_commands(skill_commands: list[Any] | None = None) -> list[ChatCommandDefinition]:
    """List all chat commands (mirrors TS listChatCommands)."""
    commands = get_chat_commands()
    if not skill_commands:
        return commands.copy()

    result = commands.copy()
    for skill_cmd in skill_commands:
        if isinstance(skill_cmd, dict):
            name = skill_cmd.get("name") or skill_cmd.get("skill_name", "")
            description = skill_cmd.get("description", "")
        else:
            name = getattr(skill_cmd, "name", None) or getattr(skill_cmd, "skill_name", "")
            description = getattr(skill_cmd, "description", "")
        if name:
            from openclaw.auto_reply.commands_registry_data import _define_chat_command
            result.append(_define_chat_command(
                key=f"skill:{name}",
                native_name=name,
                description=description or f"Run {name} skill.",
                scope="both",
                category="skills",
            ))
    return result


def list_chat_commands_for_config(
    cfg: dict[str, Any],
    skill_commands: list[Any] | None = None,
) -> list[ChatCommandDefinition]:
    """List chat commands filtered by config (mirrors TS listChatCommandsForConfig)."""
    commands = get_chat_commands()

    enabled_commands = []
    for command in commands:
        if _is_command_enabled(cfg, command.key):
            enabled_commands.append(command)

    if not skill_commands:
        return enabled_commands

    for skill_cmd in skill_commands:
        if isinstance(skill_cmd, dict):
            name = skill_cmd.get("name") or skill_cmd.get("skill_name", "")
            description = skill_cmd.get("description", "")
        else:
            name = getattr(skill_cmd, "name", None) or getattr(skill_cmd, "skill_name", "")
            description = getattr(skill_cmd, "description", "")
        if name:
            from openclaw.auto_reply.commands_registry_data import _define_chat_command
            enabled_commands.append(_define_chat_command(
                key=f"skill:{name}",
                native_name=name,
                description=description or f"Run {name} skill.",
                scope="both",
                category="skills",
            ))
    return enabled_commands


def _is_command_enabled(cfg: dict[str, Any], command_key: str) -> bool:
    """Check if command is enabled in config (mirrors TS isCommandEnabled)."""
    commands_cfg = cfg.get("commands", {})
    
    if command_key == "config":
        return commands_cfg.get("config") is True
    if command_key == "debug":
        return commands_cfg.get("debug") is True
    if command_key == "bash":
        return commands_cfg.get("bash") is True
    
    return True


_NATIVE_NAME_OVERRIDES: dict[str, dict[str, str]] = {
    "discord": {
        "tts": "voice",
    },
}


def find_command_by_native_name(
    name: str,
    provider: str | None = None,
) -> ChatCommandDefinition | None:
    """Find command by native name (mirrors TS findCommandByNativeName)."""
    normalized = name.strip().lower()

    for command in get_chat_commands():
        if command.scope == "text":
            continue

        native_name = command.native_name
        if provider and command.key in _NATIVE_NAME_OVERRIDES.get(provider, {}):
            native_name = _NATIVE_NAME_OVERRIDES[provider][command.key]

        if native_name and native_name.lower() == normalized:
            return command

    return None


def _get_attr(obj: Any, key: str, default: Any = None) -> Any:
    """Get attribute from object or dict."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def parse_command_args(
    command: Any,
    raw: str | None = None,
) -> CommandArgs | None:
    """Parse command arguments (mirrors TS parseCommandArgs).
    
    Accepts both ChatCommandDefinition objects and plain dicts.
    """
    trimmed = raw.strip() if raw else ""

    cmd_args = _get_attr(command, "args", [])
    args_parsing = _get_attr(command, "args_parsing", "none")

    if not cmd_args or args_parsing == "none":
        return CommandArgs(raw=trimmed, values={})

    return CommandArgs(
        raw=trimmed,
        values=_parse_positional_args(cmd_args, trimmed),
    )


def _parse_positional_args(definitions: list[Any], raw: str) -> dict[str, Any]:
    """Parse positional arguments (mirrors TS parsePositionalArgs)."""
    values = {}
    trimmed = raw.strip()
    if not trimmed:
        return values

    tokens = [t for t in trimmed.split() if t]
    index = 0

    for definition in definitions:
        if index >= len(tokens):
            break

        capture = _get_attr(definition, "capture_remaining", False)
        name = _get_attr(definition, "name", "")

        if capture:
            values[name] = " ".join(tokens[index:])
            index = len(tokens)
            break

        values[name] = tokens[index]
        index += 1

    return values


def normalize_command_body(raw: str, bot_username: str | None = None) -> str:
    """Normalize command body (mirrors TS normalizeCommandBody)."""
    trimmed = raw.strip()
    if not trimmed.startswith("/"):
        return trimmed
    
    # Extract first line
    newline_idx = trimmed.find("\n")
    single_line = trimmed if newline_idx == -1 else trimmed[:newline_idx].strip()
    
    # Handle colon syntax: /command: args -> /command args
    colon_match = re.match(r"^/([^\s:]+)\s*:(.*)$", single_line)
    if colon_match:
        command, rest = colon_match.groups()
        normalized_rest = rest.lstrip()
        normalized = f"/{command} {normalized_rest}" if normalized_rest else f"/{command}"
    else:
        normalized = single_line
    
    # Strip bot username mentions: /command@botname -> /command
    normalized_bot_username = bot_username.strip().lower() if bot_username else None
    if normalized_bot_username:
        mention_match = re.match(r"^/([^\s@]+)@([^\s]+)(.*)$", normalized)
        if mention_match and mention_match.group(2).lower() == normalized_bot_username:
            normalized = f"/{mention_match.group(1)}{mention_match.group(3) or ''}"
    
    # Resolve text alias
    lowered = normalized.lower()
    text_alias_map = _get_text_alias_map()
    
    exact = text_alias_map.get(lowered)
    if exact:
        return exact["canonical"]
    
    # Try token-based matching
    token_match = re.match(r"^/([^\s]+)(?:\s+([\s\S]+))?$", normalized)
    if not token_match:
        return normalized
    
    token, rest = token_match.group(1), token_match.group(2)
    token_key = f"/{token.lower()}"
    token_spec = text_alias_map.get(token_key)
    
    if not token_spec:
        return normalized
    
    if rest and not token_spec["acceptsArgs"]:
        return normalized
    
    normalized_rest = rest.lstrip() if rest else None
    return f"{token_spec['canonical']} {normalized_rest}" if normalized_rest else token_spec["canonical"]


def is_command_message(raw: str) -> bool:
    """Check if message is a command (mirrors TS isCommandMessage)."""
    trimmed = normalize_command_body(raw)
    return trimmed.startswith("/")


def get_command_detection(cfg: dict[str, Any] | None = None) -> CommandDetection:
    """Get command detection data (mirrors TS getCommandDetection)."""
    global _cached_detection, _cached_detection_commands
    
    commands = get_chat_commands()
    if _cached_detection and _cached_detection_commands is commands:
        return _cached_detection
    
    exact = set()
    patterns = []
    
    for cmd in commands:
        for alias in cmd.text_aliases:
            normalized = alias.strip().lower()
            if not normalized:
                continue
            
            exact.add(normalized)
            escaped = re.escape(normalized)
            
            if cmd.accepts_args:
                patterns.append(f"{escaped}(?:\\s+.+|\\s*:\\s*.*)?")
            else:
                patterns.append(f"{escaped}(?:\\s*:\\s*)?")
    
    regex_pattern = f"^(?:{'|'.join(patterns)})$" if patterns else "$^"
    
    _cached_detection = CommandDetection(
        exact=exact,
        regex=re.compile(regex_pattern, re.IGNORECASE),
    )
    _cached_detection_commands = commands
    return _cached_detection


def maybe_resolve_text_alias(raw: str, cfg: dict[str, Any] | None = None) -> str | None:
    """Resolve text alias if message is a command (mirrors TS maybeResolveTextAlias)."""
    trimmed = normalize_command_body(raw).strip()
    if not trimmed.startswith("/"):
        return None
    
    detection = get_command_detection(cfg)
    normalized = trimmed.lower()
    
    if normalized in detection["exact"]:
        return normalized
    
    if not detection["regex"].match(normalized):
        return None
    
    return normalized


def resolve_text_command(
    raw: str,
    cfg: dict[str, Any] | None = None,
) -> tuple[ChatCommandDefinition | None, str | None]:
    """Resolve text command from raw input (mirrors TS resolveTextCommand)."""
    alias = maybe_resolve_text_alias(raw, cfg)
    if not alias:
        return None, None
    
    # Parse command and args
    match = re.match(r"^(/[^\s]+)(?:\s+([\s\S]+))?$", alias)
    if not match:
        return None, None
    
    command_part, args_part = match.group(1), match.group(2)
    
    # Find command by text alias
    text_alias_map = _get_text_alias_map()
    spec = text_alias_map.get(command_part.lower())
    
    if not spec:
        return None, None
    
    # Find full command definition
    command = next((c for c in get_chat_commands() if c.key == spec["key"]), None)
    
    return command, args_part


__all__ = [
    "CommandArgs",
    "CommandArgValues",
    "NativeCommandSpec",
    "CommandDetection",
    "list_chat_commands",
    "list_chat_commands_for_config",
    "list_native_command_specs_for_config",
    "find_command_by_native_name",
    "parse_command_args",
    "normalize_command_body",
    "is_command_message",
    "get_command_detection",
    "maybe_resolve_text_alias",
    "resolve_text_command",
]
