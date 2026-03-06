"""
ReDoS-safe regex compilation with nested-quantifier detection.

Mirrors TS src/security/safe-regex.ts — static analysis + 256-entry LRU cache.

Addresses denial-of-service via catastrophic backtracking in untrusted regex patterns
supplied through config or external content.
"""
from __future__ import annotations

import re
from collections import OrderedDict
from typing import NamedTuple

_CACHE_MAX = 256
_TEST_WINDOW = 2048

# LRU cache: key -> compiled regex or None
_safe_regex_cache: OrderedDict[str, re.Pattern[str] | None] = OrderedDict()


# ---------------------------------------------------------------------------
# Nested-quantifier detector (mirrors TS analyzeTokensForNestedRepetition)
# ---------------------------------------------------------------------------

class _QuantifierInfo(NamedTuple):
    consumed: int
    min_repeat: int
    max_repeat: int | None  # None = unbounded


def _read_quantifier(source: str, index: int) -> _QuantifierInfo | None:
    ch = source[index] if index < len(source) else ""
    lazy = (index + 1 < len(source) and source[index + 1] == "?")
    consumed_extra = 1 if lazy else 0

    if ch == "*":
        return _QuantifierInfo(1 + consumed_extra, 0, None)
    if ch == "+":
        return _QuantifierInfo(1 + consumed_extra, 1, None)
    if ch == "?":
        return _QuantifierInfo(1 + consumed_extra, 0, 1)
    if ch != "{":
        return None

    i = index + 1
    while i < len(source) and source[i].isdigit():
        i += 1
    if i == index + 1:
        return None

    min_repeat = int(source[index + 1 : i])
    max_repeat: int | None = min_repeat
    if i < len(source) and source[i] == ",":
        i += 1
        max_start = i
        while i < len(source) and source[i].isdigit():
            i += 1
        max_repeat = None if i == max_start else int(source[max_start:i])

    if i >= len(source) or source[i] != "}":
        return None
    i += 1
    if i < len(source) and source[i] == "?":
        i += 1

    if max_repeat is not None and max_repeat < min_repeat:
        return None

    return _QuantifierInfo(i - index, min_repeat, max_repeat)


def has_nested_repetition(source: str) -> bool:
    """
    Return True if the regex pattern contains dangerous nested repetition
    that could cause catastrophic backtracking (ReDoS).

    Conservative analysis: tokenizes without full AST; errs on the side of
    blocking patterns that look nested-repeated, even if they might be safe.
    Mirrors TS hasNestedRepetition().
    """
    # Stack of frames: each frame tracks (containsRepetition, branchMinLen, branchMaxLen, lastToken)
    # lastToken = (containsRepetition, minLen, maxLen, hasAmbiguousAlternation) | None
    frames: list[dict] = [_new_frame()]

    in_char_class = False
    i = 0
    while i < len(source):
        ch = source[i]

        if ch == "\\":
            i += 2
            _emit_simple(frames)
            continue

        if in_char_class:
            if ch == "]":
                in_char_class = False
            i += 1
            continue

        if ch == "[":
            in_char_class = True
            _emit_simple(frames)
            i += 1
            continue

        if ch == "(":
            frames.append(_new_frame())
            i += 1
            continue

        if ch == ")":
            if len(frames) > 1:
                frame = frames.pop()
                if frame["has_alternation"]:
                    _record_alternative(frame)
                group_min = frame.get("alt_min", 0) if frame["has_alternation"] else frame["branch_min"]
                group_max = frame.get("alt_max", 0) if frame["has_alternation"] else frame["branch_max"]
                has_ambig = (
                    frame["has_alternation"]
                    and frame.get("alt_min") != frame.get("alt_max")
                )
                _emit_token(frames, {
                    "contains_repetition": frame["contains_repetition"],
                    "has_ambiguous_alternation": has_ambig,
                    "min_len": group_min,
                    "max_len": group_max,
                })
            i += 1
            continue

        if ch == "|":
            frame = frames[-1]
            frame["has_alternation"] = True
            _record_alternative(frame)
            frame["branch_min"] = 0
            frame["branch_max"] = 0
            frame["last_token"] = None
            i += 1
            continue

        q = _read_quantifier(source, i)
        if q is not None:
            frame = frames[-1]
            prev = frame.get("last_token")
            if prev is None:
                i += q.consumed
                continue
            # Nested repetition: a repeated token being repeated again
            if prev["contains_repetition"]:
                return True
            # Ambiguous alternation with unbounded quantifier
            if prev.get("has_ambiguous_alternation") and q.max_repeat is None:
                return True

            prev_min = prev["min_len"]
            prev_max = prev["max_len"]
            prev["min_len"] = prev_min * q.min_repeat
            prev["max_len"] = (
                float("inf") if q.max_repeat is None else prev_max * q.max_repeat
            )
            prev["contains_repetition"] = True
            frame["contains_repetition"] = True

            frame["branch_min"] = frame["branch_min"] - prev_min + prev["min_len"]
            branch_max_base = (
                float("inf")
                if not (isinstance(frame["branch_max"], (int, float)) and isinstance(prev_max, (int, float))
                        and frame["branch_max"] != float("inf") and prev_max != float("inf"))
                else frame["branch_max"] - prev_max
            )
            frame["branch_max"] = (
                float("inf")
                if (branch_max_base == float("inf") or prev["max_len"] == float("inf"))
                else branch_max_base + prev["max_len"]
            )

            i += q.consumed
            continue

        _emit_simple(frames)
        i += 1

    return False


