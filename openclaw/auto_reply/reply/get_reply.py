"""Get reply — coordinates reply generation.

Port of TypeScript:
  openclaw/src/auto-reply/reply/get-reply.ts
  openclaw/src/auto-reply/reply/get-reply-run.ts
  openclaw/src/auto-reply/reply/get-reply-directives.ts (simplified)

Flow:
  1. Build session key + agent config from cfg
  2. Detect and run commands (/new, /reset, /compact, /help, …)
  3. Resolve inline directives ([[silent]], [[reply_to:ID]], think level, model)
  4. Run agent turn via AgentSession.prompt()
  5. Return accumulated ReplyPayload(s)
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Reply payload type (mirrors TS ReplyPayload)
# ---------------------------------------------------------------------------

@dataclass
class ReplyPayload:
    text: str | None = None
    media_url: str | None = None
    media_urls: list[str] | None = None
    audio_as_voice: bool | None = None
    silent: bool | None = None
    reply_to_id: str | None = None


# ---------------------------------------------------------------------------
# Abort / stop detection
# ---------------------------------------------------------------------------

_ABORT_TRIGGERS = {"stop", "esc", "abort", "wait", "exit", "interrupt"}
_ABORT_MEMORY: dict[str, bool] = {}
_ABORT_MEMORY_MAX = 2000


def is_abort_trigger(text: str | None) -> bool:
    if not text:
        return False
    return text.strip().lower() in _ABORT_TRIGGERS


def is_abort_request_text(text: str | None) -> bool:
    if not text:
        return False
    normalized = text.strip()
    if not normalized:
        return False
    return normalized.lower() == "/stop" or is_abort_trigger(normalized)


def get_abort_memory(key: str) -> bool:
    return _ABORT_MEMORY.get(key.strip(), False)


def set_abort_memory(key: str, value: bool) -> None:
    k = key.strip()
    if not k:
        return
    if not value:
        _ABORT_MEMORY.pop(k, None)
        return
    _ABORT_MEMORY.pop(k, None)
    _ABORT_MEMORY[k] = True
    if len(_ABORT_MEMORY) > _ABORT_MEMORY_MAX:
        oldest = next(iter(_ABORT_MEMORY))
        del _ABORT_MEMORY[oldest]


def format_abort_reply_text(stopped_subagents: int = 0) -> str:
    if stopped_subagents <= 0:
        return "Agent was aborted."
    label = "sub-agent" if stopped_subagents == 1 else "sub-agents"
    return f"Agent was aborted. Stopped {stopped_subagents} {label}."


def try_fast_abort(ctx: Any) -> dict[str, Any]:
    """Fast abort detection. Returns {handled, aborted}."""
    body = (
        getattr(ctx, "CommandBody", None)
        or getattr(ctx, "RawBody", None)
        or getattr(ctx, "Body", "")
        or ""
    )
    if not is_abort_request_text(body.strip()):
        return {"handled": False, "aborted": False}
    session_key = getattr(ctx, "SessionKey", None)
    if session_key:
        # Try to abort via the gateway's embedded pi runner
        try:
            from openclaw.gateway.chat_abort import abort_chat_runs_for_session_key
            abort_chat_runs_for_session_key(None, session_key, "user_stop")
        except Exception:
            pass
        set_abort_memory(session_key, True)
    return {"handled": True, "aborted": True, "stopped_subagents": 0}


# ---------------------------------------------------------------------------
# Inline directive parsing (mirrors directive-handling.parse.ts)
# ---------------------------------------------------------------------------

_SILENT_RE = re.compile(r"\[\[silent\]\]", re.IGNORECASE)
_REPLY_TO_RE = re.compile(r"\[\[reply_to:([^\]]+)\]\]", re.IGNORECASE)
_THINK_RE = re.compile(r"\[\[think(?::(low|medium|high|off))?\]\]", re.IGNORECASE)
_MODEL_RE = re.compile(r"\[\[model:([^\]]+)\]\]", re.IGNORECASE)


@dataclass
class InlineDirectives:
    silent: bool = False
    reply_to_id: str | None = None
    think_level: str | None = None
    model_override: str | None = None
    cleaned_body: str = ""


def parse_inline_directives(body: str) -> InlineDirectives:
    silent = bool(_SILENT_RE.search(body))
    reply_to_m = _REPLY_TO_RE.search(body)
    reply_to_id = reply_to_m.group(1).strip() if reply_to_m else None
    think_m = _THINK_RE.search(body)
    think_level = think_m.group(1) if (think_m and think_m.group(1)) else (None if not think_m else "medium")
    model_m = _MODEL_RE.search(body)
    model_override = model_m.group(1).strip() if model_m else None

    cleaned = body
    for pattern in (_SILENT_RE, _REPLY_TO_RE, _THINK_RE, _MODEL_RE):
        cleaned = pattern.sub("", cleaned)
    cleaned = cleaned.strip()

    return InlineDirectives(
        silent=silent,
        reply_to_id=reply_to_id,
        think_level=think_level,
        model_override=model_override,
        cleaned_body=cleaned,
    )


# ---------------------------------------------------------------------------
# Session reset detection
# ---------------------------------------------------------------------------

_RESET_RE = re.compile(r"^/(?:new|reset)(?:\s+(.*))?$", re.IGNORECASE)


def detect_reset_command(body: str) -> tuple[bool, str]:
    """Returns (is_reset, post_reset_message)."""
    m = _RESET_RE.match(body.strip())
    if not m:
        return False, ""
    return True, (m.group(1) or "").strip()


# ---------------------------------------------------------------------------
# Command routing — delegates to commands package
# ---------------------------------------------------------------------------

async def run_command(
    command_name: str,
    args_text: str,
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
    runtime: Any,
) -> ReplyPayload | None:
    """Route a slash-command to the appropriate handler."""
    try:
        from openclaw.auto_reply.reply.commands import dispatch_command
        return await dispatch_command(command_name, args_text, ctx, cfg, session_key, runtime)
    except ImportError:
        pass
    except Exception as exc:
        logger.warning(f"Command /{command_name} failed: {exc}")
    return ReplyPayload(text=f"Unknown command: /{command_name}")


# ---------------------------------------------------------------------------
# Agent turn execution
# ---------------------------------------------------------------------------

async def run_agent_turn(
    message: str,
    session_key: str,
    cfg: dict[str, Any],
    runtime: Any,
    *,
    think_level: str | None = None,
    model_override: str | None = None,
    images: list[str] | None = None,
    on_block_reply: Callable[[ReplyPayload], Awaitable[None]] | None = None,
    on_tool_result: Callable[[ReplyPayload], Awaitable[None]] | None = None,
) -> ReplyPayload | None:
    """
    Run a single agent turn and return the final reply.

    Mirrors TS runReplyAgent() — calls AgentSession.prompt() and accumulates
    events into ReplyPayload deliveries.
    """
    try:
        from pi_mono.runtime.agent_session import AgentSession
    except ImportError:
        try:
            from openclaw.pi_runtime import get_pi_runtime
            pi_rt = get_pi_runtime()
            if pi_rt is not None:
                result = await pi_rt.run_turn_simple(session_key, message)
                return ReplyPayload(text=result.get("text") or result.get("output_text") or "")
        except Exception as exc:
            logger.error(f"run_agent_turn: pi_runtime fallback failed: {exc}")
        # Last resort — use the gateway runtime directly
        return await _run_with_gateway_runtime(message, session_key, cfg, runtime, images=images,
                                               on_block_reply=on_block_reply,
                                               on_tool_result=on_tool_result)

    return await _run_with_agent_session(
        message=message,
        session_key=session_key,
        cfg=cfg,
        runtime=runtime,
        think_level=think_level,
        model_override=model_override,
        images=images,
        on_block_reply=on_block_reply,
        on_tool_result=on_tool_result,
    )


async def _run_with_agent_session(
    message: str,
    session_key: str,
    cfg: dict[str, Any],
    runtime: Any,
    *,
    think_level: str | None = None,
    model_override: str | None = None,
    images: list[str] | None = None,
    on_block_reply: Callable[[ReplyPayload], Awaitable[None]] | None = None,
    on_tool_result: Callable[[ReplyPayload], Awaitable[None]] | None = None,
) -> ReplyPayload | None:
    """Run via pi_mono AgentSession (canonical path)."""
    try:
        from pi_mono.runtime.agent_session import AgentSession  # type: ignore[import]
    except ImportError:
        return await _run_with_gateway_runtime(
            message, session_key, cfg, runtime, images=images,
            on_block_reply=on_block_reply, on_tool_result=on_tool_result,
        )

    # Build session from gateway deps
    tools = _resolve_tools(runtime)
    system_prompt = _resolve_system_prompt(cfg)

    agent_session = AgentSession(
        session_key=session_key,
        runtime=_resolve_runtime_instance(runtime, cfg, model_override),
        tools=tools,
        system_prompt=system_prompt,
    )

    accumulated_text = ""
    events: list[Any] = []

    def on_event(event: Any) -> None:
        events.append(event)

    unsub = agent_session.subscribe(on_event)
    try:
        await agent_session.prompt(message, images=images)
    finally:
        unsub()

    # Process events
    for event in events:
        ev_type = _get_event_type(event)
        if ev_type in ("agent.text", "text", "delta"):
            delta = _get_event_text(event)
            if delta:
                accumulated_text += delta
                if on_block_reply:
                    await on_block_reply(ReplyPayload(text=delta))
        elif ev_type in ("tool_result", "agent.tool_result"):
            result_text = _get_event_text(event)
            if result_text and on_tool_result:
                await on_tool_result(ReplyPayload(text=result_text))

    if accumulated_text:
        return ReplyPayload(text=accumulated_text)
    return None


async def _run_with_gateway_runtime(
    message: str,
    session_key: str,
    cfg: dict[str, Any],
    runtime: Any,
    *,
    images: list[str] | None = None,
    on_block_reply: Callable[[ReplyPayload], Awaitable[None]] | None = None,
    on_tool_result: Callable[[ReplyPayload], Awaitable[None]] | None = None,
) -> ReplyPayload | None:
    """Fallback: run using gateway AgentSession/MultiProviderRuntime directly."""
    try:
        from openclaw.agents.agent_session import AgentSession  # type: ignore[import]
    except ImportError:
        logger.error("run_agent_turn: no usable AgentSession found")
        return ReplyPayload(text="[Agent unavailable]")

    # Resolve or create a session object
    session = _get_or_create_session(session_key, runtime)
    tools = _resolve_tools(runtime)
    system_prompt = _resolve_system_prompt(cfg)

    agent_session = AgentSession(
        session_key=session_key,
        session_id=getattr(session, "session_id", session_key),
        session=session,
        runtime=_resolve_runtime_instance(runtime, cfg, None),
        tools=tools,
        system_prompt=system_prompt,
        max_iterations=10,
        max_tokens=4096,
    )

    accumulated_text = ""
    events: list[Any] = []

    def on_event(event: Any) -> None:
        events.append(event)

    unsub = agent_session.subscribe(on_event)
    try:
        await agent_session.prompt(message, images=images)
    finally:
        unsub()

    for event in events:
        ev_type = _get_event_type(event)
        if ev_type in ("agent.text", "text", "delta"):
            delta = _get_event_text(event)
            if delta:
                accumulated_text += delta
                if on_block_reply:
                    await on_block_reply(ReplyPayload(text=delta))

    if accumulated_text:
        return ReplyPayload(text=accumulated_text)
    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_event_type(event: Any) -> str:
    if hasattr(event, "type"):
        v = event.type
        return v.value if hasattr(v, "value") else str(v)
    if isinstance(event, dict):
        return str(event.get("type", ""))
    return ""


def _get_event_text(event: Any) -> str:
    if isinstance(event, dict):
        return (
            event.get("text")
            or event.get("delta", {}).get("text", "")
            or event.get("content", "")
            or ""
        )
    if hasattr(event, "data"):
        d = event.data or {}
        return (
            d.get("text")
            or d.get("delta", {}).get("text", "")
            or d.get("content", "")
            or ""
        )
    return ""


def _resolve_tools(runtime: Any) -> list:
    if runtime is None:
        return []
    return getattr(runtime, "tools", []) or []


def _resolve_system_prompt(cfg: dict[str, Any]) -> str | None:
    if not cfg:
        return None
    return cfg.get("system_prompt") or cfg.get("agents", {}).get("defaults", {}).get("systemPrompt")


def _resolve_runtime_instance(runtime: Any, cfg: dict[str, Any], model_override: str | None) -> Any:
    if runtime is None:
        return None
    # If runtime is already a provider-level runtime, return it
    if hasattr(runtime, "prompt") or hasattr(runtime, "run_turn"):
        return runtime
    # If it wraps a runtime
    inner = getattr(runtime, "runtime", None) or getattr(runtime, "_runtime", None)
    return inner or runtime


def _get_or_create_session(session_key: str, runtime: Any) -> Any:
    if runtime and hasattr(runtime, "session_manager"):
        sm = runtime.session_manager
        if sm and hasattr(sm, "get_or_create_session_by_key"):
            return sm.get_or_create_session_by_key(session_key)
    # Create a minimal Session object
    try:
        from openclaw.agents.session import Session
        return Session(session_id=session_key)
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Main public function: get_reply_from_config
# ---------------------------------------------------------------------------

async def get_reply_from_config(
    ctx: Any,
    opts: dict[str, Any] | None = None,
    cfg: dict[str, Any] | None = None,
    *,
    runtime: Any = None,
    on_block_reply: Callable[[ReplyPayload], Awaitable[None]] | None = None,
    on_tool_result: Callable[[ReplyPayload], Awaitable[None]] | None = None,
) -> ReplyPayload | list[ReplyPayload] | None:
    """
    Main entry point for reply generation.

    Mirrors TS getReplyFromConfig():
      1. Resolve session key + config
      2. Detect /reset (session clear) or /stop (abort)
      3. Parse inline directives ([[silent]], [[reply_to:…]], [[model:…]])
      4. Detect slash commands → run command handler
      5. Run agent turn via AgentSession.prompt()

    Returns one or more ReplyPayload, or None if silent/no output.
    """
    opts = opts or {}
    cfg = cfg or {}

    session_key: str = getattr(ctx, "SessionKey", "") or ""
    body: str = (
        getattr(ctx, "BodyForCommands", None)
        or getattr(ctx, "BodyForAgent", None)
        or getattr(ctx, "Body", "")
        or ""
    )

    # ------------------------------------------------------------------
    # 1. Silent token fast-exit (e.g. [[silent]])
    # ------------------------------------------------------------------
    from openclaw.auto_reply.tokens import SILENT_REPLY_TOKEN  # type: ignore[import]
    if SILENT_REPLY_TOKEN and SILENT_REPLY_TOKEN in body:
        return None

    # ------------------------------------------------------------------
    # 2. Session reset (/new, /reset)
    # ------------------------------------------------------------------
    is_reset, post_reset_body = detect_reset_command(body)
    if is_reset:
        await _handle_session_reset(session_key, cfg)
        if not post_reset_body:
            return ReplyPayload(text="Session reset. How can I help you?")
        # Continue with the post-reset message
        body = post_reset_body

    # ------------------------------------------------------------------
    # 3. Parse inline directives
    # ------------------------------------------------------------------
    directives = parse_inline_directives(body)
    if directives.silent:
        return None
    effective_body = directives.cleaned_body or body

    # ------------------------------------------------------------------
    # 4. Command detection — matches TS hasControlCommand path
    # ------------------------------------------------------------------
    cmd_pattern = re.compile(r"^/([a-zA-Z0-9_-]+)(?:\s+(.*))?$", re.DOTALL)
    cmd_match = cmd_pattern.match(effective_body.strip())
    if cmd_match:
        cmd_name = cmd_match.group(1).lower()
        cmd_args = (cmd_match.group(2) or "").strip()
        result = await run_command(cmd_name, cmd_args, ctx, cfg, session_key, runtime)
        if result is not None:
            return result

    # ------------------------------------------------------------------
    # 5. Skill commands (/skill:name)
    # ------------------------------------------------------------------
    skill_pattern = re.compile(r"^/skill:([a-zA-Z0-9_-]+)(?:\s+(.*))?$", re.DOTALL)
    skill_match = skill_pattern.match(effective_body.strip())
    if skill_match:
        skill_name = skill_match.group(1)
        skill_args = (skill_match.group(2) or "").strip()
        try:
            from openclaw.auto_reply.skill_commands import run_skill_command
            result = await run_skill_command(skill_name, skill_args, ctx, cfg)
            if result is not None:
                return ReplyPayload(text=str(result))
        except Exception as exc:
            logger.warning(f"Skill command /{skill_name} failed: {exc}")

    # ------------------------------------------------------------------
    # 6. Regular agent turn
    # ------------------------------------------------------------------
    images = getattr(ctx, "MediaUrls", None) or []
    images = [i for i in (images or []) if i]

    final = await run_agent_turn(
        message=effective_body,
        session_key=session_key,
        cfg=cfg,
        runtime=runtime,
        think_level=directives.think_level,
        model_override=directives.model_override,
        images=images if images else None,
        on_block_reply=on_block_reply,
        on_tool_result=on_tool_result,
    )

    if directives.reply_to_id and final:
        final.reply_to_id = directives.reply_to_id

    return final


async def _handle_session_reset(session_key: str, cfg: dict[str, Any]) -> None:
    """Clear the session store entry for session_key."""
    if not session_key:
        return
    try:
        from openclaw.agents.session_manager import get_session_manager
        sm = get_session_manager()
        if sm and hasattr(sm, "reset_session"):
            await sm.reset_session(session_key)
            return
    except Exception:
        pass
    try:
        from openclaw.agents.sessions import reset_session_by_key
        reset_session_by_key(session_key)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Legacy compatibility shim — old callers used get_reply(context, dispatcher, runtime)
# ---------------------------------------------------------------------------

async def get_reply(
    context: Any,
    dispatcher: Any,
    runtime: Any,
    config: dict[str, Any] | None = None,
) -> None:
    """
    Legacy compatibility wrapper.

    Old code called:
        await get_reply(context, dispatcher, runtime, config)

    New code uses:
        await get_reply_from_config(ctx, cfg=config, runtime=runtime,
                                    on_block_reply=..., on_tool_result=...)
    """
    config = config or {}

    async def _on_block(payload: ReplyPayload) -> None:
        if payload.text:
            await dispatcher.send_block_reply(payload.text)

    async def _on_tool(payload: ReplyPayload) -> None:
        if payload.text:
            await dispatcher.send_tool_result("", payload.text)

    result = await get_reply_from_config(
        context,
        cfg=config,
        runtime=runtime,
        on_block_reply=_on_block,
        on_tool_result=_on_tool,
    )

    if result is None:
        pass
    elif isinstance(result, list):
        for r in result:
            if r.text:
                await dispatcher.send_final_reply(r.text)
    else:
        if result.text:
            await dispatcher.send_final_reply(result.text)

    await dispatcher.send_final_reply()
