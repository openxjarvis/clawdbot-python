"""Block streaming — accumulate streaming text into delivery blocks.

Port of TypeScript:
  openclaw/src/auto-reply/reply/block-streaming.ts      (165 lines)
  openclaw/src/auto-reply/reply/block-reply-coalescer.ts
  openclaw/src/auto-reply/reply/block-reply-pipeline.ts

Accumulates incoming text chunks into blocks of a configured size,
then flushes them as `on_block_reply` payloads. Ensures:
  - Min-chars threshold before flush (to avoid tiny messages)
  - Max-chars hard limit (split large blocks)
  - Paragraph-boundary preference when possible
  - Idle-timeout coalescing
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Callable, Awaitable

from openclaw.markdown.fences import parse_fence_spans, is_safe_fence_break

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_BLOCK_STREAM_MIN = 800
DEFAULT_BLOCK_STREAM_MAX = 1200
DEFAULT_BLOCK_STREAM_COALESCE_IDLE_MS = 1000


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class BlockStreamingConfig:
    enabled: bool = False
    min_chars: int = DEFAULT_BLOCK_STREAM_MIN
    max_chars: int = DEFAULT_BLOCK_STREAM_MAX
    break_preference: str = "paragraph"  # "paragraph" | "newline" | "sentence"
    flush_on_paragraph: bool = False
    coalesce_idle_ms: int = DEFAULT_BLOCK_STREAM_COALESCE_IDLE_MS


@dataclass
class BlockStreamingCoalescing:
    min_chars: int = DEFAULT_BLOCK_STREAM_MIN
    max_chars: int = DEFAULT_BLOCK_STREAM_MAX
    idle_ms: int = DEFAULT_BLOCK_STREAM_COALESCE_IDLE_MS
    joiner: str = "\n"
    flush_on_enqueue: bool = False


# ---------------------------------------------------------------------------
# Block coalescer — merges small chunks into delivery-sized blocks
# ---------------------------------------------------------------------------

class BlockReplyCoalescer:
    """
    Accumulates text chunks and flushes them when min/max thresholds
    are reached or when the idle timer fires.

    Mirrors TS block-reply-coalescer.ts.
    """

    def __init__(
        self,
        config: BlockStreamingCoalescing,
        on_flush: Callable[[str], Awaitable[None]],
    ) -> None:
        self._cfg = config
        self._on_flush = on_flush
        self._buffer = ""
        self._idle_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    async def push(self, text: str) -> None:
        """Push a text chunk into the accumulation buffer."""
        async with self._lock:
            self._cancel_idle()
            self._buffer += text

            # Max-chars hard flush
            while len(self._buffer) >= self._cfg.max_chars:
                chunk, self._buffer = self._split_at(self._buffer, self._cfg.max_chars)
                await self._on_flush(chunk)

            # Flush-on-enqueue (paragraph-boundary mode)
            if self._cfg.flush_on_enqueue and len(self._buffer) >= self._cfg.min_chars:
                # Try to find paragraph boundary near min_chars
                flush_point = self._find_break_point(self._buffer, self._cfg.min_chars)
                if flush_point > 0:
                    chunk = self._buffer[:flush_point]
                    self._buffer = self._buffer[flush_point:].lstrip("\n")
                    await self._on_flush(chunk)
                    return

            # Arm idle timer for coalescing
            if self._buffer and self._cfg.idle_ms > 0:
                self._idle_task = asyncio.create_task(self._idle_flush())

    async def flush_final(self) -> None:
        """Flush any remaining buffer at end of stream."""
        async with self._lock:
            self._cancel_idle()
            if self._buffer:
                await self._on_flush(self._buffer)
                self._buffer = ""

    async def _idle_flush(self) -> None:
        await asyncio.sleep(self._cfg.idle_ms / 1000)
        async with self._lock:
            if self._buffer:
                await self._on_flush(self._buffer)
                self._buffer = ""

    def _cancel_idle(self) -> None:
        if self._idle_task and not self._idle_task.done():
            self._idle_task.cancel()
        self._idle_task = None

    @staticmethod
    def _split_at(text: str, max_chars: int) -> tuple[str, str]:
        return text[:max_chars], text[max_chars:]

    @staticmethod
    def _find_break_point(text: str, near: int) -> int:
        """Find a good break point near ``near`` chars, respecting code fences.

        Strategy:
        1. Try double-newline (paragraph break) — skip if inside a code fence.
        2. Try single newline — skip if inside a code fence.
        3. Hard-cut at *near* — if inside a fence, close+reopen it so Markdown remains valid.
        """
        if len(text) <= near:
            return len(text)

        spans = parse_fence_spans(text)

        # Prefer double-newline (paragraph break)
        pos = text.rfind("\n\n", 0, near + 200)
        if pos > near // 2 and is_safe_fence_break(spans, pos):
            return pos + 2

        # Single newline
        pos = text.rfind("\n", 0, near + 100)
        if pos > near // 2 and is_safe_fence_break(spans, pos):
            return pos + 1

        # Hard cut — safe outside fences
        if is_safe_fence_break(spans, near):
            return near

        # Inside a fence: find next newline after near that is fence-safe
        lookahead = text.find("\n", near)
        if lookahead != -1 and is_safe_fence_break(spans, lookahead):
            return lookahead + 1

        # Last resort: hard cut (caller handles fence repair if needed)
        return near


# ---------------------------------------------------------------------------
# Block streaming pipeline
# ---------------------------------------------------------------------------

class BlockStreamingPipeline:
    """
    Full pipeline: receives raw text events → coalesces → delivers via callback.

    Mirrors TS block-reply-pipeline.ts.
    """

    def __init__(
        self,
        cfg: BlockStreamingConfig,
        on_block: Callable[[str], Awaitable[None]],
    ) -> None:
        coalesce_cfg = BlockStreamingCoalescing(
            min_chars=cfg.min_chars,
            max_chars=cfg.max_chars,
            idle_ms=cfg.coalesce_idle_ms,
            flush_on_enqueue=cfg.flush_on_paragraph or cfg.break_preference == "paragraph",
        )
        self._coalescer = BlockReplyCoalescer(coalesce_cfg, on_block)
        self._enabled = cfg.enabled
        self._block_count = 0

    @property
    def block_count(self) -> int:
        return self._block_count

    async def push(self, text: str) -> None:
        if not self._enabled or not text:
            return
        self._block_count += 1
        await self._coalescer.push(text)

    async def finish(self) -> None:
        if not self._enabled:
            return
        await self._coalescer.flush_final()


# ---------------------------------------------------------------------------
# Config resolution helpers
# ---------------------------------------------------------------------------

def resolve_block_streaming_config(
    cfg: dict | None,
    channel: str | None = None,
    account_id: str | None = None,
) -> BlockStreamingConfig:
    """Resolve BlockStreamingConfig from the OpenClaw config dict."""
    cfg = cfg or {}
    agents = cfg.get("agents", {}).get("defaults", {})
    bs_raw = agents.get("blockStreaming") or {}

    if not bs_raw.get("enabled", False):
        return BlockStreamingConfig(enabled=False)

    # Per-channel coalesce overrides
    if channel:
        channel_cfg = (cfg.get(channel.lower()) or {})
        if account_id:
            account_cfg = channel_cfg.get("accounts", {}).get(account_id, {})
            coalesce = account_cfg.get("blockStreamingCoalesce") or channel_cfg.get("blockStreamingCoalesce")
        else:
            coalesce = channel_cfg.get("blockStreamingCoalesce")
        if coalesce:
            return BlockStreamingConfig(
                enabled=True,
                min_chars=int(coalesce.get("minChars", DEFAULT_BLOCK_STREAM_MIN)),
                max_chars=int(coalesce.get("maxChars", DEFAULT_BLOCK_STREAM_MAX)),
                break_preference=coalesce.get("breakPreference", "paragraph"),
                flush_on_paragraph=bool(coalesce.get("flushOnParagraph", False)),
                coalesce_idle_ms=int(coalesce.get("idleMs", DEFAULT_BLOCK_STREAM_COALESCE_IDLE_MS)),
            )

    return BlockStreamingConfig(
        enabled=True,
        min_chars=int(bs_raw.get("minChars", DEFAULT_BLOCK_STREAM_MIN)),
        max_chars=int(bs_raw.get("maxChars", DEFAULT_BLOCK_STREAM_MAX)),
        break_preference=bs_raw.get("breakPreference", "paragraph"),
        flush_on_paragraph=bool(bs_raw.get("flushOnParagraph", False)),
        coalesce_idle_ms=DEFAULT_BLOCK_STREAM_COALESCE_IDLE_MS,
    )
