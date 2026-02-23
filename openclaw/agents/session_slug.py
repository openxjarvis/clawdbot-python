"""
Session slug generation — exact port of TypeScript openclaw/src/agents/session-slug.ts.

Provides human-readable session IDs such as "swift-harbor" or "calm-reef".
Word lists are identical to the TypeScript source of truth.
"""
from __future__ import annotations

import random
import time
from typing import Callable

# 42 adjectives (exact TS list)
_SLUG_ADJECTIVES: list[str] = [
    "amber", "briny", "brisk", "calm", "clear", "cool", "crisp", "dawn",
    "delta", "ember", "faint", "fast", "fresh", "gentle", "glow", "good",
    "grand", "keen", "kind", "lucky", "marine", "mellow", "mild", "neat",
    "nimble", "nova", "oceanic", "plaid", "quick", "quiet", "rapid", "salty",
    "sharp", "swift", "tender", "tidal", "tidy", "tide", "vivid", "warm",
    "wild", "young",
]

# 54 nouns (exact TS list)
_SLUG_NOUNS: list[str] = [
    "atlas", "basil", "bison", "bloom", "breeze", "canyon", "cedar", "claw",
    "cloud", "comet", "coral", "cove", "crest", "crustacean", "daisy", "dune",
    "ember", "falcon", "fjord", "forest", "glade", "gulf", "harbor", "haven",
    "kelp", "lagoon", "lobster", "meadow", "mist", "nudibranch", "nexus",
    "ocean", "orbit", "otter", "pine", "prairie", "reef", "ridge", "river",
    "rook", "sable", "sage", "seaslug", "shell", "shoal", "shore", "slug",
    "summit", "tidepool", "trail", "valley", "wharf", "willow", "zephyr",
]


def _random_choice(values: list[str], fallback: str) -> str:
    if not values:
        return fallback
    return random.choice(values)


def _create_slug_base(words: int = 2) -> str:
    parts = [
        _random_choice(_SLUG_ADJECTIVES, "steady"),
        _random_choice(_SLUG_NOUNS, "harbor"),
    ]
    if words > 2:
        parts.append(_random_choice(_SLUG_NOUNS, "reef"))
    return "-".join(parts)


def create_session_slug(is_taken: Callable[[str], bool] | None = None) -> str:
    """
    Generate a human-readable session slug.

    Tries up to 12 two-word slugs (each with numeric suffixes 2–12), then
    falls back to 12 three-word slugs with the same suffix strategy.
    Final fallback: three-word slug + random suffix.

    Mirrors TS createSessionSlug().
    """
    _is_taken = is_taken or (lambda _: False)

    for _ in range(12):
        base = _create_slug_base(2)
        if not _is_taken(base):
            return base
        for i in range(2, 13):
            candidate = f"{base}-{i}"
            if not _is_taken(candidate):
                return candidate

    for _ in range(12):
        base = _create_slug_base(3)
        if not _is_taken(base):
            return base
        for i in range(2, 13):
            candidate = f"{base}-{i}"
            if not _is_taken(candidate):
                return candidate

    fallback = f"{_create_slug_base(3)}-{random.random().hex()[2:5]}"
    if _is_taken(fallback):
        return f"{fallback}-{hex(int(time.time() * 1000))[2:]}"
    return fallback
