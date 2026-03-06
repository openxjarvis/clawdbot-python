"""Telegram two-lane reasoning stream support.

Extracts content inside <think>/<thinking>/<thought>/<antthinking> tags from the
agent's accumulated response text, routing it to a separate "reasoning" draft stream
while the cleaned answer goes to the main "answer" draft stream.

When `reasoningLevel` is:
  "off"    — reasoning blocks are stripped silently (default)
  "on"     — reasoning is stripped from the visible reply; not streamed live
  "stream" — reasoning gets its own live-updating draft bubble in the chat

Mirrors TypeScript:
  src/telegram/reasoning-lane-coordinator.ts  (splitTelegramReasoningText,
                                               TelegramReasoningStepState)
  src/telegram/lane-delivery.ts               (lane lifecycle)
  src/telegram/bot-message-dispatch.ts        (reasoningLevel resolution, wiring)
"""
from __future__ import annotations

import re
from typing import Any

# Regex that matches opening AND closing think-family tags.
# Mirrors TS extractThinkingFromTaggedStreamOutsideCode() regex.
_THINK_TAG_RE = re.compile(
    r"<\s*(?P<closing>/\s*)?(?:think(?:ing)?|thought|antthinking)\b[^<>]*>",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Text splitting
# ---------------------------------------------------------------------------

def split_telegram_reasoning_text(text: str) -> tuple[str, str]:
    """Split accumulated text into (reasoning_text, answer_text).

    Returns:
        reasoning_text: content inside think/thinking/thought/antthinking tags
        answer_text:    the remainder with all such tags (and their content) removed

    Both are stripped of leading/trailing whitespace.

    Mirrors TS splitTelegramReasoningText() / extractThinkingFromTaggedStream().
    """
    if not text:
        return "", ""

    reasoning_parts: list[str] = []
    answer_parts: list[str] = []

    pos = 0
    depth = 0
    reasoning_start = -1

    for m in _THINK_TAG_RE.finditer(text):
        is_closing = bool(m.group("closing"))
        tag_start = m.start()
        tag_end = m.end()

        if not is_closing:
            # Opening tag
            if depth == 0:
                # Text before this opening tag → answer
                answer_parts.append(text[pos:tag_start])
                reasoning_start = tag_end  # content starts after the tag
            depth += 1
            pos = tag_end
        else:
            # Closing tag
            if depth > 0:
                depth -= 1
                if depth == 0 and reasoning_start >= 0:
                    reasoning_parts.append(text[reasoning_start:tag_start])
                    reasoning_start = -1
            pos = tag_end

    # Remaining text after all matched tags
    if depth > 0 and reasoning_start >= 0:
        # Unclosed tag at end of stream — treat remainder as reasoning
        reasoning_parts.append(text[reasoning_start:])
    else:
        answer_parts.append(text[pos:])

    reasoning_text = "\n\n".join(p for p in reasoning_parts if p.strip()).strip()
    answer_text = "".join(answer_parts).strip()
    return reasoning_text, answer_text


def strip_reasoning_from_text(text: str) -> str:
    """Return only the answer portion (strips all reasoning blocks and tags).

    Convenience wrapper used for final delivery when reasoningLevel != "stream".
    """
    _, answer = split_telegram_reasoning_text(text)
    return answer


# ---------------------------------------------------------------------------
# Reasoning level config resolution
# ---------------------------------------------------------------------------

def resolve_reasoning_level(channel_config: dict) -> str:
    """Read reasoningLevel from the channel config dict.

    Returns "off" | "on" | "stream".
    Mirrors TS resolveTelegramReasoningLevel().
    """
    messages_cfg = channel_config.get("messages", {}) or {}
    # Try nested messages.reasoningLevel first, then top-level
    level = (
        messages_cfg.get("reasoningLevel")
        or messages_cfg.get("reasoning_level")
        or channel_config.get("reasoningLevel")
        or channel_config.get("reasoning_level")
        or "off"
    )
    if level in ("on", "stream"):
        return level
    return "off"


# ---------------------------------------------------------------------------
# ReasoningStepState — tracks delivery state across a multi-turn agent run
# ---------------------------------------------------------------------------

class TelegramReasoningStepState:
    """Tracks whether a reasoning block has been seen and delivered.

    States: none → hinted → delivered

    Used to buffer the final answer text until the reasoning message is
    committed, preventing the answer from arriving before the reasoning bubble.

    Mirrors TS createTelegramReasoningStepState().
    """

    def __init__(self) -> None:
        self._state: str = "none"  # "none" | "hinted" | "delivered"
        self._buffered_answer: str | None = None

    @property
    def state(self) -> str:
        return self._state

    def on_reasoning_seen(self) -> None:
        """Called when reasoning content is first detected in the stream."""
        if self._state == "none":
            self._state = "hinted"

    def on_reasoning_delivered(self) -> None:
        """Called after the reasoning draft is sent/updated."""
        self._state = "delivered"

    def should_buffer_final_answer(self) -> bool:
        """True when reasoning was announced but not yet delivered."""
        return self._state == "hinted"

    def buffer_final_answer(self, text: str) -> None:
        self._buffered_answer = text

    def take_buffered_answer(self) -> str | None:
        ans = self._buffered_answer
        self._buffered_answer = None
        return ans

    def reset_for_next_step(self) -> None:
        """Clear state between agent tool-call turns."""
        self._state = "none"
        self._buffered_answer = None


__all__ = [
    "split_telegram_reasoning_text",
    "strip_reasoning_from_text",
    "resolve_reasoning_level",
    "TelegramReasoningStepState",
]
