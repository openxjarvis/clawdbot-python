"""
Block reply coalescer - implements minChars/maxChars/idleMs logic

Mirrors TS block-reply-coalescer.ts functionality for merging block replies
based on character count and idle timing.

P1-5: Slack block_streaming support
"""
import asyncio
import logging
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


class BlockReplyCoalescer:
    """
    Coalesces block replies based on minChars, maxChars, idleMs.
    
    Mirrors TS BlockReplyCoalescer from openclaw/src/auto-reply/reply/block-reply-coalescer.ts
    
    Logic:
    - Buffer payloads until minChars is reached
    - Flush immediately when maxChars is exceeded
    - Flush after idleMs of inactivity
    - Force flush on finalize
    """
    
    def __init__(
        self,
        min_chars: int,
        max_chars: int,
        idle_ms: int,
        on_flush: Callable[[dict[str, Any]], Awaitable[None]],
        should_abort: Callable[[], bool],
    ):
        """
        Initialize coalescer.
        
        Args:
            min_chars: Minimum characters before flushing (unless forced)
            max_chars: Maximum characters - flush immediately when reached
            idle_ms: Idle timeout in milliseconds
            on_flush: Callback to send merged payload
            should_abort: Function to check if should abort
        """
        self.min_chars = max(1, min_chars)
        self.max_chars = max(self.min_chars, max_chars)
        self.idle_ms = max(0, idle_ms)
        self.on_flush = on_flush
        self.should_abort = should_abort
        
        self.buffer: list[dict[str, Any]] = []
        self.buffer_text = ""
        self.idle_timer: asyncio.Task | None = None
        self.flushing = False
    
    async def enqueue(self, payload: dict[str, Any]) -> None:
        """
        Enqueue a payload for coalescing.
        
        Args:
            payload: Reply payload with 'text' field
        """
        if self.should_abort():
            return
        
        # Add to buffer
        self.buffer.append(payload)
        self.buffer_text += payload.get("text", "")
        
        # Cancel existing idle timer
        if self.idle_timer:
            self.idle_timer.cancel()
            self.idle_timer = None
        
        # Check if we should flush immediately (maxChars reached)
        if len(self.buffer_text) >= self.max_chars:
            await self._flush(force=False)
        else:
            # Schedule idle flush
            if self.idle_ms > 0:
                self.idle_timer = asyncio.create_task(self._idle_flush())
    
    async def _idle_flush(self) -> None:
        """Flush after idle timeout"""
        try:
            await asyncio.sleep(self.idle_ms / 1000.0)
            await self._flush(force=False)
        except asyncio.CancelledError:
            # Timer cancelled, ignore
            pass
    
    async def _flush(self, force: bool = False) -> None:
        """
        Flush buffered payloads.
        
        Args:
            force: If True, flush regardless of minChars requirement
        """
        if self.flushing or self.should_abort():
            return
        
        # Check minChars requirement (unless forced)
        if not force and len(self.buffer_text) < self.min_chars:
            return
        
        if not self.buffer:
            return
        
        self.flushing = True
        
        try:
            # Merge payloads
            merged_payload = self._merge_payloads(self.buffer)
            
            # Send
            await self.on_flush(merged_payload)
            
            # Clear buffer
            self.buffer.clear()
            self.buffer_text = ""
            
        except Exception as e:
            logger.error(f"[coalescer] Error flushing block reply: {e}", exc_info=True)
        finally:
            self.flushing = False
            # Cancel idle timer if still running
            if self.idle_timer:
                self.idle_timer.cancel()
                self.idle_timer = None
    
    def _merge_payloads(self, payloads: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Merge multiple payloads into one.
        
        Args:
            payloads: List of payloads to merge
        
        Returns:
            Merged payload with combined text
        """
        if not payloads:
            return {}
        
        # Start with first payload as base
        merged = payloads[0].copy()
        
        # Merge text from all payloads
        merged["text"] = "".join(p.get("text", "") for p in payloads)
        
        # Merge other fields if needed (audioChunks, etc.)
        if any("audioChunks" in p for p in payloads):
            audio_chunks = []
            for p in payloads:
                if "audioChunks" in p:
                    audio_chunks.extend(p["audioChunks"])
            if audio_chunks:
                merged["audioChunks"] = audio_chunks
        
        return merged
    
    async def flush_final(self) -> None:
        """Force flush any remaining payloads"""
        await self._flush(force=True)