def _new_frame() -> dict:
    return {
        "last_token": None,
        "contains_repetition": False,
        "has_alternation": False,
        "branch_min": 0,
        "branch_max": 0,
        "alt_min": None,
        "alt_max": None,
    }


def _record_alternative(frame: dict) -> None:
    if frame["alt_min"] is None:
        frame["alt_min"] = frame["branch_min"]
        frame["alt_max"] = frame["branch_max"]
    else:
        frame["alt_min"] = min(frame["alt_min"], frame["branch_min"])
        frame["alt_max"] = max(frame["alt_max"], frame["branch_max"])


def _emit_simple(frames: list[dict]) -> None:
    _emit_token(frames, {
        "contains_repetition": False,
        "has_ambiguous_alternation": False,
        "min_len": 1,
        "max_len": 1,
    })


def _emit_token(frames: list[dict], token: dict) -> None:
    frame = frames[-1]
    frame["last_token"] = token
    if token["contains_repetition"]:
        frame["contains_repetition"] = True
    frame["branch_min"] += token["min_len"]
    frame["branch_max"] = (
        float("inf")
        if (frame["branch_max"] == float("inf") or token["max_len"] == float("inf"))
        else frame["branch_max"] + token["max_len"]
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compile_safe_regex(source: str, flags: str = "") -> re.Pattern[str] | None:
    """
    Compile a regex only if it does not contain nested repetition (ReDoS risk).

    Uses a 256-entry LRU cache keyed on `flags::source`.

    Args:
        source: Regex pattern string.
        flags: Optional flag string (e.g. "i", "m", "im").

    Returns:
        Compiled re.Pattern if safe, None if nested repetition detected or syntax error.
    """
    trimmed = source.strip()
    if not trimmed:
        return None

    cache_key = f"{flags}::{trimmed}"
    if cache_key in _safe_regex_cache:
        result = _safe_regex_cache[cache_key]
        _safe_regex_cache.move_to_end(cache_key)
        return result

    compiled: re.Pattern[str] | None = None
    if not has_nested_repetition(trimmed):
        py_flags = 0
        if "i" in flags:
            py_flags |= re.IGNORECASE
        if "m" in flags:
            py_flags |= re.MULTILINE
        if "s" in flags:
            py_flags |= re.DOTALL
        try:
            compiled = re.compile(trimmed, py_flags)
        except re.error:
            compiled = None

    _safe_regex_cache[cache_key] = compiled
    _safe_regex_cache.move_to_end(cache_key)

    if len(_safe_regex_cache) > _CACHE_MAX:
        _safe_regex_cache.popitem(last=False)

    return compiled


def test_regex_with_bounded_input(
    pattern: re.Pattern[str],
    input_str: str,
    max_window: int = _TEST_WINDOW,
) -> bool:
    """
    Test a regex against bounded input slices to prevent catastrophic backtracking
    on very long inputs. Mirrors TS testRegexWithBoundedInput().
    """
    if max_window <= 0:
        return False
    if len(input_str) <= max_window:
        return bool(pattern.search(input_str))
    if pattern.search(input_str[:max_window]):
        return True
    return bool(pattern.search(input_str[-max_window:]))


__all__ = [
    "compile_safe_regex",
    "has_nested_repetition",
    "test_regex_with_bounded_input",
]
