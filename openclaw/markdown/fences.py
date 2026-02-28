"""Fence span detection for safe Markdown splitting.

Mirrors TS openclaw/src/markdown/fences.ts — parseFenceSpans(), isSafeFenceBreak().

Used by BlockReplyCoalescer to avoid splitting inside open code fences which
would produce broken Markdown.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_FENCE_RE = re.compile(r"^( {0,3})(`{3,}|~{3,})(.*)$")


@dataclass
class FenceSpan:
    """A closed or unclosed code-fence region within a buffer.

    ``start`` is the offset of the opening fence line's first character.
    ``end`` is the offset just after the closing fence (or buffer length if unclosed).
    """
    start: int
    end: int
    open_line: str
    marker: str
    indent: str


def parse_fence_spans(buffer: str) -> list[FenceSpan]:
    """Parse all (possibly unclosed) code-fence spans in *buffer*.

    Mirrors TS ``parseFenceSpans(buffer: string): FenceSpan[]``.

    A code fence is an optional indent of up to 3 spaces followed by 3+ backticks
    or 3+ tildes.  Closing requires the same marker character and at least as many
    characters.

    Returns a list of FenceSpan objects ordered by ``start`` offset.
    """
    spans: list[FenceSpan] = []
    open_span: dict | None = None

    offset = 0
    while offset <= len(buffer):
        next_nl = buffer.find("\n", offset)
        line_end = len(buffer) if next_nl == -1 else next_nl
        line = buffer[offset:line_end]

        m = _FENCE_RE.match(line)
        if m:
            indent = m.group(1)
            marker = m.group(2)
            marker_char = marker[0]
            marker_len = len(marker)

            if open_span is None:
                open_span = {
                    "start": offset,
                    "marker_char": marker_char,
                    "marker_len": marker_len,
                    "open_line": line,
                    "marker": marker,
                    "indent": indent,
                }
            elif open_span["marker_char"] == marker_char and marker_len >= open_span["marker_len"]:
                spans.append(FenceSpan(
                    start=open_span["start"],
                    end=line_end,
                    open_line=open_span["open_line"],
                    marker=open_span["marker"],
                    indent=open_span["indent"],
                ))
                open_span = None

        if next_nl == -1:
            break
        offset = next_nl + 1

    if open_span is not None:
        spans.append(FenceSpan(
            start=open_span["start"],
            end=len(buffer),
            open_line=open_span["open_line"],
            marker=open_span["marker"],
            indent=open_span["indent"],
        ))

    return spans


def find_fence_span_at(spans: list[FenceSpan], index: int) -> FenceSpan | None:
    """Return the first FenceSpan that strictly contains *index*, or None.

    Mirrors TS ``findFenceSpanAt()``.
    """
    for span in spans:
        if span.start < index < span.end:
            return span
    return None


def is_safe_fence_break(spans: list[FenceSpan], index: int) -> bool:
    """Return True if splitting the buffer at *index* does not break a code fence.

    Mirrors TS ``isSafeFenceBreak(spans, index)``.
    """
    return find_fence_span_at(spans, index) is None
