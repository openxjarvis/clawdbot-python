"""Lane segment splitting for Telegram two-lane delivery.

Extends reasoning.py with lane-oriented data structures for use in
bot-message-dispatch and lane-delivery integration.

Mirrors TypeScript:
  src/telegram/bot-message-dispatch.ts (splitTextIntoLaneSegments, SplitLaneSegment)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from openclaw.channels.telegram.reasoning import split_telegram_reasoning_text

LaneName = Literal["answer", "reasoning"]


@dataclass
class LaneSegment:
    """A segment of text destined for a specific lane.
    
    Mirrors TS SplitLaneSegment.
    """
    lane: LaneName
    text: str


@dataclass
class SplitLaneSegmentsResult:
    """Result of splitting text into lane segments.
    
    Mirrors TS SplitLaneSegmentsResult.
    """
    segments: list[LaneSegment]
    suppressed_reasoning_only: bool


def split_text_into_lane_segments(
    text: str | None,
    reasoning_level: str = "off",
) -> SplitLaneSegmentsResult:
    """Split text into lane segments based on reasoning level.
    
    Mirrors TS splitTextIntoLaneSegments from bot-message-dispatch.ts.
    
    Args:
        text: The text to split (may contain <think> tags).
        reasoning_level: "off" | "on" | "stream"
            - "off": suppress reasoning entirely
            - "on": strip reasoning but don't stream
            - "stream": send reasoning to separate lane
    
    Returns:
        SplitLaneSegmentsResult with segments for each lane and a flag
        indicating if only reasoning was present and suppressed.
    """
    if not text:
        return SplitLaneSegmentsResult(segments=[], suppressed_reasoning_only=False)
    
    reasoning_text, answer_text = split_telegram_reasoning_text(text)
    
    segments: list[LaneSegment] = []
    suppress_reasoning = reasoning_level == "off"
    
    # Add reasoning segment if present and not suppressed
    if reasoning_text and not suppress_reasoning:
        segments.append(LaneSegment(lane="reasoning", text=reasoning_text))
    
    # Add answer segment if present
    if answer_text:
        segments.append(LaneSegment(lane="answer", text=answer_text))
    
    # Check if we suppressed reasoning and there's no answer
    suppressed_reasoning_only = bool(reasoning_text) and suppress_reasoning and not answer_text
    
    return SplitLaneSegmentsResult(
        segments=segments,
        suppressed_reasoning_only=suppressed_reasoning_only,
    )


__all__ = [
    "LaneName",
    "LaneSegment",
    "SplitLaneSegmentsResult",
    "split_text_into_lane_segments",
]
