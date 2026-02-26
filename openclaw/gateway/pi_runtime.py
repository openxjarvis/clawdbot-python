"""Pi-mono-python powered agent runtime for the gateway.

Replaces MultiProviderRuntime with a pi_coding_agent.AgentSession-based
implementation, mirroring how openclaw TypeScript uses @pi-coding-agent
as its underlying agent engine.

Architecture::

    GatewayBootstrap
         │ creates
    PiAgentRuntime              ← this module
         │ maintains pool of
    pi_coding_agent.AgentSession  per openclaw session_id
         │ subscribes to events from
    pi_agent.AgentEvent hierarchy
         │ converts to
    openclaw.events.Event → WebSocket client

Usage in bootstrap::

    from openclaw.gateway.pi_runtime import PiAgentRuntime
    self.runtime = PiAgentRuntime(
        model="google/gemini-3-pro-preview",
        fallback_models=["google/gemini-3-flash-preview"],
        cwd=workspace_dir,
    )

Usage in handlers (backward-compat run_turn interface)::

    async for event in self.runtime.run_turn(session, message, tools, model):
        await connection.send_event("agent", {...})
"""
from __future__ import annotations

import asyncio
import inspect
import logging
import re
from pathlib import Path
from typing import Any, AsyncIterator, Callable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Quota / rate-limit error detection — mirrors TS failover-error.ts patterns
# ---------------------------------------------------------------------------

_QUOTA_PATTERNS = [
    re.compile(r"429", re.IGNORECASE),
    re.compile(r"rate[_ ]limit", re.IGNORECASE),
    re.compile(r"too many requests", re.IGNORECASE),
    re.compile(r"quota[_ ]exceeded", re.IGNORECASE),
    re.compile(r"exceeded your current quota", re.IGNORECASE),
    re.compile(r"resource[_ ]exhausted", re.IGNORECASE),
    re.compile(r"RESOURCE_EXHAUSTED", re.IGNORECASE),
    re.compile(r"usage limit", re.IGNORECASE),
]


def _is_quota_error(exc: BaseException) -> bool:
    """Return True when exc looks like a rate-limit / quota-exhausted error."""
    msg = str(exc)
    return any(p.search(msg) for p in _QUOTA_PATTERNS)


