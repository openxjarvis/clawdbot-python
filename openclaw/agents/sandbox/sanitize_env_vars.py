"""Sandbox environment variable sanitization

Strips credentials and sensitive values from the env dict before they
are injected into Docker containers.

Mirrors TypeScript openclaw/src/agents/sandbox/sanitize-env-vars.ts
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Blocked patterns — any env var whose name matches one of these will be
# removed from the container environment.
# ---------------------------------------------------------------------------

_BLOCKED_ENV_VAR_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^ANTHROPIC_API_KEY$", re.IGNORECASE),
    re.compile(r"^OPENAI_API_KEY$", re.IGNORECASE),
    re.compile(r"^GEMINI_API_KEY$", re.IGNORECASE),
    re.compile(r"^OPENROUTER_API_KEY$", re.IGNORECASE),
    re.compile(r"^MINIMAX_API_KEY$", re.IGNORECASE),
    re.compile(r"^ELEVENLABS_API_KEY$", re.IGNORECASE),
    re.compile(r"^SYNTHETIC_API_KEY$", re.IGNORECASE),
    re.compile(r"^TELEGRAM_BOT_TOKEN$", re.IGNORECASE),
    re.compile(r"^DISCORD_BOT_TOKEN$", re.IGNORECASE),
    re.compile(r"^SLACK_(BOT|APP)_TOKEN$", re.IGNORECASE),
    re.compile(r"^LINE_CHANNEL_SECRET$", re.IGNORECASE),
    re.compile(r"^LINE_CHANNEL_ACCESS_TOKEN$", re.IGNORECASE),
    re.compile(r"^OPENCLAW_GATEWAY_(TOKEN|PASSWORD)$", re.IGNORECASE),
    re.compile(r"^AWS_(SECRET_ACCESS_KEY|SECRET_KEY|SESSION_TOKEN)$", re.IGNORECASE),
    re.compile(r"^(GH|GITHUB)_TOKEN$", re.IGNORECASE),
    re.compile(r"^(AZURE|AZURE_OPENAI|COHERE|AI_GATEWAY|OPENROUTER)_API_KEY$", re.IGNORECASE),
    # Generic catch-all: any var that ends with _API_KEY, _TOKEN, _PASSWORD, _PRIVATE_KEY, _SECRET
    re.compile(r"_(API_KEY|TOKEN|PASSWORD|PRIVATE_KEY|SECRET)$", re.IGNORECASE),
]

# ---------------------------------------------------------------------------
# Allowed patterns — when strict_mode=True only these pass through.
# ---------------------------------------------------------------------------

_ALLOWED_ENV_VAR_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^LANG$"),
    re.compile(r"^LC_.*$", re.IGNORECASE),
    re.compile(r"^PATH$", re.IGNORECASE),
    re.compile(r"^HOME$", re.IGNORECASE),
    re.compile(r"^USER$", re.IGNORECASE),
    re.compile(r"^SHELL$", re.IGNORECASE),
    re.compile(r"^TERM$", re.IGNORECASE),
    re.compile(r"^TZ$", re.IGNORECASE),
    re.compile(r"^NODE_ENV$", re.IGNORECASE),
    re.compile(r"^PYTHON.*$", re.IGNORECASE),
]

# Maximum allowed length for an env var value
_MAX_VALUE_LENGTH = 32768

# Minimum length for which we check base64 heuristic
_BASE64_MIN_LENGTH = 80


@dataclass
class EnvVarSanitizationResult:
    """Result of sanitizing an environment variable dict."""

    allowed: dict[str, str] = field(default_factory=dict)
    blocked: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _validate_env_var_value(value: str) -> str | None:
    """Return a warning string if *value* looks suspicious, else None."""
    if "\0" in value:
        return "Contains null bytes"
    if len(value) > _MAX_VALUE_LENGTH:
        return "Value exceeds maximum length"
    if len(value) >= _BASE64_MIN_LENGTH and re.fullmatch(r"[A-Za-z0-9+/=]{80,}", value):
        return "Value looks like base64-encoded credential data"
    return None


def _matches_any(key: str, patterns: list[re.Pattern[str]]) -> bool:
    return any(p.search(key) for p in patterns)


def sanitize_env_vars(
    env: dict[str, str],
    strict_mode: bool = False,
    custom_blocked_patterns: list[re.Pattern[str]] | None = None,
    custom_allowed_patterns: list[re.Pattern[str]] | None = None,
) -> EnvVarSanitizationResult:
    """Remove sensitive environment variables from *env*.

    Args:
        env: The raw environment variable dict to sanitize.
        strict_mode: When True, only variables matching
            ``_ALLOWED_ENV_VAR_PATTERNS`` (plus any custom ones) pass through.
        custom_blocked_patterns: Extra patterns to block in addition to defaults.
        custom_allowed_patterns: Extra patterns to allow in addition to defaults.

    Returns:
        :class:`EnvVarSanitizationResult` with ``allowed``, ``blocked``, and
        ``warnings`` fields.
    """
    blocked_patterns = _BLOCKED_ENV_VAR_PATTERNS + (custom_blocked_patterns or [])
    allowed_patterns = _ALLOWED_ENV_VAR_PATTERNS + (custom_allowed_patterns or [])

    result = EnvVarSanitizationResult()

    for raw_key, value in env.items():
        key = raw_key.strip()
        if not key:
            continue

        if _matches_any(key, blocked_patterns):
            result.blocked.append(key)
            continue

        if strict_mode and not _matches_any(key, allowed_patterns):
            result.blocked.append(key)
            continue

        warning = _validate_env_var_value(value)
        if warning:
            if warning == "Contains null bytes":
                result.blocked.append(key)
                continue
            result.warnings.append(f"{key}: {warning}")

        result.allowed[key] = value

    return result


def get_blocked_patterns() -> list[str]:
    """Return the source strings of all default blocked patterns."""
    return [p.pattern for p in _BLOCKED_ENV_VAR_PATTERNS]


def get_allowed_patterns() -> list[str]:
    """Return the source strings of all default allowed patterns."""
    return [p.pattern for p in _ALLOWED_ENV_VAR_PATTERNS]
