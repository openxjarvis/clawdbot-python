"""Sandbox path utilities.

Mirrors TypeScript openclaw/src/agents/sandbox-paths.ts and the supporting
infra/path-alias-guards.ts / infra/boundary-path.ts modules.

Key exports:
- ``normalize_at_prefix``  — strip leading "@" from a path string.
- ``resolve_sandbox_path`` — resolve a path and verify it stays inside root.
- ``assert_sandbox_path``  — like resolve_sandbox_path + symlink/hardlink check.
- ``resolve_sandboxed_media_source`` — safe media path resolution with
  http pass-through, data: URL blocking, /workspace container mapping,
  and tmp dir allowance.
"""
from __future__ import annotations

import os
import re
import stat as _stat_module
from typing import TypedDict


# ---------------------------------------------------------------------------
# Constants (mirrors TS constants in sandbox-paths.ts)
# ---------------------------------------------------------------------------

_UNICODE_SPACES = re.compile("[\u00A0\u2000-\u200A\u202F\u205F\u3000]")
_HTTP_URL_RE = re.compile(r"^https?://", re.IGNORECASE)
_DATA_URL_RE = re.compile(r"^data:", re.IGNORECASE)
_FILE_URL_RE = re.compile(r"^file://", re.IGNORECASE)
_SANDBOX_CONTAINER_WORKDIR = "/workspace"


# ---------------------------------------------------------------------------
# Low-level path helpers
# ---------------------------------------------------------------------------

def normalize_at_prefix(file_path: str) -> str:
    """Strip a leading ``@`` from a file path.

    Mirrors TS ``normalizeAtPrefix()``.
    """
    return file_path[1:] if file_path.startswith("@") else file_path


def _normalize_unicode_spaces(s: str) -> str:
    return _UNICODE_SPACES.sub(" ", s)


def _expand_path(file_path: str) -> str:
    """Normalize Unicode spaces, strip @, then expand ~ to home dir."""
    normalized = _normalize_unicode_spaces(normalize_at_prefix(file_path))
    if normalized == "~":
        return os.path.expanduser("~")
    if normalized.startswith("~/"):
        return os.path.expanduser("~") + normalized[1:]
    return normalized


def _resolve_to_cwd(file_path: str, cwd: str) -> str:
    expanded = _expand_path(file_path)
    if os.path.isabs(expanded):
        return expanded
    return os.path.normpath(os.path.join(cwd, expanded))


def _short_path(value: str) -> str:
    home = os.path.expanduser("~")
    if value.startswith(home):
        return f"~{value[len(home):]}"
    return value


# ---------------------------------------------------------------------------
# Symlink / hardlink traversal guard (mirrors assertNoPathAliasEscape)
# ---------------------------------------------------------------------------

class _PathAliasPolicy(TypedDict, total=False):
    allow_final_symlink_for_unlink: bool
    allow_final_hardlink_for_unlink: bool


async def _assert_no_path_alias_escape(
    absolute_path: str,
    root_path: str,
    boundary_label: str,
    policy: _PathAliasPolicy | None = None,
) -> None:
    """Verify that ``absolute_path`` (and every symlink along the way)
    resolves to a path inside ``root_path``.

    Raises ``ValueError`` if a symlink escapes the sandbox root, or if a
    hardlink points outside the root (when not explicitly allowed).

    Mirrors TS ``assertNoPathAliasEscape()`` / ``resolveBoundaryPath()``.
    """
    allow_final_symlink = (policy or {}).get("allow_final_symlink_for_unlink", False)
    allow_final_hardlink = (policy or {}).get("allow_final_hardlink_for_unlink", False)

    root_real = os.path.realpath(root_path)
    abs_path = os.path.normpath(os.path.abspath(absolute_path))

    # Walk every component of the path, resolving symlinks incrementally.
    rel = os.path.relpath(abs_path, root_real)
    if rel.startswith("..") or os.path.isabs(rel):
        # Lexically outside root already — check if it canonically resolves inside.
        canonical = os.path.realpath(abs_path)
        _assert_inside(canonical, root_real, boundary_label, abs_path)
        return

    segments = abs_path[len(root_real):].lstrip(os.sep).split(os.sep)
    cursor = root_real
    for i, seg in enumerate(segments):
        if not seg:
            continue
        next_cursor = os.path.join(cursor, seg)
        is_last = i == len(segments) - 1
        try:
            st = os.lstat(next_cursor)
        except FileNotFoundError:
            # Path doesn't exist — lexically safe, continue
            cursor = next_cursor
            continue

        if _stat_module.S_ISLNK(st.st_mode):
            if allow_final_symlink and is_last:
                # Final component: symlink allowed (e.g. for unlink)
                cursor = next_cursor
                continue
            # Resolve the symlink and verify it stays inside root
            try:
                link_real = os.path.realpath(next_cursor)
            except OSError:
                link_real = next_cursor
            _assert_inside(link_real, root_real, boundary_label, abs_path)
            cursor = link_real
        else:
            # Regular file/dir — check hardlink count (nlink > 1 for files)
            if (
                not is_last
                and not allow_final_hardlink
                and _stat_module.S_ISREG(st.st_mode)
                and st.st_nlink > 1
            ):
                canonical = os.path.realpath(next_cursor)
                _assert_inside(canonical, root_real, boundary_label, abs_path)
            cursor = next_cursor


