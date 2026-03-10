"""Interactive CLI prompter using questionary
Provides a unified interface for CLI interactions, similar to TypeScript's @clack/prompts

Uses nest_asyncio to allow questionary to work in async contexts.
"""
from __future__ import annotations

import sys
from typing import Any, Literal, TypeVar

import questionary
from questionary import Choice

T = TypeVar("T")


class WizardCancelledError(Exception):
    """Raised when user cancels the wizard with Ctrl+C"""
    pass


def select(
    message: str,
    choices: list[dict[str, Any]],
    default: str | None = None,
) -> str:
    """Single-select prompt
    
    Args:
        message: Prompt message
        choices: List of choices with 'name', 'value', and optional 'description'
        default: Default value
        
    Returns:
        Selected value
        
    Raises:
        WizardCancelledError: If user cancels with Ctrl+C
    """
    try:
        qchoices = [
            Choice(
                title=c.get("name", c.get("label", str(c.get("value")))),
                value=c.get("value"),
                description=c.get("description", c.get("hint")),
            )
            for c in choices
        ]
        
        result = questionary.select(
            message,
            choices=qchoices,
            default=default,
            use_shortcuts=True,
            use_arrow_keys=True,
        ).ask()
        
        if result is None:
            raise WizardCancelledError("User cancelled")
        
        return result
    except KeyboardInterrupt:
        raise WizardCancelledError("User cancelled")


def checkbox(
    message: str,
    choices: list[dict[str, Any]],
    initial_values: list[str] | None = None,
) -> list[str]:
    """Checkbox multi-select prompt (alias for multiselect, uses questionary.checkbox)
    
    Args:
        message: Prompt message
        choices: List of choices with 'name', 'value', and optional 'description'
        initial_values: Pre-selected values
        
    Returns:
        List of selected values
        
    Raises:
        WizardCancelledError: If user cancels with Ctrl+C
    """
    return multiselect(message, choices, searchable=False, initial_values=initial_values)


def multiselect(
    message: str,
    choices: list[dict[str, Any]],
    searchable: bool = False,
    initial_values: list[str] | None = None,
) -> list[str]:
    """Multi-select prompt with checkbox interface (uses questionary.checkbox)
    
    Args:
        message: Prompt message
        choices: List of choices with 'name', 'value', and optional 'description'
        searchable: If True, enables fuzzy search (questionary limitation: always enabled in checkbox)
        initial_values: Pre-selected values
        
    Returns:
        List of selected values
        
    Raises:
        WizardCancelledError: If user cancels with Ctrl+C
    """
    try:
        qchoices = [
            Choice(
                title=c.get("name", c.get("label", str(c.get("value")))),
                value=c.get("value"),
                description=c.get("description", c.get("hint")),
                checked=(c.get("value") in (initial_values or [])),
            )
            for c in choices
        ]
        
        result = questionary.checkbox(
            message,
            choices=qchoices,
            use_shortcuts=True,
        ).ask()
        
        if result is None:
            raise WizardCancelledError("User cancelled")
        
        return result
    except KeyboardInterrupt:
        raise WizardCancelledError("User cancelled")


def confirm(message: str, default: bool = True) -> bool:
    """Yes/No confirmation prompt
    
    Args:
        message: Prompt message
        default: Default value (True for Yes, False for No)
        
    Returns:
        True if Yes, False if No
        
    Raises:
        WizardCancelledError: If user cancels with Ctrl+C
    """
    try:
        result = questionary.confirm(
            message,
            default=default,
            auto_enter=False,
        ).ask()
        
        if result is None:
            raise WizardCancelledError("User cancelled")
        
        return result
    except KeyboardInterrupt:
        raise WizardCancelledError("User cancelled")


def text(
    message: str,
    default: str = "",
    validate: Any | None = None,
    multiline: bool = False,
) -> str:
    """Text input prompt
    
    Args:
        message: Prompt message
        default: Default value
        validate: Validation function or regex
        multiline: Enable multiline input
        
    Returns:
        User input string
        
    Raises:
        WizardCancelledError: If user cancels with Ctrl+C
    """
    try:
        result = questionary.text(
            message,
            default=default,
            validate=validate,
            multiline=multiline,
        ).ask()
        
        if result is None:
            raise WizardCancelledError("User cancelled")
        
        return result
    except KeyboardInterrupt:
        raise WizardCancelledError("User cancelled")


def password(message: str, validate: Any | None = None) -> str:
    """Password input prompt (hidden input)
    
    Args:
        message: Prompt message
        validate: Validation function or regex
        
    Returns:
        User input string
        
    Raises:
        WizardCancelledError: If user cancels with Ctrl+C
    """
    try:
        result = questionary.password(
            message,
            validate=validate,
        ).ask()
        
        if result is None:
            raise WizardCancelledError("User cancelled")
        
        return result
    except KeyboardInterrupt:
        raise WizardCancelledError("User cancelled")


def note(message: str, title: str | None = None) -> None:
    """Display an informational note
    
    Args:
        message: Note content
        title: Optional title
    """
    if title:
        print(f"\n{title}")
        print("-" * len(title))
    print(message)


def autocomplete(
    message: str,
    choices: list[str],
    default: str = "",
    meta_information: dict[str, str] | None = None,
) -> str:
    """Autocomplete prompt with fuzzy search
    
    Args:
        message: Prompt message
        choices: List of choice strings
        default: Default value
        meta_information: Optional dict mapping choices to descriptions
        
    Returns:
        Selected choice
        
    Raises:
        WizardCancelledError: If user cancels with Ctrl+C
    """
    try:
        result = questionary.autocomplete(
            message,
            choices=choices,
            default=default,
            meta_information=meta_information or {},
        ).ask()
        
        if result is None:
            raise WizardCancelledError("User cancelled")
        
        return result
    except KeyboardInterrupt:
        raise WizardCancelledError("User cancelled")


__all__ = [
    "select",
    "multiselect",
    "checkbox",
    "confirm",
    "text",
    "password",
    "note",
    "autocomplete",
    "WizardCancelledError",
]
