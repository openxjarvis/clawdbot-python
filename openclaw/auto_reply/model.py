"""Model directive extraction from message bodies.

Aligned with TypeScript openclaw/src/auto-reply/model.ts.

Parses /model directives and optional aliases from incoming message text,
returning a cleaned body and the extracted model/profile parts.
"""
from __future__ import annotations

import re
from typing import TypedDict


class ModelDirectiveResult(TypedDict):
    cleaned: str
    raw_model: str | None
    raw_profile: str | None
    has_directive: bool


# Matches /model followed by optional whitespace/colon and then a model string.
# Mirrors the TS regex: /(?:^|\s)\/model(?=$|\s|:)\s*:?\s*([A-Za-z0-9_.:@-]+(?:\/[A-Za-z0-9_.:@-]+)*)?/i
_MODEL_DIRECTIVE_RE = re.compile(
    r"(?:^|\s)/model(?=$|\s|:)\s*:?\s*([A-Za-z0-9_.:@-]+(?:/[A-Za-z0-9_.:@-]+)*)?",
    re.IGNORECASE,
)


def _escape_regexp(value: str) -> str:
    """Escape a string for use in a regex pattern. Mirrors TS escapeRegExp()."""
    return re.escape(value)


def extract_model_directive(
    body: str | None,
    options: dict | None = None,
) -> ModelDirectiveResult:
    """Extract a /model directive (or alias) from *body*.

    Returns a dict with:
    - ``cleaned``: body with the directive removed
    - ``raw_model``: raw model string (before @profile split), or None
    - ``raw_profile``: profile after @ in "model@profile" syntax, or None
    - ``has_directive``: whether any directive was found

    Mirrors TS extractModelDirective().
    """
    if not body:
        return {"cleaned": "", "raw_model": None, "raw_profile": None, "has_directive": False}

    model_match = _MODEL_DIRECTIVE_RE.search(body)

    aliases: list[str] = []
    if options and options.get("aliases"):
        aliases = [a.strip() for a in options["aliases"] if isinstance(a, str) and a.strip()]

    alias_match = None
    if not model_match and aliases:
        pattern = (
            r"(?:^|\s)/("
            + "|".join(_escape_regexp(a) for a in aliases)
            + r")(?=$|\s|:)(?:\s*:\s*)?"
        )
        alias_match = re.search(pattern, body, re.IGNORECASE)

    match = model_match or alias_match
    if model_match:
        raw = (model_match.group(1) or "").strip() or None
    elif alias_match:
        raw = (alias_match.group(1) or "").strip() or None
    else:
        raw = None

    raw_model: str | None = raw
    raw_profile: str | None = None
    if raw and "@" in raw:
        parts = raw.split("@", 1)
        raw_model = parts[0].strip() or None
        raw_profile = parts[1].strip() or None

    if match:
        cleaned = body.replace(match.group(0), " ", 1)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
    else:
        cleaned = body.strip()

    return {
        "cleaned": cleaned,
        "raw_model": raw_model,
        "raw_profile": raw_profile,
        "has_directive": match is not None,
    }


__all__ = ["extract_model_directive", "ModelDirectiveResult"]
