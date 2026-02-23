"""
Authentication configuration for onboarding wizard
Handles API key collection, OAuth flows, and auth profile management
"""
from __future__ import annotations


import os
from pathlib import Path


def get_provider_help_text(provider: str) -> str | None:
    """Get help text for obtaining API keys for different providers"""
    help_texts = {
        "anthropic": "Get your key from: https://console.anthropic.com/settings/keys",
        "openai": "Get your key from: https://platform.openai.com/api-keys",
        "gemini": "Get your key from: https://makersuite.google.com/app/apikey",
        "google": "Get your key from: https://makersuite.google.com/app/apikey",
        "openrouter": "Get your key from: https://openrouter.ai/keys",
    }
    return help_texts.get(provider.lower())


def prompt_api_key_simple(provider: str) -> str:
    """Prompt for API key with provider-specific help (simple version)"""
    help_text = get_provider_help_text(provider)
    
    if help_text:
        print(f"\n{help_text}\n")
    
    api_key = input(f"Enter your {provider.title()} API key: ").strip()
    
    if not api_key:
        raise ValueError("API key cannot be empty")
    
    return api_key


def check_env_api_key(provider: str) -> str | None:
    """Check if API key exists in environment variables"""
    env_vars = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "gemini": "GOOGLE_API_KEY",
        "google": "GOOGLE_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
    }
    
    env_var = env_vars.get(provider.lower())
    if env_var:
        return os.getenv(env_var)
    
    return None


def save_auth_to_env(provider: str, api_key: str) -> None:
    """Save API key to .env file"""
    env_vars = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "gemini": "GOOGLE_API_KEY",
        "google": "GOOGLE_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
    }
    
    env_var = env_vars.get(provider.lower())
    if not env_var:
        print(f"Warning: Unknown provider {provider}, cannot save to .env")
        return
    
    # Find .env file
    env_path = Path.cwd() / ".env"
    
    # Read existing content
    existing_lines = []
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            existing_lines = f.readlines()
    
    # Check if key already exists
    key_exists = False
    for i, line in enumerate(existing_lines):
        if line.strip().startswith(f"{env_var}="):
            existing_lines[i] = f"{env_var}={api_key}\n"
            key_exists = True
            break
    
    # Add if doesn't exist
    if not key_exists:
        existing_lines.append(f"\n# {provider.title()} API Key\n")
        existing_lines.append(f"{env_var}={api_key}\n")
    
    # Write back
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(existing_lines)
    
    print(f"API key saved to {env_path}")


def save_api_key_to_credentials(provider: str, api_key: str) -> None:
    """Save API key to the TS-aligned credentials store.

    Primary:  ~/.openclaw/agents/main/agent/auth-profiles.json
              Mirrors setGeminiApiKey / setAnthropicApiKey in
              openclaw/src/commands/onboard-auth.credentials.ts.

    Fallback: ~/.pi/agent/auth.json (pi_coding_agent legacy)
              Kept for backward compatibility until pi_coding_agent
              is updated to use OPENCLAW_AGENT_DIR.
    """
    _PROVIDER_NORMALISE = {
        "gemini": "google",
        "google": "google",
        "anthropic": "anthropic",
        "openai": "openai",
        "openrouter": "openrouter",
    }
    pi_provider = _PROVIDER_NORMALISE.get(provider.lower(), provider.lower())

    # ── Primary: ~/.openclaw/agents/main/agent/auth-profiles.json ────────────
    try:
        from openclaw.config.auth_profiles import set_api_key
        set_api_key(pi_provider, api_key)
    except Exception as e:
        print(f"Warning: Could not save to auth-profiles.json: {e}")

    # ── Fallback: ~/.pi/agent/auth.json (pi_coding_agent legacy) ─────────────
    try:
        from pi_coding_agent.core.auth_storage import AuthStorage
        AuthStorage().set_api_key(pi_provider, api_key)
    except Exception:
        pass  # non-fatal — primary store is enough


def configure_auth(provider: str) -> dict:
    """Configure authentication for a provider.

    TS-aligned: saves to both the credentials store (pi_coding_agent
    AuthStorage → ~/.pi/agent/auth.json) AND the .env file for convenience.
    The credentials store is what the gateway daemon uses; .env is for
    interactive `uv run` invocations.
    """
    # Check if API key already stored in credentials store (auth-profiles.json)
    stored_key: str | None = None
    try:
        from openclaw.config.auth_profiles import get_api_key, _PROVIDER_NORMALISE  # type: ignore[attr-defined]
        pi_provider = {
            "gemini": "google", "google": "google",
            "anthropic": "anthropic", "openai": "openai",
        }.get(provider.lower(), provider.lower())
        stored_key = get_api_key(pi_provider)
    except Exception:
        pass

    # Check environment variable
    env_key = check_env_api_key(provider)

    existing_key = stored_key or env_key
    if existing_key:
        source = "credentials store" if stored_key else "environment"
        use_existing = input(
            f"Found {provider.upper()} API key in {source}. Use it? [Y/n]: "
        ).strip().lower()
        if use_existing != "n":
            # Ensure it's in the credentials store even if it came from env
            if not stored_key:
                save_api_key_to_credentials(provider, existing_key)
            return {
                "provider": provider,
                "api_key": existing_key,
                "source": source,
            }

    # Prompt for API key
    api_key = prompt_api_key_simple(provider)

    # Save to credentials store (primary — used by daemon service)
    save_api_key_to_credentials(provider, api_key)

    # Also offer to save to .env (convenience for interactive runs)
    save_to_env = input("Also save API key to .env file? [Y/n]: ").strip().lower()
    if save_to_env != "n":
        try:
            save_auth_to_env(provider, api_key)
        except Exception as e:
            print(f"Warning: Could not save to .env: {e}")

    return {
        "provider": provider,
        "api_key": api_key,
        "source": "manual",
    }
