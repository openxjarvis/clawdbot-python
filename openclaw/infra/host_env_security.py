"""
Host environment variable sanitization for exec/subprocess calls.

Mirrors TS src/infra/host-env-security.ts + host-env-security-policy.json.

Protects against environment variable injection attacks where:
- A malicious actor sets PYTHONPATH or NODE_OPTIONS before the gateway runs
- A skill/tool script tries to override critical variables like PATH
- DYLD_* or LD_* vars can cause dynamic linker hijacking
"""
from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# Blocked individual environment variable keys
# Matches TS host-env-security-policy.json blocked keys (19 total)
# ---------------------------------------------------------------------------

BLOCKED_ENV_KEYS: frozenset[str] = frozenset([
    "NODE_OPTIONS",         # Node.js runtime injection
    "NODE_PATH",            # Node.js module path injection
    "PYTHONHOME",           # Python runtime injection
    "PYTHONPATH",           # Python module path injection
    "PYTHONSTARTUP",        # Python startup script injection
    "PYTHONEXECUTABLE",     # Python binary override
    "PERL5LIB",             # Perl library path injection
    "PERL5OPT",             # Perl command-line option injection
    "RUBYOPT",              # Ruby option injection
    "RUBYLIB",              # Ruby library path injection
    "BASH_ENV",             # Bash environment file (executed before any script)
    "ENV",                  # sh ENV startup file (executed before any interactive shell)
    "ZDOTDIR",              # Zsh dotfile directory redirect
    "SHELL",                # Shell binary override
    "IFS",                  # Internal field separator manipulation
    "PS1",                  # Shell prompt (can include command execution)
    "PS4",                  # Shell trace prompt (used in execution tracing attacks)
    "PROMPT_COMMAND",       # Bash prompt command injection
    "BASH_FUNC_%",          # Bash function export injection prefix pattern
])

# ---------------------------------------------------------------------------
# Blocked environment variable prefixes
# Matches TS host-env-security-policy.json blocked prefixes (3 total)
# ---------------------------------------------------------------------------

BLOCKED_ENV_PREFIXES: tuple[str, ...] = (
    "DYLD_",        # macOS dynamic linker — allows dylib injection
    "LD_",          # Linux dynamic linker — allows shared library injection
    "BASH_FUNC_",   # Bash exported function injection
)

# PATH is immutable — never allow overriding it through user/tool config
_IMMUTABLE_KEYS: frozenset[str] = frozenset(["PATH"])

# HOME cannot be overridden (prevents dotfile injection attacks)
_PROTECTED_KEYS: frozenset[str] = frozenset(["HOME"])


def _is_blocked_key(key: str) -> bool:
    """Return True if this env var key should be removed from exec environments."""
    if key in BLOCKED_ENV_KEYS:
        return True
    if key in _IMMUTABLE_KEYS:
        return False  # immutable means keep host value, not remove
    for prefix in BLOCKED_ENV_PREFIXES:
        if key.startswith(prefix):
            return True
    return False


def sanitize_host_exec_env(
    base_env: dict[str, str] | None = None,
    overrides: dict[str, str] | None = None,
) -> dict[str, str]:
    """
    Produce a sanitized environment dict for subprocess execution.

    Logic (mirrors TS sanitizeHostExecEnv):
    1. Start from base_env (defaults to os.environ).
    2. Remove all keys matching BLOCKED_ENV_KEYS or BLOCKED_ENV_PREFIXES.
    3. PATH is preserved from base_env — cannot be overridden via overrides.
    4. HOME is preserved from base_env — cannot be overridden.
    5. Apply remaining overrides (after filtering blocked keys).

    Args:
        base_env: Base environment (defaults to os.environ.copy()).
        overrides: Additional variables to merge (e.g. from tool config).
                   Blocked keys and PATH in overrides are silently ignored.

    Returns:
        Sanitized environment dict safe to pass to subprocess.
    """
    env = dict(base_env if base_env is not None else os.environ)

    # Remove blocked keys from base env
    blocked_keys_found = [k for k in list(env.keys()) if _is_blocked_key(k)]
    for key in blocked_keys_found:
        del env[key]

    # Apply allowed overrides
    if overrides:
        host_path = env.get("PATH")
        host_home = env.get("HOME")

        for key, value in overrides.items():
            if _is_blocked_key(key):
                continue
            if key in _IMMUTABLE_KEYS:
                continue
            if key in _PROTECTED_KEYS:
                continue
            env[key] = value

        # Restore PATH and HOME from host (cannot be overridden)
        if host_path is not None:
            env["PATH"] = host_path
        if host_home is not None:
            env["HOME"] = host_home

    return env


def get_blocked_env_keys_in(env: dict[str, str]) -> list[str]:
    """Return the list of blocked keys present in the given env dict (for auditing)."""
    return [k for k in env if _is_blocked_key(k)]


__all__ = [
    "BLOCKED_ENV_KEYS",
    "BLOCKED_ENV_PREFIXES",
    "sanitize_host_exec_env",
    "get_blocked_env_keys_in",
]
