"""Memory flush — pre-compaction memory persistence.

Port of TypeScript:
  openclaw/src/auto-reply/reply/memory-flush.ts  (144 lines)

Fires a synthetic agent turn just before context compaction to let
the agent persist important memories to disk. This runs BEFORE the
compactor truncates the session, so the agent can write to
memory/YYYY-MM-DD.md files.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from ..tokens import SILENT_REPLY_TOKEN

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (match TS defaults)
# ---------------------------------------------------------------------------

DEFAULT_MEMORY_FLUSH_SOFT_TOKENS = 4_000

DEFAULT_MEMORY_FLUSH_PROMPT = " ".join([
    "Pre-compaction memory flush.",
    "Store durable memories now (use memory/YYYY-MM-DD.md; create memory/ if needed).",
    "IMPORTANT: If the file already exists, APPEND new content only and do not overwrite existing entries.",
    f"If nothing to store, reply with {SILENT_REPLY_TOKEN}.",
])

DEFAULT_MEMORY_FLUSH_SYSTEM_PROMPT = " ".join([
    "Pre-compaction memory flush turn.",
    "The session is near auto-compaction; capture durable memories to disk.",
    f"You may reply, but usually {SILENT_REPLY_TOKEN} is correct.",
])


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class MemoryFlushSettings:
    enabled: bool = False
    soft_threshold_tokens: int = DEFAULT_MEMORY_FLUSH_SOFT_TOKENS
    prompt: str = DEFAULT_MEMORY_FLUSH_PROMPT
    system_prompt: str = DEFAULT_MEMORY_FLUSH_SYSTEM_PROMPT


@dataclass
class MemoryFlushResult:
    flushed: bool = False
    silent: bool = False
    reply_text: str | None = None
    tokens_before: int = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_date_stamp(now_ms: int, timezone: str = "UTC") -> str:
    """Format date as YYYY-MM-DD in the given timezone."""
    try:
        import zoneinfo
        from datetime import datetime, timezone as tz_mod
        dt = datetime.fromtimestamp(now_ms / 1000, tz=tz_mod.utc)
        local = dt.astimezone(zoneinfo.ZoneInfo(timezone))
        return local.strftime("%Y-%m-%d")
    except Exception:
        return time.strftime("%Y-%m-%d", time.gmtime(now_ms / 1000))


def resolve_memory_flush_prompt_for_run(
    prompt: str,
    cfg: dict | None = None,
    now_ms: int | None = None,
) -> str:
    """Interpolate date tokens and append current-time line."""
    if now_ms is None:
        now_ms = int(time.time() * 1000)
    cfg = cfg or {}

    timezone = (
        cfg.get("agents", {}).get("defaults", {}).get("timezone")
        or cfg.get("timezone")
        or "UTC"
    )
    date_stamp = _format_date_stamp(now_ms, timezone)
    with_date = prompt.replace("YYYY-MM-DD", date_stamp).rstrip()

    time_line = f"Current time: {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(now_ms / 1000))} UTC"

    if not with_date:
        return time_line
    if "Current time:" in with_date:
        return with_date
    return f"{with_date}\n{time_line}"


def resolve_memory_flush_settings(cfg: dict | None, agent_cfg: dict | None) -> MemoryFlushSettings:
    """Resolve memory flush settings from config."""
    cfg = cfg or {}
    agent_cfg = agent_cfg or {}
    agents_defaults = cfg.get("agents", {}).get("defaults", {})

    mf_raw = (
        agent_cfg.get("memoryFlush")
        or agents_defaults.get("memoryFlush")
        or {}
    )
    if not mf_raw:
        return MemoryFlushSettings(enabled=False)

    enabled = bool(mf_raw.get("enabled", False))
    threshold = int(mf_raw.get("softThresholdTokens", DEFAULT_MEMORY_FLUSH_SOFT_TOKENS))
    prompt = str(mf_raw.get("prompt", DEFAULT_MEMORY_FLUSH_PROMPT))
    sys_prompt = str(mf_raw.get("systemPrompt", DEFAULT_MEMORY_FLUSH_SYSTEM_PROMPT))

    return MemoryFlushSettings(
        enabled=enabled,
        soft_threshold_tokens=threshold,
        prompt=prompt,
        system_prompt=sys_prompt,
    )


def should_trigger_memory_flush(
    settings: MemoryFlushSettings,
    context_tokens: int,
    max_context_tokens: int,
) -> bool:
    """Return True if context is close enough to the limit to trigger a flush."""
    if not settings.enabled:
        return False
    available = max_context_tokens - context_tokens
    return available <= settings.soft_threshold_tokens


# ---------------------------------------------------------------------------
# Main flush function
# ---------------------------------------------------------------------------

async def run_memory_flush(
    session_key: str,
    settings: MemoryFlushSettings,
    cfg: dict | None = None,
    runtime: Any = None,
    now_ms: int | None = None,
) -> MemoryFlushResult:
    """
    Run a single pre-compaction memory-flush agent turn.

    Mirrors TS runMemoryFlush():
      1. Build the flush prompt (interpolate date/time)
      2. Run a short agent turn via AgentSession
      3. If reply is SILENT_REPLY_TOKEN, skip output
      4. Return MemoryFlushResult
    """
    if not settings.enabled:
        return MemoryFlushResult(flushed=False)

    prompt = resolve_memory_flush_prompt_for_run(settings.prompt, cfg=cfg, now_ms=now_ms)

    try:
        text = await _run_flush_turn(
            session_key=session_key,
            message=prompt,
            system_prompt=settings.system_prompt,
            cfg=cfg or {},
            runtime=runtime,
        )
    except Exception as exc:
        logger.error(f"memory_flush: agent turn failed: {exc}", exc_info=True)
        return MemoryFlushResult(flushed=False)

    if not text:
        return MemoryFlushResult(flushed=True, silent=True)

    # Check for silent token
    silent = _is_silent_reply(text)
    return MemoryFlushResult(
        flushed=True,
        silent=silent,
        reply_text=None if silent else text,
    )


async def _run_flush_turn(
    session_key: str,
    message: str,
    system_prompt: str,
    cfg: dict,
    runtime: Any,
) -> str:
    """Run a single agent turn for memory flush."""
    try:
        from pi_mono.runtime.agent_session import AgentSession  # type: ignore[import]
        agent_session = AgentSession(
            session_key=session_key,
            runtime=runtime,
            system_prompt=system_prompt,
        )
        events: list = []
        unsub = agent_session.subscribe(events.append)
        try:
            await agent_session.prompt(message)
        finally:
            unsub()
        return _extract_text_from_events(events)
    except ImportError:
        pass

    # Fallback: use gateway runtime
    try:
        from openclaw.agents.agent_session import AgentSession  # type: ignore[import]
        from openclaw.agents.session import Session
        session = Session(session_id=session_key)
        agent_session = AgentSession(
            session_key=session_key,
            session_id=session_key,
            session=session,
            runtime=runtime,
            system_prompt=system_prompt,
            max_iterations=3,
        )
        events: list = []
        unsub = agent_session.subscribe(events.append)
        try:
            await agent_session.prompt(message)
        finally:
            unsub()
        return _extract_text_from_events(events)
    except Exception as exc:
        logger.warning(f"memory flush turn failed: {exc}")
        return ""


def _extract_text_from_events(events: list) -> str:
    text = ""
    for event in events:
        ev_type = ""
        if hasattr(event, "type"):
            v = event.type
            ev_type = v.value if hasattr(v, "value") else str(v)
        elif isinstance(event, dict):
            ev_type = str(event.get("type", ""))

        if ev_type in ("agent.text", "text", "delta"):
            if isinstance(event, dict):
                delta = event.get("text") or event.get("delta", {}).get("text", "") or ""
            elif hasattr(event, "data"):
                d = event.data or {}
                delta = d.get("text") or d.get("delta", {}).get("text", "") or ""
            else:
                delta = ""
            text += delta
    return text


def _is_silent_reply(text: str) -> bool:
    if not text:
        return True
    stripped = text.strip()
    return stripped.startswith(SILENT_REPLY_TOKEN) or stripped.endswith(SILENT_REPLY_TOKEN)
