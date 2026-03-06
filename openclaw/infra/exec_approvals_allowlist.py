"""
Exec approvals allowlist evaluation — mirrors TS src/infra/exec-approvals-allowlist.ts
+ src/infra/exec-approvals-analysis.ts

Evaluates whether a shell command is satisfied by the current exec-approvals.json
allowlist and safeBins, and resolves patterns to persist for "allow-always" decisions.
"""
from __future__ import annotations

import fnmatch
import os
import re
import shlex
import shutil
import sys
from dataclasses import dataclass, field
from typing import Any

# ──────────────────────────────────────────────────────────────────────────────
# Default safe bins (executables that are safe for read-only, non-destructive use)
# Mirrors TS DEFAULT_SAFE_BINS in exec-approvals-analysis.ts
# ──────────────────────────────────────────────────────────────────────────────

DEFAULT_SAFE_BINS: list[str] = [
    "cat", "ls", "echo", "pwd", "which", "whoami", "env",
    "date", "uname", "hostname", "id", "head", "tail",
    "wc", "sort", "uniq", "grep", "awk", "sed", "cut",
    "tr", "find", "du", "df", "ps", "top", "uptime",
    "printf", "true", "false", "test", "exit",
    "git",  # git status/log/diff are safe; destructive ops need allowlist
    "python", "python3", "pip", "pip3",
    "node", "npm", "npx",
    "cargo", "rustc",
    "go",
]

# Shells and dispatch-wrappers that get unwrapped for allow-always pattern resolution
_SHELL_EXECUTABLES = frozenset(["sh", "bash", "zsh", "fish", "dash", "ksh", "csh", "tcsh"])
_DISPATCH_WRAPPERS = frozenset(["nice", "nohup", "env", "sudo", "doas", "timeout", "strace", "ltrace"])
_SHELL_MULTIPLEXERS = frozenset(["busybox", "toybox"])

# Trusted directories for safe-bin path resolution
_DEFAULT_TRUSTED_DIRS: frozenset[str] = frozenset([
    "/usr/bin", "/bin", "/usr/local/bin",
    "/opt/homebrew/bin",  # macOS Homebrew
    "/usr/sbin", "/sbin",
])

# ──────────────────────────────────────────────────────────────────────────────
# Command chain splitter
# ──────────────────────────────────────────────────────────────────────────────

_CHAIN_PATTERN = re.compile(r"&&|\|\||(?<![\|&]);(?!;)")

def _has_shell_line_continuation(command: str) -> bool:
    """Return True if command contains shell line-continuation (\\newline)."""
    return bool(re.search(r"\\\n|\\\r\n|\\\r", command))


def split_command_chain(command: str) -> list[str] | None:
    """
    Split a shell command into chain parts on &&, ||, ;.
    Returns None if no chain operators found (single command).
    Respects single and double quotes to avoid false splits inside strings.

    Mirrors TS splitCommandChain().
    """
    parts: list[str] = []
    current: list[str] = []
    i = 0
    n = len(command)
    in_single = False
    in_double = False

    while i < n:
        ch = command[i]
        if ch == "'" and not in_double:
            in_single = not in_single
            current.append(ch)
            i += 1
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            current.append(ch)
            i += 1
            continue
        if in_single or in_double:
            current.append(ch)
            i += 1
            continue
        # Check for && or ||
        if i + 1 < n and command[i:i+2] in ("&&", "||"):
            parts.append("".join(current).strip())
            current = []
            i += 2
            continue
        # Check for ; (not ;; which is case statement)
        if ch == ";" and (i + 1 >= n or command[i + 1] != ";"):
            parts.append("".join(current).strip())
            current = []
            i += 1
            continue
        current.append(ch)
        i += 1

    tail = "".join(current).strip()
    if tail:
        parts.append(tail)

    if len(parts) <= 1:
        return None  # No chain operators found
    return [p for p in parts if p]


# ──────────────────────────────────────────────────────────────────────────────
# Command segment analysis
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class CommandResolution:
    """Parsed executable resolution for a command segment."""
    raw_executable: str = ""
    executable_name: str = ""  # basename without path
    resolved_path: str | None = None
    effective_argv: list[str] = field(default_factory=list)
    policy_blocked: bool = False  # True if this segment is unconditionally blocked


@dataclass
class ExecCommandSegment:
    """A single parsed command segment."""
    raw: str = ""
    argv: list[str] = field(default_factory=list)
    resolution: CommandResolution | None = None


def _resolve_executable(name: str) -> str | None:
    """Resolve executable name to absolute path using PATH."""
    return shutil.which(name)


def _parse_argv(command: str) -> list[str]:
    """Parse command into argv using shlex, falling back gracefully."""
    try:
        return shlex.split(command)
    except ValueError:
        # Unmatched quotes etc. — fall back to splitting on whitespace
        return command.split()


