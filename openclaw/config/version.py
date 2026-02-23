"""
Version parsing and comparison — matches openclaw/src/config/version.ts
"""
from __future__ import annotations

import re
from typing import Optional


# v?X.Y.Z(-R)?
_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:-(\d+))?$")


class OpenClawVersion:
    """Parsed OpenClaw version."""

    __slots__ = ("major", "minor", "patch", "revision")

    def __init__(self, major: int, minor: int, patch: int, revision: int = 0) -> None:
        self.major = major
        self.minor = minor
        self.patch = patch
        self.revision = revision

    def __repr__(self) -> str:
        return f"OpenClawVersion({self.major}.{self.minor}.{self.patch}-{self.revision})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, OpenClawVersion):
            return NotImplemented
        return (self.major, self.minor, self.patch, self.revision) == (
            other.major, other.minor, other.patch, other.revision
        )


def parse_openclaw_version(raw: Optional[str]) -> Optional[OpenClawVersion]:
    """
    Parse a version string like "v1.2.3" or "1.2.3-4".

    Returns None on parse failure.

    Matches TS parseOpenClawVersion().
    """
    if not raw or not isinstance(raw, str):
        return None
    m = _VERSION_RE.match(raw.strip())
    if not m:
        return None
    major = int(m.group(1))
    minor = int(m.group(2))
    patch_num = int(m.group(3))
    revision = int(m.group(4)) if m.group(4) else 0
    return OpenClawVersion(major, minor, patch_num, revision)


def compare_openclaw_versions(
    a: Optional[str],
    b: Optional[str],
) -> Optional[int]:
    """
    Compare two version strings.

    Returns:
        -1 if a < b
         0 if a == b
         1 if a > b
        None if either cannot be parsed

    Matches TS compareOpenClawVersions().
    """
    va = parse_openclaw_version(a)
    vb = parse_openclaw_version(b)
    if va is None or vb is None:
        return None
    ta = (va.major, va.minor, va.patch, va.revision)
    tb = (vb.major, vb.minor, vb.patch, vb.revision)
    if ta < tb:
        return -1
    if ta > tb:
        return 1
    return 0


__all__ = [
    "OpenClawVersion",
    "parse_openclaw_version",
    "compare_openclaw_versions",
]
