"""
Sandbox security validation — mirrors TS src/agents/sandbox/validate-sandbox-security.ts

Blocks dangerous Docker configurations before container creation.
Threat model: local-trusted config, but protect against foot-guns and config injection.
"""
from __future__ import annotations

import os
from pathlib import PurePosixPath
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Host paths that should never be bind-mounted into sandbox containers.
# Matches TS BLOCKED_HOST_PATHS.
BLOCKED_HOST_PATHS: list[str] = [
    "/etc",
    "/private/etc",
    "/proc",
    "/sys",
    "/dev",
    "/root",
    "/boot",
    "/run",
    "/var/run",
    "/private/var/run",
    "/var/run/docker.sock",
    "/private/var/run/docker.sock",
    "/run/docker.sock",
]

_BLOCKED_SECCOMP_PROFILES: frozenset[str] = frozenset(["unconfined"])
_BLOCKED_APPARMOR_PROFILES: frozenset[str] = frozenset(["unconfined"])

# Container paths reserved by OpenClaw sandbox — must not be shadowed by bind mounts.
_RESERVED_CONTAINER_TARGETS: list[str] = ["/workspace", "/agent"]


# ---------------------------------------------------------------------------
# Path helpers (pure string, no I/O)
# ---------------------------------------------------------------------------

def _normalize_host_path(raw: str) -> str:
    """Normalize a POSIX path: resolve `.`/`..`, collapse `//`, strip trailing `/`."""
    parts = raw.split("/")
    resolved: list[str] = []
    for part in parts:
        if part == "" or part == ".":
            continue
        if part == "..":
            if resolved:
                resolved.pop()
        else:
            resolved.append(part)
    normalized = "/" + "/".join(resolved)
    return normalized if normalized != "/" else "/"


def _is_path_inside(root: str, target: str) -> bool:
    if root == "/":
        return True
    return target == root or target.startswith(root + "/")


def _resolve_via_existing_ancestor(path: str) -> str:
    """Resolve symlinks through existing ancestors to prevent symlink-escape bind mounts."""
    p = path
    # Walk up until we find an existing prefix, then realpath that prefix.
    parts = []
    while p and p != "/":
        if os.path.exists(p):
            try:
                real = os.path.realpath(p)
                if parts:
                    suffix = "/".join(reversed(parts))
                    return _normalize_host_path(real + "/" + suffix)
                return real
            except OSError:
                pass
        p, tail = os.path.split(p)
        parts.append(tail)
    return path


def _parse_bind_source(bind: str) -> str:
    """Extract host/source path from a Docker bind string `source:target[:mode]`."""
    trimmed = bind.strip()
    # Handle Windows-style drive letter (unlikely but safe)
    parts = trimmed.split(":")
    if len(parts) >= 2:
        return parts[0]
    return trimmed


def _parse_bind_target(bind: str) -> str:
    """Extract container target path from `source:target[:mode]`."""
    parts = bind.strip().split(":")
    if len(parts) >= 2:
        return parts[1]
    return ""


# ---------------------------------------------------------------------------
# Individual validators
# ---------------------------------------------------------------------------

def validate_bind_mounts(
    binds: list[str] | None,
    *,
    allowed_source_roots: list[str] | None = None,
    allow_sources_outside_allowed_roots: bool = False,
    allow_reserved_container_targets: bool = False,
) -> None:
    """Validate Docker bind mounts — raises ValueError on dangerous configs."""
    if not binds:
        return

    norm_roots: list[str] = []
    if allowed_source_roots:
        for root in allowed_source_roots:
            r = root.strip()
            if r.startswith("/"):
                norm = _normalize_host_path(r)
                norm_roots.append(norm)
                real = _resolve_via_existing_ancestor(norm)
                if real != norm:
                    norm_roots.append(real)

    for raw_bind in binds:
        bind = raw_bind.strip()
        if not bind:
            continue

        source_raw = _parse_bind_source(bind)

        # Non-absolute source paths are rejected (volume names, relative paths)
        if not source_raw.startswith("/"):
            raise ValueError(
                f'Sandbox security: bind "{bind}" uses non-absolute source path '
                f'"{source_raw}". Only absolute POSIX paths are allowed.'
            )

        source = _normalize_host_path(source_raw)

        # Block root mount
        if source == "/":
            raise ValueError(
                f'Sandbox security: bind "{bind}" covers the root filesystem. '
                "Mounting / into a sandbox container is not allowed."
            )

        # Check against blocked paths
        for blocked in BLOCKED_HOST_PATHS:
            if source == blocked or source.startswith(blocked + "/"):
                raise ValueError(
                    f'Sandbox security: bind "{bind}" targets blocked path "{blocked}". '
                    "Mounting system directories into sandbox containers is not allowed."
                )

        # Check reserved container targets
        if not allow_reserved_container_targets:
            target_raw = _parse_bind_target(bind)
            if target_raw and target_raw.startswith("/"):
                target = _normalize_host_path(target_raw)
                for reserved in _RESERVED_CONTAINER_TARGETS:
                    if _is_path_inside(reserved, target):
                        raise ValueError(
                            f'Sandbox security: bind "{bind}" targets reserved container path '
                            f'"{reserved}". This can shadow OpenClaw sandbox mounts.'
                        )

        # Check allowed source roots
        if norm_roots and not allow_sources_outside_allowed_roots:
            inside = any(_is_path_inside(root, source) for root in norm_roots)
            if not inside:
                # Re-check after symlink resolution
                canonical = _resolve_via_existing_ancestor(source)
                inside = any(_is_path_inside(root, canonical) for root in norm_roots)
            if not inside:
                raise ValueError(
                    f'Sandbox security: bind "{bind}" source "{source}" is outside '
                    f"allowed roots ({', '.join(norm_roots)})."
                )

        # Symlink-escape hardening: re-check via existing ancestors
        canonical = _resolve_via_existing_ancestor(source)
        if canonical != source:
            if canonical == "/":
                raise ValueError(
                    f'Sandbox security: bind "{bind}" resolves to root via symlink.'
                )
            for blocked in BLOCKED_HOST_PATHS:
                if canonical == blocked or canonical.startswith(blocked + "/"):
                    raise ValueError(
                        f'Sandbox security: bind "{bind}" resolves via symlink to blocked path '
                        f'"{blocked}".'
                    )