def _resolve_command_resolution(argv: list[str], cwd: str | None = None) -> CommandResolution:
    """Build CommandResolution from an argv list."""
    if not argv:
        return CommandResolution()
    raw_exec = argv[0]
    exec_name = os.path.basename(raw_exec)
    resolved = _resolve_executable(raw_exec) or (raw_exec if os.path.isabs(raw_exec) else None)
    return CommandResolution(
        raw_executable=raw_exec,
        executable_name=exec_name.lower(),
        resolved_path=resolved,
        effective_argv=argv,
    )


def analyze_shell_command(
    command: str,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> tuple[bool, list[ExecCommandSegment]]:
    """
    Parse a single (non-chained) shell command into segments with resolution.
    Returns (ok, segments).  ok=False means analysis failed (e.g. empty/invalid).

    Mirrors TS analyzeShellCommand().
    """
    command = command.strip()
    if not command:
        return False, []

    argv = _parse_argv(command)
    if not argv:
        return False, []

    resolution = _resolve_command_resolution(argv, cwd)
    segment = ExecCommandSegment(raw=command, argv=argv, resolution=resolution)
    return True, [segment]


# ──────────────────────────────────────────────────────────────────────────────
# Allowlist pattern matching
# ──────────────────────────────────────────────────────────────────────────────

def _normalize_pattern(pattern: str) -> str:
    """Lower-case and normalise a pattern for matching."""
    return pattern.strip().lower()


def _match_single_pattern(path: str, pattern: str) -> bool:
    """Match a resolved path against a single allowlist pattern (glob or exact)."""
    p = _normalize_pattern(pattern)
    target = path.lower()
    # Exact match
    if p == target:
        return True
    # Glob match
    if fnmatch.fnmatch(target, p):
        return True
    # Basename match: allow "git" to match "/usr/bin/git"
    basename = os.path.basename(target)
    if p == basename or fnmatch.fnmatch(basename, p):
        return True
    return False


def match_allowlist(
    allowlist: list[dict],
    resolution: CommandResolution | None,
) -> dict | None:
    """
    Match a command resolution against the allowlist.
    Returns the first matching entry dict or None.

    Mirrors TS matchAllowlist().
    """
    if not resolution or not allowlist:
        return None

    candidates: list[str] = []
    if resolution.resolved_path:
        candidates.append(resolution.resolved_path)
    if resolution.raw_executable:
        candidates.append(resolution.raw_executable)
        candidates.append(os.path.basename(resolution.raw_executable))
    if resolution.executable_name:
        candidates.append(resolution.executable_name)

    for entry in allowlist:
        pattern = entry.get("pattern", "")
        if not pattern:
            continue
        for candidate in candidates:
            if _match_single_pattern(candidate, pattern):
                return entry
    return None


def resolve_allowlist_candidate_path(
    resolution: CommandResolution | None,
    cwd: str | None = None,
) -> str | None:
    """Get the best candidate path for allowlist matching from a resolution."""
    if not resolution:
        return None
    if resolution.resolved_path:
        return resolution.resolved_path
    if resolution.raw_executable and os.path.isabs(resolution.raw_executable):
        return resolution.raw_executable
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Safe-bin check
# ──────────────────────────────────────────────────────────────────────────────

def normalize_safe_bins(entries: list[str] | None) -> frozenset[str]:
    """Normalise a list of safe bin names to a frozen lowercase set."""
    if not entries:
        return frozenset()
    return frozenset(e.strip().lower() for e in entries if e.strip())


def resolve_safe_bins(entries: list[str] | None) -> frozenset[str]:
    """Return safe bins from config, or defaults if None (mirrors TS resolveSafeBins)."""
    if entries is None:
        return normalize_safe_bins(DEFAULT_SAFE_BINS)
    return normalize_safe_bins(entries)


def _is_trusted_safe_bin_path(
    resolved_path: str | None,
    trusted_dirs: frozenset[str] | None = None,
) -> bool:
    """Return True if resolved_path is inside a trusted directory."""
    if not resolved_path:
        return False
    dirs = trusted_dirs if trusted_dirs is not None else _DEFAULT_TRUSTED_DIRS
    dirname = os.path.dirname(os.path.abspath(resolved_path))
    return dirname in dirs


def is_safe_bin_usage(
    argv: list[str],
    resolution: CommandResolution | None,
    safe_bins: frozenset[str],
    trusted_dirs: frozenset[str] | None = None,
    safe_bin_profiles: dict[str, Any] | None = None,
) -> bool:
    """
    Return True if this segment is satisfied by the safe-bins policy.
    Windows always returns False (conservative).

    Mirrors TS isSafeBinUsage().
    """
    if sys.platform == "win32":
        return False
    if not safe_bins:
        return False
    if not resolution:
        return False

    exec_name = resolution.executable_name.lower()
    if exec_name not in safe_bins:
        return False
    if not _is_trusted_safe_bin_path(resolution.resolved_path, trusted_dirs):
        return False

    # If safe_bin_profiles provided, validate argv against the profile
    if safe_bin_profiles and exec_name in safe_bin_profiles:
        try:
            from openclaw.infra.exec_safe_bin_validator import validate_safe_bin_argv, SafeBinProfile
            profile_data = safe_bin_profiles[exec_name]
            if isinstance(profile_data, dict):
                profile = SafeBinProfile(**profile_data)
            else:
                profile = profile_data
            return validate_safe_bin_argv(argv[1:], profile)
        except Exception:
            pass

    return True


# ──────────────────────────────────────────────────────────────────────────────
# Segment group evaluation
# ──────────────────────────────────────────────────────────────────────────────

def _evaluate_segments(
    segments: list[ExecCommandSegment],
    allowlist: list[dict],
    safe_bins: frozenset[str],
    safe_bin_profiles: dict[str, Any] | None,
    cwd: str | None,
    trusted_dirs: frozenset[str] | None,
) -> tuple[bool, list[dict], list[str | None]]:
    """
    Evaluate a list of segments against allowlist + safeBins.
    Returns (satisfied, matches, satisfied_by_labels).
    """
    matches: list[dict] = []
    satisfied_by: list[str | None] = []

    for segment in segments:
        if segment.resolution and segment.resolution.policy_blocked:
            satisfied_by.append(None)
            return False, matches, satisfied_by

        candidate_path = resolve_allowlist_candidate_path(segment.resolution, cwd)
        resolution = (
            CommandResolution(
                **{**segment.resolution.__dict__, "resolved_path": candidate_path}
            )
            if candidate_path and segment.resolution
            else segment.resolution
        )

        match = match_allowlist(allowlist, resolution)
        if match:
            matches.append(match)

        safe = is_safe_bin_usage(
            segment.argv, segment.resolution, safe_bins, trusted_dirs, safe_bin_profiles
        )

        by: str | None = "allowlist" if match else ("safeBins" if safe else None)
        satisfied_by.append(by)
        if by is None:
            return False, matches, satisfied_by

    return True, matches, satisfied_by


# ──────────────────────────────────────────────────────────────────────────────
# Main evaluation entry point
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class ExecAllowlistAnalysis:
    """Result of evaluating a shell command against the allowlist."""
    analysis_ok: bool = False
    allowlist_satisfied: bool = False
    allowlist_matches: list[dict] = field(default_factory=list)
    segments: list[ExecCommandSegment] = field(default_factory=list)
    segment_satisfied_by: list[str | None] = field(default_factory=list)


def evaluate_shell_allowlist(
    command: str,
    allowlist: list[dict],
    safe_bins: frozenset[str] | None = None,
    cwd: str | None = None,
    trusted_dirs: frozenset[str] | None = None,
    safe_bin_profiles: dict[str, Any] | None = None,
) -> ExecAllowlistAnalysis:
    """
    Evaluate a shell command (including &&/||/; chains) against the allowlist.
    Returns ExecAllowlistAnalysis.

    Mirrors TS evaluateShellAllowlist().
    """
    _safe_bins = safe_bins if safe_bins is not None else normalize_safe_bins(DEFAULT_SAFE_BINS)

    def _fail() -> ExecAllowlistAnalysis:
        return ExecAllowlistAnalysis(analysis_ok=False)

    # Conservative: shell line-continuation semantics are shell-specific
    if _has_shell_line_continuation(command):
        return _fail()

    # Split into chain parts on &&, ||, ;
    chain_parts = split_command_chain(command)
    if sys.platform == "win32":
        chain_parts = None  # Windows: treat as single command

    if not chain_parts:
        ok, segments = analyze_shell_command(command, cwd)
        if not ok or not segments:
            return _fail()
        satisfied, matches, by = _evaluate_segments(
            segments, allowlist, _safe_bins, safe_bin_profiles, cwd, trusted_dirs
        )
        return ExecAllowlistAnalysis(
            analysis_ok=True,
            allowlist_satisfied=satisfied,
            allowlist_matches=matches,
            segments=segments,
            segment_satisfied_by=by,
        )

    # Multi-part chain: all parts must be satisfied
    all_matches: list[dict] = []
    all_segments: list[ExecCommandSegment] = []
    all_by: list[str | None] = []

    for part in chain_parts:
        ok, segments = analyze_shell_command(part, cwd)
        if not ok or not segments:
            return _fail()
        all_segments.extend(segments)
        satisfied, matches, by = _evaluate_segments(
            segments, allowlist, _safe_bins, safe_bin_profiles, cwd, trusted_dirs
        )
        all_matches.extend(matches)
        all_by.extend(by)
        if not satisfied:
            return ExecAllowlistAnalysis(
                analysis_ok=True,
                allowlist_satisfied=False,
                allowlist_matches=all_matches,
                segments=all_segments,
                segment_satisfied_by=all_by,
            )

    return ExecAllowlistAnalysis(
        analysis_ok=True,
        allowlist_satisfied=True,
        allowlist_matches=all_matches,
        segments=all_segments,
        segment_satisfied_by=all_by,
    )


# ──────────────────────────────────────────────────────────────────────────────
# resolve_allow_always_patterns
# ──────────────────────────────────────────────────────────────────────────────

def _is_shell_wrapper(executable_name: str) -> bool:
    return executable_name.lower() in _SHELL_EXECUTABLES


def _is_dispatch_wrapper(executable_name: str) -> bool:
    return executable_name.lower() in _DISPATCH_WRAPPERS


def _is_shell_multiplexer(executable_name: str) -> bool:
    return executable_name.lower() in _SHELL_MULTIPLEXERS


def _extract_shell_wrapper_inline_command(argv: list[str]) -> str | None:
    """
    Extract the -c command string from a shell wrapper invocation.
    e.g. ["zsh", "-lc", "git status"] → "git status"
         ["bash", "-c", "cmd"] → "cmd"
    """
    if len(argv) < 3:
        return None
    shell = argv[0].lower()
    if os.path.basename(shell) not in _SHELL_EXECUTABLES:
        return None
    # Find -c flag
    for i, arg in enumerate(argv[1:], 1):
        if arg in ("-c",) or arg.endswith("c") and arg.startswith("-"):
            # Next arg is the command
            if i + 1 < len(argv):
                return argv[i + 1]
    # Some shells: -lc combines flags
    for arg in argv[1:]:
        if arg.startswith("-") and "c" in arg and not arg.startswith("--"):
            # The inline command may be concatenated or in the next position
            idx = argv.index(arg)
            if idx + 1 < len(argv):
                return argv[idx + 1]
    return None


def _collect_allow_always_patterns(
    segment: ExecCommandSegment,
    cwd: str | None,
    depth: int,
    out: set[str],
) -> None:
    """Recursively collect patterns for "allow always" (mirrors TS collectAllowAlwaysPatterns)."""
    if depth >= 3:
        return
    if not segment.argv:
        return

    exec_name = os.path.basename(segment.argv[0]).lower()

    # Dispatch wrapper (nice, nohup, env, timeout, sudo, …) → unwrap inner command
    if _is_dispatch_wrapper(exec_name):
        # Find first non-flag arg after the executable
        inner: list[str] = []
        i = 1
        while i < len(segment.argv):
            arg = segment.argv[i]
            if not arg.startswith("-") and "=" not in arg:
                inner = segment.argv[i:]
                break
            i += 1
        if inner:
            inner_resolution = _resolve_command_resolution(inner, cwd)
            _collect_allow_always_patterns(
                ExecCommandSegment(raw=" ".join(inner), argv=inner, resolution=inner_resolution),
                cwd,
                depth + 1,
                out,
            )
        return

    # Shell multiplexer (busybox, toybox) → block (too ambiguous)
    if _is_shell_multiplexer(exec_name):
        return  # blocked

    candidate_path = resolve_allowlist_candidate_path(segment.resolution, cwd)
    if not candidate_path:
        return

    # Shell wrapper → unwrap inner command
    if _is_shell_wrapper(exec_name):
        inline = _extract_shell_wrapper_inline_command(segment.argv)
        if not inline:
            return
        ok, inner_segments = analyze_shell_command(inline, cwd)
        if not ok:
            return
        for inner_seg in inner_segments:
            _collect_allow_always_patterns(inner_seg, cwd, depth + 1, out)
        return

    # Regular executable → persist resolved path
    out.add(candidate_path)


def resolve_allow_always_patterns(
    segments: list[ExecCommandSegment],
    cwd: str | None = None,
) -> list[str]:
    """
    Derive persisted allowlist patterns for an "allow always" decision.
    When wrapped in a shell (e.g. `zsh -lc "<cmd>"`), persists the inner
    executable(s) rather than the shell binary.

    Mirrors TS resolveAllowAlwaysPatterns().
    """
    patterns: set[str] = set()
    for segment in segments:
        _collect_allow_always_patterns(segment, cwd, 0, patterns)
    return list(patterns)


__all__ = [
    "DEFAULT_SAFE_BINS",
    "CommandResolution",
    "ExecCommandSegment",
    "ExecAllowlistAnalysis",
    "split_command_chain",
    "analyze_shell_command",
    "match_allowlist",
    "normalize_safe_bins",
    "resolve_safe_bins",
    "is_safe_bin_usage",
    "evaluate_shell_allowlist",
    "resolve_allow_always_patterns",
]
