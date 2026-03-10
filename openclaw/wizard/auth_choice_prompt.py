"""Auth choice grouped prompt UI - aligned with TypeScript auth-choice-prompt.ts

Provides two-level grouped selection UI for provider authentication.
Mirrors openclaw/src/commands/auth-choice-prompt.ts
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .auth_choice_types import AuthChoice

from .auth_choice_groups import (
    AUTH_CHOICE_GROUP_DEFS,
    PROVIDER_AUTH_CHOICE_OPTION_HINTS,
    PROVIDER_AUTH_CHOICE_OPTION_LABELS,
    build_auth_choice_options,
)


BACK_VALUE = "__back"


async def prompt_auth_choice_grouped(include_skip: bool = True) -> AuthChoice:
    """Prompt for auth choice using grouped two-level selection
    
    Aligns with TS promptAuthChoiceGrouped:
    - Level 1: Select provider group (OpenAI, Anthropic, MiniMax, etc.)
    - Level 2: Select auth method within group (if multiple options)
    - Supports "Back" navigation from level 2 to level 1
    
    Args:
        include_skip: Whether to include "Skip for now" option
        
    Returns:
        Selected AuthChoice
    """
    from . import prompter
    
    groups = AUTH_CHOICE_GROUP_DEFS.copy()
    
    while True:
        # Level 1: Select provider group
        print("\n" + "=" * 80)
        print("Model/Auth Provider Selection")
        print("=" * 80)
        print("\nSelect your LLM provider:")
        
        # Build choices for questionary
        provider_choices = [
            {
                "name": f"{group.label}" + (f" - {group.hint}" if group.hint else ""),
                "value": idx,
            }
            for idx, group in enumerate(groups)
        ]
        
        if include_skip:
            provider_choices.append({"name": "Skip for now", "value": "skip"})
        
        # Get user choice with questionary
        try:
            choice_result = prompter.select(
                "Select provider:",
                choices=provider_choices,
            )
            
            # Handle skip
            if choice_result == "skip":
                return "skip"
            
            choice_idx = choice_result
            
        except prompter.WizardCancelledError:
            if include_skip:
                return "skip"
            else:
                choice_idx = 0  # Default to first
        
        selected_group = groups[choice_idx]
        
        # If group has only one choice, return it directly
        if len(selected_group.choices) == 1:
            return selected_group.choices[0]
        
        # Level 2: Select auth method within group
        options = build_auth_choice_options(selected_group)
        
        while True:
            print("\n" + "-" * 80)
            print(f"{selected_group.label} Auth Method")
            print("-" * 80)
            
            # Build choices for auth methods
            method_choices = [
                {
                    "name": option.label + (f" - {option.hint}" if option.hint else ""),
                    "value": option.value,
                }
                for option in options
            ]
            method_choices.append({"name": "← Back", "value": BACK_VALUE})
            
            # Get user choice with questionary
            try:
                selected_auth = prompter.select(
                    "Select auth method:",
                    choices=method_choices,
                )
                
                # Handle back
                if selected_auth == BACK_VALUE:
                    break  # Go back to level 1
                
                # Return selected auth choice
                return selected_auth
                
            except prompter.WizardCancelledError:
                break  # Go back to level 1


def format_auth_choice_label(auth_choice: AuthChoice) -> str:
    """Format auth choice for display
    
    Args:
        auth_choice: Authentication choice
        
    Returns:
        Formatted label
    """
    return PROVIDER_AUTH_CHOICE_OPTION_LABELS.get(auth_choice, auth_choice)


def format_auth_choice_hint(auth_choice: AuthChoice) -> str | None:
    """Get hint text for auth choice
    
    Args:
        auth_choice: Authentication choice
        
    Returns:
        Hint text or None
    """
    return PROVIDER_AUTH_CHOICE_OPTION_HINTS.get(auth_choice)
