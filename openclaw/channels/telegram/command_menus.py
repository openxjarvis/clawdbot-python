"""Telegram command menu and inline keyboard utilities.

Fully aligned with TypeScript openclaw/src/auto-reply/commands-registry.ts resolveCommandArgMenu
and openclaw/src/telegram/bot-native-commands.ts inline keyboard building
"""
from __future__ import annotations

import logging
from typing import Any, TypedDict

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)


class ResolvedCommandArgChoice(TypedDict):
    """Resolved command argument choice."""
    label: str
    value: str


class CommandArgMenuResult(TypedDict):
    """Result of menu resolution."""
    arg: dict[str, Any]
    choices: list[ResolvedCommandArgChoice]
    title: str | None


def resolve_command_arg_choices(
    command: dict[str, Any],
    arg: dict[str, Any],
    cfg: dict[str, Any] | None = None,
) -> list[ResolvedCommandArgChoice]:
    """Resolve command argument choices (mirrors TS resolveCommandArgChoices).
    
    Args:
        command: Command definition
        arg: Argument definition
        cfg: OpenClaw configuration
        
    Returns:
        List of resolved choices
    """
    choices = arg.get("choices")
    if not choices:
        return []
    
    # Static choices (list or dict)
    if isinstance(choices, list):
        return [
            ResolvedCommandArgChoice(label=str(c), value=str(c))
            for c in choices
        ]
    elif isinstance(choices, dict):
        return [
            ResolvedCommandArgChoice(label=label, value=value)
            for value, label in choices.items()
        ]
    
    # Dynamic choices (function)
    elif callable(choices):
        try:
            result = choices({"cfg": cfg})
            if isinstance(result, list):
                return [
                    ResolvedCommandArgChoice(label=str(c), value=str(c))
                    for c in result
                ]
            elif isinstance(result, dict):
                return [
                    ResolvedCommandArgChoice(label=label, value=value)
                    for value, label in result.items()
                ]
        except Exception as exc:
            logger.warning(f"Failed to resolve dynamic choices: {exc}")
            return []
    
    return []


def resolve_command_arg_menu(
    command: dict[str, Any],
    args: dict[str, Any] | None = None,
    cfg: dict[str, Any] | None = None,
) -> CommandArgMenuResult | None:
    """Resolve command argument menu (mirrors TS resolveCommandArgMenu).
    
    Args:
        command: Command definition
        args: Parsed command arguments
        cfg: OpenClaw configuration
        
    Returns:
        Menu result or None if no menu needed
    """
    if not command.get("args") or not command.get("args_menu"):
        return None
    
    if command.get("args_parsing") == "none":
        return None
    
    arg_spec = command["args_menu"]
    
    # Resolve arg name
    if arg_spec == "auto":
        # Find first arg with choices
        arg_name = None
        for arg_def in command["args"]:
            if resolve_command_arg_choices(command, arg_def, cfg):
                arg_name = arg_def["name"]
                break
    elif isinstance(arg_spec, dict):
        arg_name = arg_spec.get("arg")
    else:
        return None
    
    if not arg_name:
        return None
    
    # Check if arg value already provided
    if args and args.get("values") and args["values"].get(arg_name) is not None:
        return None
    
    # If we have raw text but no parsed values, assume user provided something
    if args and args.get("raw") and not args.get("values"):
        return None
    
    # Find arg definition
    arg = None
    for arg_def in command["args"]:
        if arg_def["name"] == arg_name:
            arg = arg_def
            break
    
    if not arg:
        return None
    
    # Resolve choices
    choices = resolve_command_arg_choices(command, arg, cfg)
    if not choices:
        return None
    
    title = None
    if isinstance(arg_spec, dict):
        title = arg_spec.get("title")
    
    return CommandArgMenuResult(
        arg=arg,
        choices=choices,
        title=title,
    )


def build_inline_keyboard_for_menu(
    menu: CommandArgMenuResult,
    command: dict[str, Any],
) -> InlineKeyboardMarkup:
    """Build inline keyboard from menu (mirrors TS inline keyboard building).
    
    Args:
        menu: Resolved menu
        command: Command definition
        
    Returns:
        Inline keyboard markup
    """
    from .command_parsing import build_command_text_from_args
    
    # Build keyboard rows (2 buttons per row)
    rows: list[list[InlineKeyboardButton]] = []
    
    for i in range(0, len(menu["choices"]), 2):
        slice_choices = menu["choices"][i:i+2]
        row = []
        
        for choice in slice_choices:
            # Build callback data as command text with this choice
            callback_data = build_command_text_from_args(
                command,
                {"values": {menu["arg"]["name"]: choice["value"]}}
            )
            
            button = InlineKeyboardButton(
                text=choice["label"],
                callback_data=callback_data
            )
            row.append(button)
        
        rows.append(row)
    
    return InlineKeyboardMarkup(rows)


__all__ = [
    "ResolvedCommandArgChoice",
    "CommandArgMenuResult",
    "resolve_command_arg_choices",
    "resolve_command_arg_menu",
    "build_inline_keyboard_for_menu",
]