def _assert_inside(candidate: str, root_real: str, label: str, original: str) -> None:
    candidate_norm = os.path.normpath(candidate)
    root_norm = os.path.normpath(root_real)
    if candidate_norm == root_norm or candidate_norm.startswith(root_norm + os.sep):
        return
    raise ValueError(
        f"Path resolves outside {label} ({_short_path(root_real)}): {_short_path(original)}"
    )


# ---------------------------------------------------------------------------
# resolveSandboxPath
# ---------------------------------------------------------------------------

class _SandboxPathResult(TypedDict):
    resolved: str
    relative: str


def resolve_sandbox_path(
    file_path: str,
    cwd: str,
    root: str,
) -> _SandboxPathResult:
    """Resolve ``file_path`` relative to ``cwd`` and verify it stays inside
    ``root``.

    Raises ``ValueError`` if the resolved path escapes the sandbox root.
    Mirrors TS ``resolveSandboxPath()``.
    """
    resolved = _resolve_to_cwd(file_path, cwd)
    root_resolved = os.path.normpath(os.path.abspath(root))
    relative = os.path.relpath(root_resolved, resolved) if resolved != root_resolved else ""

    # Compute relative path from root to resolved
    try:
        relative = os.path.relpath(resolved, root_resolved)
    except ValueError:
        # Different drive on Windows
        raise ValueError(
            f"Path escapes sandbox root ({_short_path(root_resolved)}): {file_path}"
        )

    if not relative or relative == ".":
        return {"resolved": resolved, "relative": ""}

    if relative.startswith("..") or os.path.isabs(relative):
        raise ValueError(
            f"Path escapes sandbox root ({_short_path(root_resolved)}): {file_path}"
        )

    return {"resolved": resolved, "relative": relative}


# ---------------------------------------------------------------------------
# assertSandboxPath
# ---------------------------------------------------------------------------

async def assert_sandbox_path(
    file_path: str,
    cwd: str,
    root: str,
    allow_final_symlink_for_unlink: bool = False,
    allow_final_hardlink_for_unlink: bool = False,
) -> _SandboxPathResult:
    """Resolve and assert that ``file_path`` stays inside ``root``, including
    traversal of symlinks and hardlinks.

    Mirrors TS ``assertSandboxPath()``.
    """
    resolved = resolve_sandbox_path(file_path, cwd, root)
    policy: _PathAliasPolicy = {
        "allow_final_symlink_for_unlink": allow_final_symlink_for_unlink,
        "allow_final_hardlink_for_unlink": allow_final_hardlink_for_unlink,
    }
    await _assert_no_path_alias_escape(
        absolute_path=resolved["resolved"],
        root_path=root,
        boundary_label="sandbox root",
        policy=policy,
    )
    return resolved


# ---------------------------------------------------------------------------
# Media source helpers
# ---------------------------------------------------------------------------

def assert_media_not_data_url(media: str) -> None:
    """Raise if ``media`` is a data: URL.

    Mirrors TS ``assertMediaNotDataUrl()``.
    """
    if _DATA_URL_RE.match(media.strip()):
        raise ValueError("data: URLs are not supported for media. Use buffer instead.")


