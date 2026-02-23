"""Media parsing from agent output.

Extracts MEDIA: tokens and directives from agent text output.
Aligned with TypeScript src/media/parse.ts

The agent signals file delivery by including lines like:
    MEDIA:/path/to/file.pptx
    MEDIA:https://example.com/image.jpg
    MEDIA:`/path/with spaces/file.pdf`
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# Matches: MEDIA: followed by an optional backtick-quoted or bare path/URL
# Mirrors TS: /\bMEDIA:\s*`?([^\n]+)`?/gi
_MEDIA_TOKEN_RE = re.compile(r"\bMEDIA:\s*`?([^\n`]+)`?", re.IGNORECASE)

# Fenced code block detector — avoid extracting MEDIA: tokens inside ``` blocks
_FENCE_RE = re.compile(r"^```", re.MULTILINE)


@dataclass
class MediaParseResult:
    """Result of parsing media from output text."""

    text: Optional[str] = None
    media_url: Optional[str] = None           # first URL (legacy single-item compat)
    media_urls: Optional[list[str]] = None    # all URLs when >1
    audio_as_voice: bool = False


def _is_valid_media_source(candidate: str) -> bool:
    """Return True if the candidate looks like a usable media source."""
    if not candidate:
        return False
    c = candidate.strip()
    # HTTP/S URL
    if c.startswith(("http://", "https://", "file://")):
        return True
    # Absolute local path
    if c.startswith("/") or c.startswith("~"):
        return True
    # Relative path with extension (e.g. ./foo.png, presentations/file.pptx)
    if re.search(r"\.[a-zA-Z0-9]{1,6}$", c):
        return True
    return False


def _normalize_media_source(raw: str) -> str:
    """Expand ~ and strip surrounding quotes."""
    raw = raw.strip().strip("'\"")
    if raw.startswith("~"):
        raw = str(Path(raw).expanduser())
    return raw


def split_media_from_output(text: str) -> MediaParseResult:
    """Split MEDIA: tokens and directives from output text.

    Supports:
    - ``MEDIA:/absolute/path/file.pptx``
    - ``MEDIA:~/relative/path/file.pdf``
    - ``MEDIA:https://example.com/image.jpg``
    - ``MEDIA:`/path with spaces/file.pdf```
    - Legacy ``[[image:URL]]``, ``[[audio:URL]]``, ``[[file:URL]]`` tags

    Args:
        text: Output text from agent

    Returns:
        MediaParseResult with cleaned text and extracted media URLs.
    """
    if not text:
        return MediaParseResult()

    media_urls: list[str] = []
    audio_as_voice = False

    # -----------------------------------------------------------------------
    # 1. Handle fenced code blocks — skip MEDIA: extraction inside them
    # -----------------------------------------------------------------------
    fence_positions: list[tuple[int, int]] = []
    fence_starts = [m.start() for m in _FENCE_RE.finditer(text)]
    for i in range(0, len(fence_starts) - 1, 2):
        fence_positions.append((fence_starts[i], fence_starts[i + 1]))

    def _inside_fence(pos: int) -> bool:
        return any(s <= pos <= e for s, e in fence_positions)

    # -----------------------------------------------------------------------
    # 2. Parse line-by-line, extracting MEDIA: tokens
    # -----------------------------------------------------------------------
    lines = text.split("\n")
    kept_lines: list[str] = []
    char_offset = 0

    for line in lines:
        stripped = line.lstrip()
        if stripped.upper().startswith("MEDIA:") and not _inside_fence(char_offset):
            # Extract all MEDIA: tokens from this line
            found_any = False
            for m in _MEDIA_TOKEN_RE.finditer(line):
                raw = m.group(1).strip()
                candidate = _normalize_media_source(raw)
                if _is_valid_media_source(candidate):
                    media_urls.append(candidate)
                    found_any = True
            if found_any:
                # Remove this line from output text
                char_offset += len(line) + 1
                continue
        kept_lines.append(line)
        char_offset += len(line) + 1

    clean_text = "\n".join(kept_lines).rstrip()

    # -----------------------------------------------------------------------
    # 3. Legacy [[TYPE:URL]] tags — kept for backward compat
    # -----------------------------------------------------------------------
    legacy_pattern = re.compile(
        r"\[\[(image|audio|video|file):([^\]]+)\]\]", re.IGNORECASE
    )

    def _replace_legacy(match: re.Match) -> str:
        url = match.group(2).strip()
        if url:
            media_urls.append(_normalize_media_source(url))
        return ""

    clean_text = legacy_pattern.sub(_replace_legacy, clean_text)

    # -----------------------------------------------------------------------
    # 4. [[audio_as_voice]] directive
    # -----------------------------------------------------------------------
    voice_pattern = re.compile(r"\[\[audio_as_voice\]\]", re.IGNORECASE)
    if voice_pattern.search(clean_text):
        audio_as_voice = True
        clean_text = voice_pattern.sub("", clean_text)

    clean_text = re.sub(r"\n{3,}", "\n\n", clean_text).rstrip()

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_urls: list[str] = []
    for u in media_urls:
        if u not in seen:
            seen.add(u)
            unique_urls.append(u)

    return MediaParseResult(
        text=clean_text if clean_text else None,
        media_url=unique_urls[0] if len(unique_urls) >= 1 else None,
        media_urls=unique_urls if len(unique_urls) > 1 else None,
        audio_as_voice=audio_as_voice,
    )
