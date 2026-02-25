"""Telegram command utilities.

Telegram-specific command normalization, custom command resolution, and sync.
Fully aligned with TypeScript openclaw/src/config/telegram-custom-commands.ts
and openclaw/src/telegram/bot-native-commands.ts
"""
from __future__ import annotations

import logging
import re
from typing import Any, TypedDict

logger = logging.getLogger(__name__)


TELEGRAM_COMMAND_NAME_PATTERN = re.compile(r"^[a-z0-9_]{1,32}$")


class TelegramCustomCommandInput(TypedDict, total=False):
    """Telegram custom command input."""
    command: str | None
    description: str | None


class TelegramCustomCommandIssue(TypedDict):
    """Telegram custom command validation issue."""
    index: int
    field: str
    message: str


class TelegramCustomCommand(TypedDict):
    """Resolved Telegram custom command."""
    command: str
    description: str


class TelegramCustomCommandsResult(TypedDict):
    """Result of custom command resolution."""
    commands: list[TelegramCustomCommand]
    issues: list[TelegramCustomCommandIssue]


def normalize_telegram_command_name(value: str) -> str:
    """Normalize Telegram command name (mirrors TS normalizeTelegramCommandName)."""
    trimmed = value.strip()
    if not trimmed:
        return ""
    
    without_slash = trimmed[1:] if trimmed.startswith("/") else trimmed
    return without_slash.strip().lower().replace("-", "_")


def normalize_telegram_command_description(value: str) -> str:
    """Normalize Telegram command description (mirrors TS normalizeTelegramCommandDescription)."""
    return value.strip()


def resolve_telegram_custom_commands(
    commands: list[TelegramCustomCommandInput] | None = None,
    reserved_commands: set[str] | None = None,
    check_reserved: bool = True,
    check_duplicates: bool = True,
) -> TelegramCustomCommandsResult:
    """Resolve and validate Telegram custom commands (mirrors TS resolveTelegramCustomCommands).
    
    Args:
        commands: List of custom command inputs
        reserved_commands: Set of reserved command names
        check_reserved: Whether to check for conflicts with reserved names
        check_duplicates: Whether to check for duplicate commands
        
    Returns:
        Dict with resolved commands and validation issues
    """
    entries = commands if isinstance(commands, list) else []
    reserved = reserved_commands or set()
    seen = set()
    resolved: list[TelegramCustomCommand] = []
    issues: list[TelegramCustomCommandIssue] = []
    
    for index, entry in enumerate(entries):
        normalized = normalize_telegram_command_name(str(entry.get("command", "")))
        
        if not normalized:
            issues.append(
                TelegramCustomCommandIssue(
                    index=index,
                    field="command",
                    message="Telegram custom command is missing a command name.",
                )
            )
            continue
        
        if not TELEGRAM_COMMAND_NAME_PATTERN.match(normalized):
            issues.append(
                TelegramCustomCommandIssue(
                    index=index,
                    field="command",
                    message=f"Telegram custom command \"/{normalized}\" is invalid (use a-z, 0-9, underscore; max 32 chars).",
                )
            )
            continue
        
        if check_reserved and normalized in reserved:
            issues.append(
                TelegramCustomCommandIssue(
                    index=index,
                    field="command",
                    message=f"Telegram custom command \"/{normalized}\" conflicts with a native command.",
                )
            )
            continue
        
        if check_duplicates and normalized in seen:
            issues.append(
                TelegramCustomCommandIssue(
                    index=index,
                    field="command",
                    message=f"Telegram custom command \"/{normalized}\" is duplicated.",
                )
            )
            continue
        
        description = normalize_telegram_command_description(str(entry.get("description", "")))
        if not description:
            issues.append(
                TelegramCustomCommandIssue(
                    index=index,
                    field="description",
                    message=f"Telegram custom command \"/{normalized}\" is missing a description.",
                )
            )
            continue
        
        if check_duplicates:
            seen.add(normalized)
        
        resolved.append(
            TelegramCustomCommand(
                command=normalized,
                description=description,
            )
        )
    
    return TelegramCustomCommandsResult(
        commands=resolved,
        issues=issues,
    )


def build_capped_telegram_commands(
    commands: list[dict[str, str]],
    max_commands: int = 100,
) -> list[dict[str, str]]:
    """Cap Telegram commands list (mirrors TS buildCappedTelegramCommands).
    
    Telegram has a limit of 100 commands per bot.
    
    Args:
        commands: List of command dicts with 'command' and 'description'
        max_commands: Maximum number of commands (default: 100)
        
    Returns:
        Capped list of commands
    """
    if len(commands) <= max_commands:
        return commands
    
    logger.warning(
        f"Telegram command count ({len(commands)}) exceeds limit ({max_commands}). "
        f"Truncating to first {max_commands} commands."
    )
    
    return commands[:max_commands]


async def sync_telegram_commands(
    bot: Any,
    cfg: dict[str, Any],
    account_id: str,
    skill_commands: list[Any] | None = None,
) -> bool:
    """Sync commands with Telegram API (mirrors TS syncTelegramCommands).
    
    Builds the complete command list and registers with Telegram.
    
    Args:
        bot: Telegram bot instance
        cfg: OpenClaw configuration
        account_id: Telegram account ID
        skill_commands: Optional skill command specs
        
    Returns:
        True if sync succeeded
    """
    try:
        from openclaw.auto_reply.commands_registry import list_native_command_specs_for_config
        
        # Get native commands
        native_specs = list_native_command_specs_for_config(cfg, skill_commands)
        
        # Build command list
        commands = []
        for spec in native_specs:
            commands.append({
                "command": spec["name"],
                "description": spec["description"][:256],
            })
        
        # Add custom commands (support both camelCase and snake_case config keys)
        account_cfg = cfg.get("channels", {}).get("telegram", {}).get("accounts", {}).get(account_id, {})
        custom_commands_raw = account_cfg.get("customCommands") or account_cfg.get("custom_commands")
        custom_result = resolve_telegram_custom_commands(
            commands=custom_commands_raw,
            reserved_commands={spec["name"] for spec in native_specs},
        )
        
        for custom_cmd in custom_result["commands"]:
            commands.append({
                "command": custom_cmd["command"],
                "description": custom_cmd["description"][:256],
            })
        
        # Log validation issues
        for issue in custom_result["issues"]:
            logger.warning(f"Custom command issue at index {issue['index']}: {issue['message']}")
        
        # Cap to Telegram limit
        capped_commands = build_capped_telegram_commands(commands)
        
        # Register with Telegram
        await bot.set_my_commands(capped_commands)
        
        logger.info(f"Synced {len(capped_commands)} commands with Telegram")
        return True
    
    except Exception as exc:
        logger.error(f"Failed to sync Telegram commands: {exc}")
        return False


__all__ = [
    "TELEGRAM_COMMAND_NAME_PATTERN",
    "TelegramCustomCommandInput",
    "TelegramCustomCommandIssue",
    "TelegramCustomCommand",
    "TelegramCustomCommandsResult",
    "normalize_telegram_command_name",
    "normalize_telegram_command_description",
    "resolve_telegram_custom_commands",
    "build_capped_telegram_commands",
    "sync_telegram_commands",
]