def _map_container_workspace_path(candidate: str, sandbox_root: str) -> str | None:
    """Map ``/workspace/...`` container paths to the local sandbox root.

    Mirrors TS ``mapContainerWorkspacePath()``.
    """
    normalized = candidate.replace("\\", "/")
    if normalized == _SANDBOX_CONTAINER_WORKDIR:
        return os.path.normpath(os.path.abspath(sandbox_root))
    prefix = f"{_SANDBOX_CONTAINER_WORKDIR}/"
    if not normalized.startswith(prefix):
        return None
    rel = normalized[len(prefix):]
    if not rel:
        return os.path.normpath(os.path.abspath(sandbox_root))
    parts = [p for p in rel.split("/") if p]
    return os.path.normpath(os.path.join(sandbox_root, *parts))


def _resolve_preferred_openclaw_tmp_dir() -> str:
    """Resolve the preferred OpenClaw tmp directory.

    Mirrors TS ``resolvePreferredOpenClawTmpDir()``.
    """
    import tempfile
    return os.path.join(tempfile.gettempdir(), "openclaw")


def _is_path_inside(root: str, candidate: str) -> bool:
    root_norm = os.path.normpath(os.path.abspath(root))
    cand_norm = os.path.normpath(os.path.abspath(candidate))
    return cand_norm == root_norm or cand_norm.startswith(root_norm + os.sep)


async def _resolve_allowed_tmp_media_path(
    candidate: str, sandbox_root: str
) -> str | None:
    """Return ``candidate`` if it resolves inside the OpenClaw tmp dir."""
    expanded = _expand_path(candidate)
    if not os.path.isabs(expanded):
        return None
    resolved = os.path.normpath(os.path.abspath(expanded))
    tmp_dir = os.path.normpath(os.path.abspath(_resolve_preferred_openclaw_tmp_dir()))
    if not _is_path_inside(tmp_dir, resolved):
        return None
    # Assert no alias escape inside tmp
    await _assert_no_path_alias_escape(
        absolute_path=resolved,
        root_path=tmp_dir,
        boundary_label="tmp root",
    )
    return resolved


async def resolve_sandboxed_media_source(
    media: str,
    sandbox_root: str,
) -> str:
    """Resolve a media path/URL for sandboxed tool use.

    Rules (mirrors TS ``resolveSandboxedMediaSource()``):
    - http/https URLs: pass through unchanged.
    - data: URLs: blocked (raise ValueError).
    - file:// URLs: map /workspace container path, then fall through.
    - /workspace/... container paths: mapped to ``sandbox_root``.
    - Absolute paths inside the tmp dir: allowed.
    - Everything else: must resolve inside ``sandbox_root``.
    """
    raw = media.strip()
    if not raw:
        return raw

    # HTTP/HTTPS: pass through
    if _HTTP_URL_RE.match(raw):
        return raw

    # data: blocked
    assert_media_not_data_url(raw)

    candidate = raw

    # file:// URL handling
    if _FILE_URL_RE.match(candidate):
        # Try to map /workspace container file URLs
        try:
            from urllib.parse import urlparse, unquote
            parsed = urlparse(candidate)
            if parsed.scheme == "file":
                pathname = unquote(parsed.path).replace("\\", "/")
                mapped = _map_container_workspace_path(pathname, sandbox_root)
                if mapped:
                    candidate = mapped
                else:
                    # Convert file:// URL to local path
                    import urllib.request
                    candidate = urllib.request.url2pathname(parsed.path)
        except Exception as exc:
            raise ValueError(f"Invalid file:// URL for sandboxed media: {raw}") from exc

    # Container /workspace mapping
    container_mapped = _map_container_workspace_path(candidate, sandbox_root)
    if container_mapped:
        candidate = container_mapped

    # Tmp dir allowance
    tmp_path = await _resolve_allowed_tmp_media_path(candidate, sandbox_root)
    if tmp_path:
        return tmp_path

    # Must be inside sandbox root
    result = await assert_sandbox_path(
        file_path=candidate,
        cwd=sandbox_root,
        root=sandbox_root,
    )
    return result["resolved"]