def validate_network_mode(
    network: str | None,
    *,
    allow_container_namespace_join: bool = False,
) -> None:
    """Validate Docker network mode — raises ValueError for dangerous modes."""
    if not network:
        return
    n = network.strip().lower()
    if n == "host":
        raise ValueError(
            f'Sandbox security: network mode "{network}" is blocked. '
            'Network "host" bypasses container network isolation. Use "bridge" or "none".'
        )
    if n.startswith("container:") and not allow_container_namespace_join:
        raise ValueError(
            f'Sandbox security: network mode "{network}" is blocked by default. '
            'Container namespace joins bypass sandbox network isolation. '
            "Set dangerouslyAllowContainerNamespaceJoin=true only when you fully trust this runtime."
        )


def validate_seccomp_profile(profile: str | None) -> None:
    """Raise ValueError if the seccomp profile is 'unconfined'."""
    if profile and profile.strip().lower() in _BLOCKED_SECCOMP_PROFILES:
        raise ValueError(
            f'Sandbox security: seccomp profile "{profile}" is blocked. '
            "Disabling seccomp removes syscall filtering. Use a custom profile or omit this setting."
        )


def validate_apparmor_profile(profile: str | None) -> None:
    """Raise ValueError if the AppArmor profile is 'unconfined'."""
    if profile and profile.strip().lower() in _BLOCKED_APPARMOR_PROFILES:
        raise ValueError(
            f'Sandbox security: apparmor profile "{profile}" is blocked. '
            "Disabling AppArmor removes mandatory access controls. "
            "Use a named profile or omit this setting."
        )


def validate_sandbox_security(
    cfg: dict[str, Any],
    *,
    allowed_source_roots: list[str] | None = None,
) -> None:
    """
    Full sandbox security validation — call before creating a Docker container.

    Args:
        cfg: dict with keys: binds, network, seccomp_profile/seccompProfile,
             apparmor_profile/apparmorProfile, and dangerous override flags.
        allowed_source_roots: optional list of allowed host bind-mount roots.

    Raises:
        ValueError: if any security constraint is violated.
    """
    binds: list[str] | None = cfg.get("binds")
    network: str | None = cfg.get("network")
    seccomp = cfg.get("seccomp_profile") or cfg.get("seccompProfile")
    apparmor = cfg.get("apparmor_profile") or cfg.get("apparmorProfile")
    allow_ns_join: bool = bool(
        cfg.get("dangerously_allow_container_namespace_join")
        or cfg.get("dangerouslyAllowContainerNamespaceJoin")
    )
    allow_reserved: bool = bool(
        cfg.get("dangerously_allow_reserved_container_targets")
        or cfg.get("dangerouslyAllowReservedContainerTargets")
    )
    allow_external: bool = bool(
        cfg.get("dangerously_allow_external_bind_sources")
        or cfg.get("dangerouslyAllowExternalBindSources")
    )

    validate_bind_mounts(
        binds,
        allowed_source_roots=allowed_source_roots,
        allow_sources_outside_allowed_roots=allow_external,
        allow_reserved_container_targets=allow_reserved,
    )
    validate_network_mode(network, allow_container_namespace_join=allow_ns_join)
    validate_seccomp_profile(seccomp)
    validate_apparmor_profile(apparmor)


__all__ = [
    "BLOCKED_HOST_PATHS",
    "validate_bind_mounts",
    "validate_network_mode",
    "validate_seccomp_profile",
    "validate_apparmor_profile",
    "validate_sandbox_security",
    "parse_bind_source_path",
    "parse_bind_target_path",
    "normalize_host_path",
]

# Public aliases matching TS export names
parse_bind_source_path = _parse_bind_source
parse_bind_target_path = _parse_bind_target
normalize_host_path = _normalize_host_path