class PiAgentRuntime:
    """Gateway-level runtime powered by pi_coding_agent.AgentSession.

    Maintains a pool of pi_coding_agent.AgentSession instances, one per
    openclaw session_id.  Provides a ``run_turn()`` async-generator
    interface compatible with the old MultiProviderRuntime, so gateway
    handlers need no changes.
    """

    def __init__(
        self,
        model: str = "google/gemini-2.0-flash",
        fallback_models: list[str] | None = None,
        cwd: str | Path | None = None,
        system_prompt: str | None = None,
    ) -> None:
        self.model_str = model
        # All candidates: primary first, then fallbacks (mirrors TS runWithModelFallback)
        self.model_candidates: list[str] = [model] + list(fallback_models or [])
        self.cwd = str(cwd) if cwd else None
        self.system_prompt = system_prompt

        # Per-session pool: openclaw session_id → pi_coding_agent.AgentSession
        self._pool: dict[str, Any] = {}

        # Observer list — mirrors MultiProviderRuntime.event_listeners.
        # Listeners are called for every Event emitted during run_turn,
        # allowing components like GatewayServer to broadcast events to clients.
        self._event_listeners: list[Callable] = []

    # ------------------------------------------------------------------
    # Pool management
    # ------------------------------------------------------------------

    def _get_or_create_pi_session(
        self,
        session_id: str,
        extra_tools: list[Any] | None = None,
    ) -> Any:
        """Get or create a pi_coding_agent.AgentSession for session_id."""
        if session_id in self._pool:
            return self._pool[session_id]

        try:
            from pi_coding_agent import AgentSession as PiAgentSession
            from openclaw.agents.pi_stream import _resolve_model
            from openclaw.agents.history_utils import read_session_transcript, limit_history_turns
            from pathlib import Path

            model = None
            try:
                model = _resolve_model(self.model_str)
            except Exception:
                pass

            # Load and limit history (Phase 1: Emergency fix for token overflow)
            history_messages = []
            try:
                session_dir = Path.home() / ".openclaw" / "agents" / "main" / "sessions"
                transcript_path = session_dir / f"{session_id}.jsonl"
                
                if transcript_path.exists():
                    # Limit to last 200 messages
                    history_messages = read_session_transcript(transcript_path, limit=200)
                    # Further limit to last 50 turns
                    history_messages = limit_history_turns(history_messages, max_turns=50)
                    
                    logger.info(
                        f"Loaded {len(history_messages)} messages from history "
                        f"(limited to 200 messages / 50 turns)"
                    )
            except Exception as e:
                logger.warning(f"Failed to load limited history: {e}")
                history_messages = []

            pi_session = PiAgentSession(
                cwd=self.cwd,
                model=model,
                session_id=session_id,
            )
            
            # Manually set limited history if session has _conversation_history attribute
            if hasattr(pi_session, '_conversation_history') and history_messages:
                pi_session._conversation_history = history_messages
                logger.info(f"Applied limited history ({len(history_messages)} messages) to session")

            # Thinking models (e.g. gemini-3-pro-preview) require a non-zero
            # thinking budget — set a default level so they don't error with
            # "Budget 0 is invalid. This model only works in thinking mode."
            if model is not None and getattr(model, "reasoning", False):
                try:
                    pi_session.set_thinking_level("low")
                    logger.info("Set thinking_level=low for reasoning model %s", model.id)
                except Exception as exc:
                    logger.warning("Could not set thinking level: %s", exc)

            # Inject openclaw-specific tools — skip any whose name clashes with
            # a pi_coding_agent built-in (e.g. "read", "write", "bash" …) to
            # avoid the "Duplicate function declaration found" 400 error from
            # the Gemini API.
            if extra_tools:
                from openclaw.agents.agent_session import _wrap_openclaw_tool
                existing = list(pi_session._all_tools)
                existing_names = {getattr(t, "name", "") for t in existing}
                wrapped = []
                for t in extra_tools:
                    tool_name = getattr(t, "name", "")
                    if tool_name in existing_names:
                        logger.debug("Skipping duplicate tool %r (already provided by pi_coding_agent)", tool_name)
                        continue
                    try:
                        m = type(t).__module__
                        if "pi_coding_agent" in m or "pi_agent" in m:
                            wrapped.append(t)
                        else:
                            wrapped.append(_wrap_openclaw_tool(t))
                        existing_names.add(tool_name)
                    except Exception as exc:
                        logger.warning("Skipping tool %r: %s", tool_name, exc)
                all_tools = existing + wrapped
                pi_session._all_tools = all_tools
                pi_session._agent.set_tools(all_tools)
                logger.info("Injected %d extra tools (%d skipped as duplicates)", len(wrapped), len(extra_tools) - len(wrapped))

            self._pool[session_id] = pi_session
            logger.info("Created pi_coding_agent.AgentSession for session %s", session_id[:8])

        except Exception as exc:
            logger.error("Failed to create pi session: %s", exc, exc_info=True)
            raise

        return self._pool[session_id]

    def evict_session(self, session_id: str) -> None:
        """Remove a session from the pool."""
        self._pool.pop(session_id, None)

    # ------------------------------------------------------------------
    # Observer pattern — mirrors MultiProviderRuntime.add_event_listener
    # ------------------------------------------------------------------

    def add_event_listener(self, listener: Callable) -> None:
        """Register a listener that is called for every Event produced during run_turn.

        Mirrors ``MultiProviderRuntime.add_event_listener``.  The listener may
        be a regular function or a coroutine function; both are supported.

        Args:
            listener: Callable accepting a single ``Event`` argument.
        """
        if listener not in self._event_listeners:
            self._event_listeners.append(listener)
        logger.debug("PiAgentRuntime: registered event listener %r", listener)

    def remove_event_listener(self, listener: Callable) -> None:
        """Deregister a previously-registered listener (no-op if not found)."""
        try:
            self._event_listeners.remove(listener)
            logger.debug("PiAgentRuntime: removed event listener %r", listener)
        except ValueError:
            pass

    async def _dispatch_event(self, event: Any) -> None:
        """Call every registered listener with *event*.

        Handles both sync and async listeners, and swallows exceptions so that
        a misbehaving listener never interrupts the generator.
        """
        for listener in list(self._event_listeners):
            try:
                result = listener(event)
                if inspect.isawaitable(result):
                    await result
            except Exception as exc:
                logger.warning("PiAgentRuntime: event listener error: %s", exc)

    # ------------------------------------------------------------------
    # run_turn — backward-compatible async generator
    # ------------------------------------------------------------------

    async def run_turn(
        self,
        session: Any,
        message: str,
        tools: list[Any] | None = None,
        model: str | None = None,
        system_prompt: str | None = None,
        images: list[str] | None = None,
    ) -> AsyncIterator[Any]:
        """Stream agent events for one conversation turn.

        Mirrors TS ``runWithModelFallback``: when a quota/rate-limit error is
        received for the primary model, transparently retries with each
        configured fallback model in order.

        Args:
            session:       openclaw Session object (provides session_id)
            message:       User message text
            tools:         Optional tool list (openclaw AgentToolBase instances)
            model:         Optional per-call model override (skips fallbacks)
            system_prompt: Optional system prompt override
            images:        Optional list of image data URLs or http URLs
        """
        session_id = getattr(session, "session_id", "") or ""
        extra_tools = list(tools) if tools else None

        # Build the candidate list for this turn.
        # A per-call override bypasses the configured fallback chain (mirrors TS).
        if model and model != self.model_str:
            candidates = [model]
        else:
            candidates = list(self.model_candidates)

        from openclaw.agents.pi_stream import _resolve_model
        from openclaw.events import Event, EventType

        last_error: Exception | None = None

        for attempt, candidate_model in enumerate(candidates):
            is_fallback = attempt > 0

            if is_fallback:
                logger.warning(
                    "Model %r quota/rate-limit exceeded — retrying with fallback %r",
                    candidates[attempt - 1],
                    candidate_model,
                )

            # Get or create the session, then switch model if needed
            try:
                pi_session = self._get_or_create_pi_session(session_id, extra_tools)
            except Exception as exc:
                yield Event(
                    type=EventType.ERROR,
                    source="pi-runtime",
                    session_id=session_id,
                    data={"message": f"Session creation failed: {exc}"},
                )
                return

            # Switch model when using a fallback or explicit override
            if candidate_model != self.model_str or is_fallback:
                try:
                    m = _resolve_model(candidate_model)
                    await pi_session.set_model(m)
                    
                    # CRITICAL FIX: Adjust thinking_level based on model capabilities
                    # When falling back from a reasoning model to a non-reasoning model,
                    # we must clear the thinking_level or the API will return 400.
                    if hasattr(m, "reasoning"):
                        if m.reasoning:
                            # New model supports reasoning — set thinking_level
                            try:
                                pi_session.set_thinking_level("low")
                                logger.info("Set thinking_level=low for reasoning model %s", m.id)
                            except Exception as exc:
                                logger.debug("Could not set thinking level: %s", exc)
                        else:
                            # New model does NOT support reasoning — clear thinking_level
                            try:
                                pi_session.set_thinking_level("off")
                                logger.info("Cleared thinking_level for non-reasoning model %s", m.id)
                            except Exception as exc:
                                logger.debug("Could not clear thinking level: %s", exc)
                    
                    logger.info("Switched session %s to model %r", session_id[:8], candidate_model)
                except Exception as exc:
                    logger.warning("Model switch to %r failed: %s", candidate_model, exc)

            # Apply system prompt on every turn
            effective_prompt = system_prompt or self.system_prompt
            if effective_prompt:
                pi_session._agent.set_system_prompt(effective_prompt)
                logger.debug(
                    "Applied system prompt (%d chars) to session %s",
                    len(effective_prompt), session_id[:8],
                )

            # Bridge pi events → async queue
            event_queue: asyncio.Queue[Any] = asyncio.Queue()
            _SENTINEL = object()
            _quota_error: list[Exception] = []  # mutable cell to communicate error out

            _prev_text: list[str] = [""]

            def on_event(pi_event: Any) -> None:
                from openclaw.events import Event, EventType  # noqa: F811

                # pi can emit both AgentEvent objects and plain dicts
                if isinstance(pi_event, dict):
                    etype = pi_event.get("type")
                else:
                    etype = getattr(pi_event, "type", None)

                if etype == "message_update":
                    if isinstance(pi_event, dict):
                        msg = pi_event.get("message")
                    else:
                        msg = getattr(pi_event, "message", None)
                    if isinstance(msg, dict):
                        content = msg.get("content", [])
                    else:
                        content = getattr(msg, "content", []) if msg else []
                    full_text = ""
                    for chunk in content:
                        if isinstance(chunk, dict):
                            t = chunk.get("text") if chunk.get("type") == "text" else None
                        else:
                            t = getattr(chunk, "text", None)
                        if t and isinstance(t, str):
                            full_text += t
                    delta = full_text[len(_prev_text[0]):]
                    _prev_text[0] = full_text
                    if delta:
                        event_queue.put_nowait(Event(
                            type=EventType.TEXT,
                            source="pi-session",
                            session_id=session_id,
                            data={"text": delta},
                        ))
                    return

                if etype in ("message_start", "turn_start", "agent_start"):
                    _prev_text[0] = ""

                if etype in ("agent_end", "turn_end"):
                    if isinstance(pi_event, dict):
                        msgs = pi_event.get("messages") or []
                        msg = pi_event.get("message")
                    else:
                        msgs = getattr(pi_event, "messages", None) or []
                        msg = getattr(pi_event, "message", None)
                    if not isinstance(msgs, list):
                        msgs = [msgs] if msgs else []
                    if msg:
                        msgs = [msg] + list(msgs)
                    for m in msgs:
                        # m may be a dict (pi emits some events as plain dicts)
                        if isinstance(m, dict):
                            err = m.get("error_message") or m.get("errorMessage")
                        else:
                            err = getattr(m, "error_message", None)
                        if err:
                            logger.error("pi agent error (stop_reason=error): %s", err)
                            # Check whether this is a quota error so the outer
                            # loop can decide to try a fallback model.
                            synthetic = RuntimeError(str(err))
                            if _is_quota_error(synthetic):
                                _quota_error.append(synthetic)
                            else:
                                event_queue.put_nowait(Event(
                                    type=EventType.ERROR,
                                    source="pi-session",
                                    session_id=session_id,
                                    data={"message": str(err)},
                                ))
                            return

                from openclaw.agents.agent_session import _convert_pi_event
                oc_event = _convert_pi_event(pi_event, session_id)
                if oc_event is not None:
                    event_queue.put_nowait(oc_event)

            unsub = pi_session.subscribe(on_event)

            async def _run_prompt(
                _pi_session: Any = pi_session,
                _images: list[str] | None = images,
            ) -> None:
                try:
                    pi_images = None
                    if _images:
                        try:
                            from pi_ai.types import ImageContent
                            import base64 as _b64
                            pi_images = []
                            for img_ref in _images:
                                if isinstance(img_ref, str) and img_ref.startswith("data:"):
                                    header, data_str = img_ref.split(",", 1)
                                    mime_type = header.split(";")[0].split(":", 1)[1]
                                    img_bytes = _b64.b64decode(data_str)
                                    b64_data = _b64.b64encode(img_bytes).decode()
                                    pi_images.append(ImageContent(type="image", data=b64_data, mime_type=mime_type))
                                elif isinstance(img_ref, str) and img_ref.startswith(("http://", "https://")):
                                    import httpx
                                    resp = httpx.get(img_ref, timeout=30.0)
                                    if resp.status_code == 200:
                                        mime_type = resp.headers.get("content-type", "image/jpeg").split(";")[0]
                                        b64_data = _b64.b64encode(resp.content).decode()
                                        pi_images.append(ImageContent(type="image", data=b64_data, mime_type=mime_type))
                        except Exception as img_exc:
                            logger.warning("Failed to convert images: %s", img_exc)
                            pi_images = None
                    
                    # Phase 2: Token monitoring - estimate before sending
                    from openclaw.agents.compaction.functions import estimate_messages_tokens, should_compact
                    
                    context_tokens = 0
                    context_window = 1_048_576  # Gemini default
                    
                    try:
                        if hasattr(_pi_session, '_conversation_history'):
                            context_tokens = estimate_messages_tokens(_pi_session._conversation_history)
                            logger.debug(f"Estimated context tokens: {context_tokens}")
                            
                            # Phase 3: Auto-compaction trigger (Safeguard)
                            compaction_settings = {
                                'enabled': True,
                                'reserveTokens': 16384,      # 16K for response
                                'keepRecentTokens': 20000,   # Keep recent 20K
                            }
                            
                            if should_compact(context_tokens, context_window, compaction_settings):
                                logger.warning(
                                    f"Auto-compaction triggered: {context_tokens} tokens "
                                    f"exceeds threshold ({context_window - compaction_settings['reserveTokens']})"
                                )
                                
                                # Note: Full compaction implementation would go here
                                # For now, the history limit (Phase 1) prevents overflow
                                logger.info("Using history limiting as compaction strategy")
                            elif context_tokens > context_window * 0.9:
                                logger.warning(
                                    f"Context tokens ({context_tokens}) approaching limit ({context_window})"
                                )
                    except Exception as e:
                        logger.debug(f"Token estimation failed: {e}")
                    
                    await _pi_session.prompt(message, pi_images)
                except Exception as exc:
                    if _is_quota_error(exc):
                        _quota_error.append(exc)
                    else:
                        from openclaw.events import Event, EventType  # noqa: F811
                        event_queue.put_nowait(Event(
                            type=EventType.ERROR,
                            source="pi-runtime",
                            session_id=session_id,
                            data={"message": str(exc)},
                        ))
                finally:
                    event_queue.put_nowait(_SENTINEL)

            prompt_task = asyncio.create_task(_run_prompt())
            collected_events: list[Any] = []

            try:
                while True:
                    event = await event_queue.get()
                    if event is _SENTINEL:
                        break
                    collected_events.append(event)
            finally:
                unsub()
                if not prompt_task.done():
                    prompt_task.cancel()
                    try:
                        await prompt_task
                    except asyncio.CancelledError:
                        pass

            # If a quota error was detected and we have more fallbacks, retry
            if _quota_error and attempt < len(candidates) - 1:
                last_error = _quota_error[0]
                # Evict the session so the fallback model gets a fresh session
                # that won't be confused by the failed turn's internal state
                self.evict_session(session_id)
                continue

            # No quota error (or no more fallbacks) — yield collected events
            if is_fallback and not _quota_error:
                # Inform the client which fallback model was used
                yield Event(
                    type=EventType.TEXT,
                    source="pi-runtime",
                    session_id=session_id,
                    data={"text": f"[Using fallback model: {candidate_model}]\n"},
                )

            for ev in collected_events:
                await self._dispatch_event(ev)
                yield ev

            # Phase 2: Update session token statistics after successful run
            try:
                from openclaw.agents.session_entry import update_session_entry_tokens
                
                # Extract usage info from events if available
                input_tokens = 0
                output_tokens = 0
                for evt in collected_events:
                    if hasattr(evt, 'data') and isinstance(evt.data, dict):
                        usage = evt.data.get('usage', {})
                        if usage:
                            input_tokens += usage.get('input_tokens', 0) or usage.get('inputTokens', 0)
                            output_tokens += usage.get('output_tokens', 0) or usage.get('outputTokens', 0)
                
                # Update SessionEntry if we have usage data or context estimate
                if input_tokens or output_tokens or context_tokens:
                    await update_session_entry_tokens(
                        session_manager=getattr(self, 'session_manager', None),
                        session_id=session_id,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        context_tokens=context_tokens if context_tokens > 0 else None,
                    )
                    logger.debug(
                        f"Updated session tokens: input={input_tokens}, "
                        f"output={output_tokens}, context={context_tokens}"
                    )
            except Exception as e:
                logger.warning(f"Failed to update session token statistics: {e}")

            # If quota error and NO more fallbacks, emit a helpful error
            if _quota_error:
                err_msg = (
                    f"Quota exceeded for all configured models "
                    f"({', '.join(candidates)}). "
                    "Please check your API plan or add more fallback models in "
                    "`agents.defaults.model.fallbacks`."
                )
                err_event = Event(
                    type=EventType.ERROR,
                    source="pi-runtime",
                    session_id=session_id,
                    data={"message": err_msg},
                )
                await self._dispatch_event(err_event)
                yield err_event

            return  # done — either success or exhausted all candidates

        # Should not reach here, but yield last error just in case
        if last_error:
            yield Event(
                type=EventType.ERROR,
                source="pi-runtime",
                session_id=session_id,
                data={"message": str(last_error)},
            )

    # ------------------------------------------------------------------
    # Abort running session
    # ------------------------------------------------------------------

    async def abort_session(self, session_id: str) -> None:
        """Abort any running turn for the given session."""
        pi_session = self._pool.get(session_id)
        if pi_session is not None:
            try:
                await pi_session.abort()
            except Exception as exc:
                logger.warning("Abort session %s: %s", session_id[:8], exc)


__all__ = ["PiAgentRuntime"]
