"""Sandbox security validation

Blocks dangerous Docker configurations before containers are created.
Mirrors TypeScript ``openclaw/src/agents/sandbox/validate-sandbox-security.ts``
exactly — same blocked paths, same error messages, same logic flow.
"""
from __future__ import annotations

import os
import posixpath
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


# ---------------------------------------------------------------------------
# Blocked paths — must match TS BLOCKED_HOST_PATHS
# ---------------------------------------------------------------------------

BLOCKED_HOST_PATHS: list[str] = [
    "/etc",
    "/private/etc",
    "/proc",
    "/sys",
    "/dev",
    "/root",
    "/boot",
    # Directories that commonly contain (or alias) the Docker socket.
    "/run",
    "/var/run",
    "/private/var/run",
    "/var/run/docker.sock",
    "/private/var/run/docker.sock",
    "/run/docker.sock",
]

_BLOCKED_NETWORK_MODES: frozenset[str] = frozenset({"host"})
_BLOCKED_SECCOMP_PROFILES: frozenset[str] = frozenset({"unconfined"})
_BLOCKED_APPARMOR_PROFILES: frozenset[str] = frozenset({"unconfined"})


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


@dataclass
class BlockedBindReason:
    """Why a bind mount was blocked."""

    kind: Literal["targets", "covers", "non_absolute"]
    blocked_path: str = ""
    source_path: str = ""


# ---------------------------------------------------------------------------
# Path helpers (mirrors TS parseBindSourcePath / normalizeHostPath)
# ---------------------------------------------------------------------------


def parse_bind_source_path(bind: str) -> str:
    """Extract the source (host) path from ``source:target[:mode]``."""
    trimmed = bind.strip()
    first_colon = trimmed.find(":")
    if first_colon <= 0:
        return trimmed
    return trimmed[:first_colon]


def normalize_host_path(raw: str) -> str:
    """Normalize a POSIX path: resolve ``.``/``..``, collapse ``//``, strip trailing ``/``."""
    trimmed = raw.strip()
    normalized = posixpath.normpath(trimmed).rstrip("/") or "/"
    return normalized


# ---------------------------------------------------------------------------
# Core block-reason logic
# ---------------------------------------------------------------------------


def get_blocked_reason_for_source_path(source_normalized: str) -> BlockedBindReason | None:
    """Return a :class:`BlockedBindReason` if *source_normalized* is dangerous."""
    if source_normalized == "/":
        return BlockedBindReason(kind="covers", blocked_path="/")
    for blocked in BLOCKED_HOST_PATHS:
        if source_normalized == blocked or source_normalized.startswith(blocked + "/"):
            return BlockedBindReason(kind="targets", blocked_path=blocked)
    return None


def get_blocked_bind_reason(bind: str) -> BlockedBindReason | None:
    """String-only blocked-path check (no filesystem I/O).

    Mirrors TS ``getBlockedBindReason()``.
    """
    source_raw = parse_bind_source_path(bind)
    if not source_raw.startswith("/"):
        return BlockedBindReason(kind="non_absolute", source_path=source_raw)
    normalized = normalize_host_path(source_raw)
    return get_blocked_reason_for_source_path(normalized)


def _try_realpath_absolute(path: str) -> str:
    """Resolve symlinks on the local filesystem if the path exists."""
    if not path.startswith("/"):
        return path
    if not os.path.exists(path):
        return path
    try:
        return normalize_host_path(str(Path(path).resolve()))
    except Exception:
        return path


def _format_bind_blocked_error(bind: str, reason: BlockedBindReason) -> Exception:
    if reason.kind == "non_absolute":
        return ValueError(
            f'Sandbox security: bind mount "{bind}" uses a non-absolute source path '
            f'"{reason.source_path}". Only absolute POSIX paths are supported for sandbox binds.'
        )
    verb = "covers" if reason.kind == "covers" else "targets"
    return ValueError(
        f'Sandbox security: bind mount "{bind}" {verb} blocked path "{reason.blocked_path}". '
        "Mounting system directories (or Docker socket paths) into sandbox containers is not "
        "allowed. Use project-specific paths instead (e.g. /home/user/myproject)."
    )


# ---------------------------------------------------------------------------
# Public validators — mirrors TS validate* functions
# ---------------------------------------------------------------------------


def validate_bind_mounts(binds: list[str] | None) -> None:
    """Raise :class:`ValueError` if any bind mount is dangerous.

    Mirrors TS ``validateBindMounts()``.
    """
    if not binds:
        return

    for raw_bind in binds:
        bind = raw_bind.strip()
        if not bind:
            continue

        # Fast string-only check
        blocked = get_blocked_bind_reason(bind)
        if blocked:
            raise _format_bind_blocked_error(bind, blocked)

        # Symlink escape hardening
        source_raw = parse_bind_source_path(bind)
        source_normalized = normalize_host_path(source_raw)
        source_real = _try_realpath_absolute(source_normalized)
        if source_real != source_normalized:
            reason = get_blocked_reason_for_source_path(source_real)
            if reason:
                raise _format_bind_blocked_error(bind, reason)


def validate_network_mode(network: str | None) -> None:
    """Raise :class:`ValueError` if *network* mode is blocked.

    Mirrors TS ``validateNetworkMode()``.
    """
    if network and network.strip().lower() in _BLOCKED_NETWORK_MODES:
        raise ValueError(
            f'Sandbox security: network mode "{network}" is blocked. '
            'Network "host" mode bypasses container network isolation. '
            'Use "bridge" or "none" instead.'
        )


def validate_seccomp_profile(profile: str | None) -> None:
    """Raise :class:`ValueError` if *profile* is ``unconfined``.

    Mirrors TS ``validateSeccompProfile()``.
    """
    if profile and profile.strip().lower() in _BLOCKED_SECCOMP_PROFILES:
        raise ValueError(
            f'Sandbox security: seccomp profile "{profile}" is blocked. '
            "Disabling seccomp removes syscall filtering and weakens sandbox isolation. "
            "Use a custom seccomp profile file or omit this setting."
        )


def validate_apparmor_profile(profile: str | None) -> None:
    """Raise :class:`ValueError` if *profile* is ``unconfined``.

    Mirrors TS ``validateApparmorProfile()``.
    """
    if profile and profile.strip().lower() in _BLOCKED_APPARMOR_PROFILES:
        raise ValueError(
            f'Sandbox security: apparmor profile "{profile}" is blocked. '
            "Disabling AppArmor removes mandatory access controls and weakens sandbox isolation. "
            "Use a named AppArmor profile or omit this setting."
        )


def validate_sandbox_security(
    binds: list[str] | None = None,
    network: str | None = None,
    seccomp_profile: str | None = None,
    apparmor_profile: str | None = None,
) -> None:
    """Validate all sandbox security settings at once.

    Mirrors TS ``validateSandboxSecurity()``.

    Raises:
        ValueError: On the first security violation found.
    """
    validate_bind_mounts(binds)
    validate_network_mode(network)
    validate_seccomp_profile(seccomp_profile)
    validate_apparmor_profile(apparmor_profile)
