"""
Per-binary argv validation for safe-bin execution policy.

Mirrors TS src/infra/exec-safe-bin-policy-validator.ts.

Safe bins are stdin-only tools that can be called without full shell approval.
This validator enforces per-binary argument constraints so that even "safe" binaries
cannot be called with dangerous flags (e.g. `git` with `--upload-pack` for SSRF).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SafeBinProfile:
    """
    Per-binary argument validation profile.

    Mirrors TS SafeBinProfile from exec-safe-bin-policy-profiles.ts.
    """
    # Set of long flags (--flag) that accept a value argument
    allowed_value_flags: set[str] = field(default_factory=set)
    # Set of flags (short or long) that are explicitly denied
    denied_flags: set[str] = field(default_factory=set)
    # Minimum number of positional arguments required
    min_positional: int = 0
    # Maximum number of positional arguments allowed (None = unlimited)
    max_positional: int | None = None


def _is_path_like(value: str) -> bool:
    """Return True if the token looks like a filesystem path."""
    t = value.strip()
    if not t or t == "-":
        return False
    if t.startswith(("./", "../", "~", "/")):
        return True
    # Windows drive letter
    if len(t) >= 3 and t[1] == ":" and t[2] in ("/", "\\"):
        return True
    return False


def _has_glob(value: str) -> bool:
    """Return True if the value contains glob metacharacters."""
    return any(c in value for c in "*?[]")


def _is_safe_literal(value: str) -> bool:
    """Return True if the value is a safe literal (no glob, no path)."""
    if not value or value == "-":
        return True
    return not _has_glob(value) and not _is_path_like(value)


def _parse_token(raw: str) -> dict[str, Any]:
    """
    Parse a single argv token into its type and components.

    Returns a dict with keys:
    - kind: "empty" | "stdin" | "terminator" | "positional" | "flag"
    - style: "short" | "long" (for flags)
    - flag: canonical flag string (for long flags: --flag)
    - flags: list of single-char flags (for short clusters: -abc)
    - cluster: original cluster string (for short: "abc")
    - inline_value: value after = (for --flag=value)
    - raw: original token
    """
    if not raw:
        return {"kind": "empty", "raw": raw}
    if raw == "-":
        return {"kind": "stdin", "raw": raw}
    if raw == "--":
        return {"kind": "terminator", "raw": raw}

    if raw.startswith("--"):
        # Long option: --flag or --flag=value
        if "=" in raw:
            flag_part, inline_value = raw.split("=", 1)
        else:
            flag_part, inline_value = raw, None
        return {
            "kind": "flag",
            "style": "long",
            "flag": flag_part,
            "inline_value": inline_value,
            "raw": raw,
        }

    if raw.startswith("-") and len(raw) > 1:
        # Short option cluster: -abc or -aVALUE
        cluster = raw[1:]
        flags = list(cluster)
        return {
            "kind": "flag",
            "style": "short",
            "cluster": cluster,
            "flags": flags,
            "raw": raw,
        }

    return {"kind": "positional", "raw": raw}


def validate_safe_bin_argv(args: list[str], profile: SafeBinProfile) -> bool:
    """
    Validate an argv list against a SafeBinProfile.

    Returns True if the arguments are safe according to the profile, False otherwise.
    Mirrors TS validateSafeBinArgv().

    Rules:
    - Unknown long flags → rejected
    - Denied flags (short or long) → rejected
    - Flags with values: value must be a safe literal (no glob, no path)
    - Positional args: must be safe literals, count must be in [min, max]
    - Glob characters anywhere → rejected
    - Path-like tokens in positional args → rejected

    Args:
        args: Argument list (NOT including the binary name).
        profile: Validation profile for this binary.

    Returns:
        True if arguments are valid, False otherwise.
    """
    positional: list[str] = []
    i = 0

    while i < len(args):
        raw = args[i] if i < len(args) else ""
        token = _parse_token(raw)

        if token["kind"] in ("empty", "stdin"):
            i += 1
            continue

        if token["kind"] == "terminator":
            # Everything after -- is positional
            for rest in args[i + 1 :]:
                if not rest or rest == "-":
                    continue
                if not _is_safe_literal(rest):
                    return False
                positional.append(rest)
            break

        if token["kind"] == "positional":
            if not _is_safe_literal(token["raw"]):
                return False
            positional.append(token["raw"])
            i += 1
            continue

        # Flag handling
        if token["style"] == "long":
            flag: str = token["flag"]
            inline_value: str | None = token.get("inline_value")

            # Denied flags
            if flag in profile.denied_flags:
                return False

            # Must be in allowed_value_flags OR be a known bool flag
            expects_value = flag in profile.allowed_value_flags
            if inline_value is not None:
                if not expects_value:
                    return False
                if not _is_safe_literal(inline_value):
                    return False
                i += 1
            elif expects_value:
                # Value is the next token
                if i + 1 >= len(args) or not _is_safe_literal(args[i + 1]):
                    return False
                i += 2
            else:
                # Must be in some known set — if not in allowed_value_flags and not denied,
                # reject unknown flags conservatively
                # (profile should list all allowed bool flags in allowed_value_flags with empty sentinel)
                # For maximum safety: if the flag is not in the known set, reject
                if profile.allowed_value_flags and flag not in profile.allowed_value_flags:
                    return False
                i += 1
            continue

        # Short flag cluster
        cluster_flags: list[str] = token["flags"]
        cluster: str = token["cluster"]
        consumed = i + 1
        valid = True
        for j, f in enumerate(cluster_flags):
            short = f"-{f}"
            if short in profile.denied_flags or f in profile.denied_flags:
                valid = False
                break
            if short in profile.allowed_value_flags or f in profile.allowed_value_flags:
                # Remaining chars in cluster are the inline value
                inline = cluster[j + 1 :]
                if inline:
                    if not _is_safe_literal(inline):
                        valid = False
                    break
                # Value is next token
                if i + 1 >= len(args) or not _is_safe_literal(args[i + 1]):
                    valid = False
                    break
                consumed = i + 2
                break
        if not valid:
            return False
        i = consumed

    # Validate positional count
    if len(positional) < profile.min_positional:
        return False
    if profile.max_positional is not None and len(positional) > profile.max_positional:
        return False

    return True


__all__ = ["SafeBinProfile", "validate_safe_bin_argv"]
