"""Moonshot AI (Kimi) auth handler

Handles Moonshot AI authentication (.ai, .cn, Kimi Code).
Mirrors openclaw/src/commands/auth-choice.moonshot.ts
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..auth_choice_types import AuthChoice
    from ...config.schema import ClawdbotConfig

from .base import ApplyAuthChoiceResult


async def apply_auth_choice_moonshot(
    auth_choice: AuthChoice,
    config: ClawdbotConfig,
    set_default_model: bool = True,
    agent_dir: str | None = None,
    agent_id: str | None = None,
    opts: dict | None = None,
) -> ApplyAuthChoiceResult | None:
    """Handle Moonshot AI (Kimi) authentication
    
    Supports:
    - moonshot-api-key: Kimi API key (.ai)
    - moonshot-api-key-cn: Kimi API key (.cn)
    - kimi-code-api-key: Kimi Code API key (subscription)
    
    Args:
        auth_choice: Selected authentication choice
        config: Current configuration
        set_default_model: Whether to set default model
        agent_dir: Optional agent directory
        agent_id: Optional agent ID
        opts: Optional parameters
        
    Returns:
        ApplyAuthChoiceResult if handled, None otherwise
    """
    if auth_choice not in ("moonshot-api-key", "moonshot-api-key-cn", "kimi-code-api-key"):
        return None
    
    # Check opts first
    api_key = None
    if opts and "moonshotApiKey" in opts:
        api_key = opts["moonshotApiKey"]
    elif opts and "kimiCodeApiKey" in opts and auth_choice == "kimi-code-api-key":
        api_key = opts["kimiCodeApiKey"]
    
    # Check environment
    if not api_key:
        env_var = "KIMI_CODE_API_KEY" if auth_choice == "kimi-code-api-key" else "MOONSHOT_API_KEY"
        api_key = os.getenv(env_var)
        if api_key:
            use_env = input(f"\n✓ Found {env_var} in environment. Use it? [Y/n]: ").strip().lower()
            if use_env == "n":
                api_key = None
    
    # Prompt for API key
    if not api_key:
        if auth_choice == "kimi-code-api-key":
            print("\nKimi Code API Key Configuration")
            print("-" * 60)
            print("Get your API key from: https://kimi.moonshot.cn/subscription")
            api_key = input("\nEnter your Kimi Code API key: ").strip()
        elif auth_choice == "moonshot-api-key-cn":
            print("\nKimi API Key Configuration (.cn)")
            print("-" * 60)
            print("Get your API key from: https://platform.moonshot.cn/console/api-keys")
            api_key = input("\nEnter your Kimi API key: ").strip()
        else:
            print("\nKimi API Key Configuration (.ai)")
            print("-" * 60)
            print("Get your API key from: https://platform.moonshot.ai/console/api-keys")
            api_key = input("\nEnter your Kimi API key: ").strip()
        
        if not api_key:
            raise ValueError("Kimi API key is required")
    
    # Save to auth-profiles.json
    try:
        from ...config.auth_profiles import set_api_key
        profile_id = "kimi-code" if auth_choice == "kimi-code-api-key" else "moonshot"
        set_api_key(profile_id, api_key)
        print(f"✓ Kimi API key saved")
    except Exception as e:
        print(f"Warning: Could not save to auth-profiles.json: {e}")
    
    # Model selection moved to main onboarding flow (prompt_default_model)
    # Just ensure the config structures exist
    if set_default_model:
        from ...config.schema import AgentsConfig, AgentDefaults, AgentConfig
        
        if not config.agents:
            config.agents = AgentsConfig()
        if not config.agents.defaults:
            config.agents.defaults = AgentDefaults()
        if not config.agent:
            config.agent = AgentConfig()
    
    return ApplyAuthChoiceResult(config=config)
