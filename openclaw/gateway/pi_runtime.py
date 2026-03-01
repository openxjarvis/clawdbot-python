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


def _is_abort_error(exc: BaseException) -> bool:
    """Return True when exc represents a deliberate abort/cancellation.

    Delegates to agents/errors.py so the logic is kept in one place.
    Mirrors TS ``isRunnerAbortError``.
    """
    from openclaw.agents.errors import is_runner_abort_error
    return is_runner_abort_error(exc)


def _trim_tool_call_names_in_event(event: Any) -> None:
    """Trim whitespace from tool call names in a pi event.

    Mirrors TS ``wrapStreamFnTrimToolCallNames`` /
    ``trimWhitespaceFromToolCallNamesInMessage``.
    Some models return tool call names with leading/trailing whitespace
    which causes downstream parsing failures.
    """
    msg = None
    if isinstance(event, dict):
        msg = event.get("message")
    elif hasattr(event, "message"):
        msg = getattr(event, "message", None)
    if msg is None:
        return

    content = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", None)
    if not isinstance(content, list):
        return
    for block in content:
        if isinstance(block, dict) and block.get("type") == "toolCall":
            name = block.get("name")
            if isinstance(name, str):
                trimmed = name.strip()
                if trimmed != name:
                    block["name"] = trimmed
        elif hasattr(block, "type") and getattr(block, "type", None) == "toolCall":
            name = getattr(block, "name", None)
            if isinstance(name, str):
                trimmed = name.strip()
                if trimmed != name:
                    block.name = trimmed


class PiSession:
    """Lightweight wrapper around pi_coding_agent.AgentSession for testability.

    Exposes only the fields that PiAgentRuntime and its tests need to mock.
    """

    def __init__(self, session_id: str | None = None, **kwargs: Any) -> None:
        self.session_id = session_id or ""
        self.history: list[Any] = kwargs.get("history", [])

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError("PiSession.run must be implemented by subclass or mock")


class PiAgentRuntime:
    """Gateway-level runtime powered by pi_coding_agent.AgentSession.

    Maintains a pool of pi_coding_agent.AgentSession instances, one per
    openclaw session_id.  Provides a ``run_turn()`` async-generator
    interface compatible with the old MultiProviderRuntime, so gateway
    handlers need no changes.
    """

    # Retry loop constants — aligned with TS run.ts
    BASE_RUN_RETRY_ITERATIONS = 24
    RUN_RETRY_ITERATIONS_PER_PROFILE = 8
    MIN_RUN_RETRY_ITERATIONS = 32
    MAX_RUN_RETRY_ITERATIONS = 160
    MAX_OVERFLOW_COMPACTION_ATTEMPTS = 3

    def __init__(
        self,
        model: str = "google/gemini-2.0-flash",
        fallback_models: list[str] | None = None,
        cwd: str | Path | None = None,
        system_prompt: str | None = None,
        config: Any = None,
        hook_runner: Any | None = None,
        *,
        workspace_dir: str | Path | None = None,
    ) -> None:
        self.model_str = model
        self.model_candidates: list[str] = [model] + list(fallback_models or [])
        # workspace_dir is an alias for cwd (accepted for API compatibility)
        self.cwd = str(workspace_dir or cwd) if (workspace_dir or cwd) else None
        self.system_prompt = system_prompt
        self._config = config  # keep original mock/object intact
        self.config = config if isinstance(config, dict) else {}

        self._hook_runner: Any | None = hook_runner

        # Per-session pool: openclaw session_id → pi_coding_agent.AgentSession
        self._pool: dict[str, Any] = {}

        self._event_listeners: list[Callable] = []

        # Auth profile rotation — mirrors TS auth-profiles integration in run.ts
        self._rotation_manager: Any | None = None
        self._profile_store: Any | None = None
        try:
            from openclaw.agents.auth.profile import ProfileStore
            from openclaw.agents.auth.rotation import RotationManager
            self._profile_store = ProfileStore()
            self._rotation_manager = RotationManager(self._profile_store)
        except Exception:
            pass

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
                    
                    # Phase 4: Apply history budget limit (maxHistoryShare)
                    try:
                        from openclaw.agents.compaction.functions import prune_history_for_context_share
                        from openclaw.agents.context_window_guard import resolve_context_window_info
                        
                        # Use context window guard for dynamic resolution
                        provider = self.model_str.split('/')[0] if '/' in self.model_str else 'google'
                        model_id = self.model_str.split('/')[-1] if '/' in self.model_str else self.model_str
                        model_context_window = model.contextWindow if model and hasattr(model, 'contextWindow') else None
                        
                        window_info = resolve_context_window_info(
                            cfg=self.config,
                            provider=provider,
                            model_id=model_id,
                            model_context_window=model_context_window,
                            default_tokens=1_048_576,
                        )
                        context_window = window_info.tokens
                        
                        # Get max_history_share from config
                        agents_config = self.config.get('agents', {})
                        defaults = agents_config.get('defaults', {})
                        max_history_share = defaults.get('maxHistoryShare', 0.5)
                        
                        prune_result = prune_history_for_context_share(
                            messages=history_messages,
                            max_context_tokens=context_window,
                            max_history_share=max_history_share,
                        )
                        
                        if prune_result['dropped_messages'] > 0:
                            history_messages = prune_result['messages']
                            logger.info(
                                f"History budget: dropped {prune_result['dropped_messages']} messages "
                                f"({prune_result['dropped_tokens']} tokens), "
                                f"kept {len(history_messages)} messages ({prune_result['kept_tokens']} tokens)"
                            )
                        else:
                            logger.debug("History within budget, no pruning needed")
                    except Exception as budget_exc:
                        logger.debug(f"History budget pruning skipped: {budget_exc}")
                    
                    logger.info(
                        f"Loaded {len(history_messages)} messages from history "
                        f"(limited to 200 messages / 50 turns, with budget pruning)"
                    )
            except Exception as e:
                logger.warning(f"Failed to load limited history: {e}")
                history_messages = []

            pi_session = PiAgentSession(
                cwd=self.cwd,
                model=model,
                session_id=session_id,
            )
            
            # Install tool result context guard (preemptive protection)
            try:
                from openclaw.agents.tool_result_context_guard import install_tool_result_context_guard
                
                cleanup_fn = install_tool_result_context_guard(
                    agent=pi_session,
                    context_window_tokens=context_window,
                )
                logger.debug(f"Tool result context guard installed for session {session_id[:8]}")
            except Exception as guard_exc:
                logger.debug(f"Tool result context guard installation failed: {guard_exc}")
            
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
                            wrapped.append(_wrap_openclaw_tool(t, session_id=session_id))
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

    async def reset_session(self, session_id: str) -> None:
        """Reset a session — fires before_reset hook then evicts the session.

        Called on /new or /reset commands. Mirrors TS resetSession() behavior.
        """
        # --- Plugin Hook: before_reset ---
        if self._hook_runner and self._hook_runner.has_hooks("before_reset"):
            try:
                await self._hook_runner.run_before_reset(
                    {"session_key": session_id},
                    self._build_agent_ctx(session_id),
                )
            except Exception as exc:
                logger.debug(f"before_reset hook failed: {exc}")

        self.evict_session(session_id)

        # --- Plugin Hook: session_end ---
        if self._hook_runner and self._hook_runner.has_hooks("session_end"):
            try:
                await self._hook_runner.run_session_end(
                    {"session_key": session_id},
                    self._build_session_ctx(session_id),
                )
            except Exception as exc:
                logger.debug(f"session_end hook failed: {exc}")

    # ------------------------------------------------------------------
    # Compaction execution
    # ------------------------------------------------------------------
    
    async def _execute_compaction(
        self,
        session_id: str,
        pi_session: Any,
        context_window: int,
        compaction_settings: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Execute compaction on a session's history.
        
        Mirrors TypeScript compaction flow:
        1. Prune history for context share (maxHistoryShare)
        2. Summarize dropped messages using LLM
        3. Update session compactionCount
        4. Enrich summary with tool failures and file ops
        
        Returns:
            Compaction result dict with summary, or None if compaction skipped
        """
        try:
            # --- Plugin Hook: before_compaction ---
            if self._hook_runner and self._hook_runner.has_hooks("before_compaction"):
                try:
                    await self._hook_runner.run_before_compaction(
                        {"session_id": session_id, "context_window": context_window},
                        self._build_agent_ctx(session_id),
                    )
                except Exception as exc:
                    logger.debug(f"before_compaction hook failed: {exc}")

            from openclaw.agents.compaction.functions import (
                prune_history_for_context_share,
                summarize_in_stages,
                estimate_messages_tokens,
            )
            from openclaw.agents.extensions.compaction_safeguard import enrich_compaction_summary
            from openclaw.agents.session_entry import update_session_entry_tokens
            
            if not hasattr(pi_session, '_conversation_history'):
                logger.debug("No conversation history to compact")
                return None
            
            history = pi_session._conversation_history
            if not history or len(history) < 10:
                logger.debug("History too short to compact (< 10 messages)")
                return None
            
            # Step 1: Prune history for context budget
            max_history_share = compaction_settings.get('maxHistoryShare', 0.5)
            prune_result = prune_history_for_context_share(
                messages=history,
                max_context_tokens=context_window,
                max_history_share=max_history_share,
            )
            
            dropped_messages = prune_result['dropped_messages_list']
            kept_messages = prune_result['messages']
            
            if not dropped_messages:
                logger.debug("No messages dropped during history pruning")
                return None
            
            logger.info(
                f"Compaction: dropped {len(dropped_messages)} messages "
                f"({prune_result['dropped_tokens']} tokens), "
                f"kept {len(kept_messages)} messages ({prune_result['kept_tokens']} tokens)"
            )
            
            # Step 2: Summarize dropped messages
            # Try to get model info from pi_session
            model_info = {
                "provider": "google",  # Default for Gemini
                "model": "gemini-2.0-flash",
                "contextWindow": context_window,
            }
            
            # Try to extract actual model from session
            if hasattr(pi_session, '_agent'):
                agent = pi_session._agent
                if hasattr(agent, '_model'):
                    model_obj = agent._model
                    if hasattr(model_obj, 'id'):
                        model_info["model"] = model_obj.id
                    if hasattr(model_obj, 'context_window'):
                        model_info["contextWindow"] = model_obj.context_window
            
            # Get API key (try environment)
            import os
            api_key = os.environ.get('GOOGLE_API_KEY') or os.environ.get('GEMINI_API_KEY', '')
            
            if not api_key:
                logger.warning("No API key available for compaction summarization, using fallback")
                summary = f"Summary of {len(dropped_messages)} dropped messages (no API key for LLM summarization)"
            else:
                reserve_tokens = compaction_settings.get('reserveTokens', 16384)
                max_chunk_tokens = compaction_settings.get('keepRecentTokens', 20000)
                
                summary = await summarize_in_stages(
                    messages=dropped_messages,
                    model=model_info,
                    api_key=api_key,
                    signal=None,  # No abort signal for now
                    reserve_tokens=reserve_tokens,
                    max_chunk_tokens=max_chunk_tokens,
                    context_window=context_window,
                    custom_instructions="Preserve all key decisions, TODOs, open questions, and constraints.",
                    previous_summary=None,
                )
            
            # Step 3: Enrich summary with tool failures and file ops — only in
            # "safeguard" mode (mirrors TS: safeguard extension applied only when
            # compaction.mode === "safeguard").
            _compaction_mode = compaction_settings.get('mode', 'safeguard')
            if _compaction_mode == 'safeguard':
                enriched_summary = enrich_compaction_summary(
                    base_summary=summary,
                    messages_to_summarize=dropped_messages,
                    turn_prefix_messages=[],
                    file_ops=None,
                    workspace_dir=self.cwd,
                    include_workspace_context=True,
                )
            else:
                enriched_summary = summary
            
            # Step 4: Update session history with compacted version
            # Insert summary as a system-like message at the beginning of kept messages
            compaction_message = {
                "role": "user",
                "content": f"[Conversation history summary]\n{enriched_summary}",
                "timestamp": 0,  # Place at beginning
            }
            
            new_history = [compaction_message] + kept_messages
            pi_session._conversation_history = new_history
            
            # Step 5: Update compactionCount in SessionEntry
            # This would require access to session_manager
            # For now, log the compaction
            logger.info(f"Session {session_id[:8]} compaction completed successfully")

            compaction_result = {
                "summary": enriched_summary,
                "dropped_messages": len(dropped_messages),
                "dropped_tokens": prune_result['dropped_tokens'],
                "kept_messages": len(kept_messages),
                "kept_tokens": prune_result['kept_tokens'],
            }

            # --- Plugin Hook: after_compaction ---
            if self._hook_runner and self._hook_runner.has_hooks("after_compaction"):
                try:
                    await self._hook_runner.run_after_compaction(
                        {"session_id": session_id, "result": compaction_result},
                        self._build_agent_ctx(session_id),
                    )
                except Exception as exc:
                    logger.debug(f"after_compaction hook failed: {exc}")

            return compaction_result
            
        except Exception as e:
            logger.error(f"Compaction execution failed: {e}", exc_info=True)
            return None

    # ------------------------------------------------------------------
    # Tool result truncation — mirrors TS truncateOversizedToolResultsInSession
    # ------------------------------------------------------------------

    async def _truncate_oversized_tool_results(
        self,
        session_id: str,
        pi_session: Any,
        max_chars_per_result: int = 50_000,
    ) -> bool:
        """Truncate oversized tool results in session history.

        Mirrors TS ``truncateOversizedToolResultsInSession()`` — used as a
        fallback when compaction alone cannot resolve a context overflow.

        Returns True if any results were truncated.
        """
        if not hasattr(pi_session, "_conversation_history"):
            return False
        truncated_any = False
        for msg in pi_session._conversation_history:
            role = msg.get("role") if isinstance(msg, dict) else getattr(msg, "role", None)
            if role != "tool":
                continue
            content = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", None)
            if isinstance(content, str) and len(content) > max_chars_per_result:
                head = content[: max_chars_per_result // 2]
                tail = content[-(max_chars_per_result // 4) :]
                truncated = f"{head}\n\n[... truncated {len(content) - max_chars_per_result} chars ...]\n\n{tail}"
                if isinstance(msg, dict):
                    msg["content"] = truncated
                else:
                    msg.content = truncated
                truncated_any = True
            elif isinstance(content, list):
                for part in content:
                    text = part.get("text") if isinstance(part, dict) else getattr(part, "text", None)
                    if isinstance(text, str) and len(text) > max_chars_per_result:
                        head = text[: max_chars_per_result // 2]
                        tail = text[-(max_chars_per_result // 4) :]
                        truncated = f"{head}\n\n[... truncated {len(text) - max_chars_per_result} chars ...]\n\n{tail}"
                        if isinstance(part, dict):
                            part["text"] = truncated
                        else:
                            part.text = truncated
                        truncated_any = True
        if truncated_any:
            logger.info("Truncated oversized tool results in session %s", session_id[:8])
        return truncated_any

    async def _wait_for_session_idle(self, pi_session: Any, timeout: float = 30.0) -> bool:
        """Wait until *pi_session* is no longer actively streaming.

        Mirrors TS ``flushPendingToolResultsAfterIdle`` / ``waitForIdle``.
        Returns True when session becomes idle before *timeout*, False on timeout.

        This prevents injecting synthetic tool-result events while a tool call
        is still in-flight, which would cause "missing tool result" errors.
        """
        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            # Check known idle indicators on pi_session
            is_idle = False
            if hasattr(pi_session, "is_idle"):
                try:
                    is_idle = bool(pi_session.is_idle())
                except Exception:
                    is_idle = True  # assume idle on error
            elif hasattr(pi_session, "_is_running"):
                is_idle = not getattr(pi_session, "_is_running", False)
            else:
                is_idle = True  # cannot determine — assume idle

            if is_idle:
                return True

            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                return False

            await asyncio.sleep(min(0.1, remaining))

    def _resolve_max_retry_iterations(self, profile_count: int = 1) -> int:
        """Compute max retry iterations.  Mirrors TS ``resolveMaxRunRetryIterations``."""
        raw = self.BASE_RUN_RETRY_ITERATIONS + profile_count * self.RUN_RETRY_ITERATIONS_PER_PROFILE
        return min(self.MAX_RUN_RETRY_ITERATIONS, max(self.MIN_RUN_RETRY_ITERATIONS, raw))

    def _build_extra_params(
        self,
        provider: str,
        model: str,
        auth_profile: Any | None = None,
    ) -> dict[str, Any]:
        """Build provider-specific extra params for pi_session.prompt().

        Mirrors TS ``buildExtraParams`` from ``pi-embedded-runner/extra-params.ts``.

        Covers:
        - Anthropic prompt caching (``cache_control`` headers on system prompt)
        - OpenRouter provider routing headers
        - Z.AI tool-stream flag
        - Upstream model ID injection for compatibility

        Returns:
            Dict of extra params to pass to pi_session.prompt() if supported.
            Empty dict if no special params are needed.
        """
        extra: dict[str, Any] = {}

        prov = (provider or "").lower()

        if "anthropic" in prov or "claude" in model.lower():
            # Enable prompt-caching beta for Anthropic — reduces cost & latency
            extra["anthropic_beta"] = ["prompt-caching-2024-07-31"]
            extra["cache_control"] = {"type": "ephemeral"}

        if "openrouter" in prov:
            # Route to the upstream provider that owns the model
            upstream = model.split("/")[-1] if "/" in model else model
            extra["x-openrouter-provider"] = {"order": [upstream], "allow_fallbacks": False}

        if "z.ai" in prov or "z-ai" in prov:
            extra["z_ai_tool_stream"] = True

        # Inject auth profile custom headers if available
        if auth_profile and hasattr(auth_profile, "extra_headers"):
            hdrs = getattr(auth_profile, "extra_headers", None)
            if isinstance(hdrs, dict) and hdrs:
                extra["extra_headers"] = hdrs

        return extra

    def _resolve_auth_profile_candidates(self, provider: str) -> list[str]:
        """Return ordered list of auth profile IDs for the provider.

        Falls back to ``[None]`` (no profile) when rotation is unavailable.
        """
        if not self._rotation_manager or not self._profile_store:
            return [None]  # type: ignore[list-item]
        try:
            self._rotation_manager.clear_expired_cooldowns()
            profiles = self._profile_store.list_profiles(provider)
            available = [p for p in profiles if p.is_available()]
            available.sort(key=lambda p: p.last_used or __import__("datetime").datetime.min)
            if not available:
                return [None]  # type: ignore[list-item]
            return [p.id for p in available]
        except Exception:
            return [None]  # type: ignore[list-item]

    def _apply_auth_profile(self, profile_id: str | None) -> str | None:
        """Apply an auth profile's API key to the environment. Returns the key or None."""
        if not profile_id or not self._profile_store:
            return None
        import os
        profile = self._profile_store.get_profile(profile_id)
        if not profile:
            return None
        key = profile.get_api_key()
        if key:
            env_map = {
                "google": ["GOOGLE_API_KEY", "GEMINI_API_KEY"],
                "anthropic": ["ANTHROPIC_API_KEY"],
                "openai": ["OPENAI_API_KEY"],
            }
            for env_name in env_map.get(profile.provider, []):
                os.environ[env_name] = key
        return key

    # ------------------------------------------------------------------
    # Observer pattern — mirrors MultiProviderRuntime.add_event_listener
    # ------------------------------------------------------------------

    def set_hook_runner(self, hook_runner: Any) -> None:
        """Set the plugin hook runner. Called from bootstrap after plugin loading."""
        self._hook_runner = hook_runner

    def _build_agent_ctx(self, session_id: str) -> dict[str, Any]:
        """Build PluginHookAgentContext for hook calls."""
        return {
            "agent_id": "main",
            "session_key": session_id,
            "session_id": session_id,
            "model": self.model_str,
            "workspace_dir": self.cwd,
        }

    def _build_session_ctx(self, session_id: str) -> dict[str, Any]:
        """Build PluginHookSessionContext for hook calls."""
        return {
            "session_key": session_id,
            "session_id": session_id,
        }

    def _build_gateway_ctx(self) -> dict[str, Any]:
        """Build PluginHookGatewayContext for hook calls."""
        return {
            "config": self.config,
            "workspace_dir": self.cwd,
        }

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
        run_id: str | None = None,
        session_key: str | None = None,
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
            run_id:        Optional run identifier for active-run registry
            session_key:   Optional session key for active-run registry
        """
        import uuid as _uuid
        session_id = getattr(session, "session_id", "") or ""
        extra_tools = list(tools) if tools else None
        _run_id = run_id or str(_uuid.uuid4())
        _session_key = session_key or session_id

        # Register as active run so steer/abort can find this turn
        from openclaw.agents.pi_embedded import (
            EmbeddedPiRunHandle,
            set_active_embedded_run,
            clear_active_embedded_run,
        )
        _active_handle: EmbeddedPiRunHandle | None = None

        # --- Plugin Hook: session_start ---
        if self._hook_runner and not getattr(session, "_hook_session_started", False):
            try:
                await self._hook_runner.run_session_start(
                    {"session_key": session_id},
                    self._build_session_ctx(session_id),
                )
                object.__setattr__(session, "_hook_session_started", True)
            except Exception:
                pass  # hooks must not break core flow

        # --- Plugin Hook: before_model_resolve ---
        # Allows plugins to override provider/model before resolution
        effective_model = model
        if self._hook_runner:
            try:
                resolve_result = await self._hook_runner.run_before_model_resolve(
                    {"model": model or self.model_str, "config": self.config},
                    self._build_agent_ctx(session_id),
                )
                if resolve_result:
                    if resolve_result.get("model_override"):
                        effective_model = resolve_result["model_override"]
                        logger.debug(f"[hooks] before_model_resolve: model overridden to {effective_model}")
            except Exception as exc:
                logger.warning(f"before_model_resolve hook failed: {exc}")

        # --- Plugin Hook: before_prompt_build ---
        # Allows plugins to inject system_prompt and prepend_context
        effective_system_prompt = system_prompt
        if self._hook_runner:
            try:
                prompt_result = await self._hook_runner.run_before_prompt_build(
                    {"system_prompt": system_prompt, "config": self.config},
                    self._build_agent_ctx(session_id),
                )
                if prompt_result:
                    if prompt_result.get("system_prompt"):
                        effective_system_prompt = prompt_result["system_prompt"]
                    if prompt_result.get("prepend_context") and effective_system_prompt:
                        effective_system_prompt = (
                            prompt_result["prepend_context"] + "\n\n" + effective_system_prompt
                        )
                    elif prompt_result.get("prepend_context"):
                        effective_system_prompt = prompt_result["prepend_context"]
            except Exception as exc:
                logger.warning(f"before_prompt_build hook failed: {exc}")

        # Use effective values going forward
        if effective_model and effective_model != model:
            model = effective_model
        if effective_system_prompt and effective_system_prompt != system_prompt:
            system_prompt = effective_system_prompt

        # --- Plugin Hook: message_received ---
        if self._hook_runner:
            try:
                await self._hook_runner.run_message_received(
                    {"message": message, "session_key": session_id},
                    self._build_agent_ctx(session_id),
                )
            except Exception as exc:
                logger.warning(f"message_received hook failed: {exc}")

        # Build the candidate list for this turn.
        # A per-call override bypasses the configured fallback chain (mirrors TS).
        if model and model != self.model_str:
            candidates = [model]
        else:
            candidates = list(self.model_candidates)

        from openclaw.agents.pi_stream import _resolve_model
        from openclaw.events import Event, EventType

        # --- Outer retry loop (mirrors TS runEmbeddedPiAgent while-loop) ---
        # Handles: auth profile rotation, context overflow compaction/truncation,
        # thinking-level fallback. The inner loop handles model quota failover.
        provider_hint = candidates[0].split("/")[0] if "/" in candidates[0] else "google"
        auth_profile_ids = self._resolve_auth_profile_candidates(provider_hint)
        max_retry = self._resolve_max_retry_iterations(len(auth_profile_ids))
        overflow_compaction_attempts = 0
        current_profile_idx = 0
        current_think_level: str | None = None  # set on fallback

        try:
            for retry_iteration in range(max_retry):
                # Apply auth profile (if available)
                if auth_profile_ids and current_profile_idx < len(auth_profile_ids):
                    pid = auth_profile_ids[current_profile_idx]
                    self._apply_auth_profile(pid)

                last_error: Exception | None = None
                context_tokens = 0
                _context_overflow = False
                _auth_error = False

                for attempt, candidate_model in enumerate(candidates):
                    is_fallback = attempt > 0

                    if is_fallback:
                        logger.warning(
                            "Model %r quota/rate-limit exceeded — retrying with fallback %r",
                            candidates[attempt - 1],
                            candidate_model,
                        )

                    # Resolve provider/model_id early so they are always in scope
                    # for usage normalisation at end of attempt (line ~1384).
                    provider = candidate_model.split("/")[0] if "/" in candidate_model else "google"
                    model_id = candidate_model.split("/")[-1] if "/" in candidate_model else candidate_model

                    # Acquire the session write lock for the full attempt duration.
                    # Mirrors TS run/attempt.ts: acquireSessionWriteLock held across the
                    # entire attempt so concurrent writes cannot corrupt the session file.
                    # We store the context manager and release it explicitly at every exit
                    # point (before return / before continue) using _release_attempt_lock().
                    _attempt_lock_ctx = None
                    try:
                        from openclaw.agents.session_lock import acquire_session_write_lock_cached
                        from openclaw.config.sessions.transcripts import get_session_transcript_path
                        _session_file = get_session_transcript_path(session_id)
                        _attempt_lock_ctx = acquire_session_write_lock_cached(_session_file, max_hold_ms=600_000)
                        await _attempt_lock_ctx.__aenter__()
                    except Exception as _lock_exc:
                        logger.debug("Could not acquire session write lock for %s: %s", session_id[:8], _lock_exc)
                        _attempt_lock_ctx = None

                    async def _release_attempt_lock() -> None:
                        nonlocal _attempt_lock_ctx
                        if _attempt_lock_ctx is not None:
                            try:
                                await _attempt_lock_ctx.__aexit__(None, None, None)
                            except Exception:
                                pass
                            _attempt_lock_ctx = None

                    # Get or create the session, then switch model if needed
                    try:
                        pi_session = self._get_or_create_pi_session(session_id, extra_tools)
                    except Exception as exc:
                        logger.error(f"Session creation failed: {exc}", exc_info=True)
                        await _release_attempt_lock()
                        yield Event(
                            type=EventType.ERROR,
                            source="pi-runtime",
                            session_id=session_id,
                            data={"message": f"Session creation failed: {exc}"},
                        )
                        return

                    # Register as the active embedded run — enables steer/abort from outside
                    if _active_handle is None:
                        _active_handle = EmbeddedPiRunHandle(
                            run_id=_run_id,
                            session_key=_session_key,
                            pi_session=pi_session,
                        )
                        set_active_embedded_run(session_id, _active_handle, _session_key)

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

                    # Apply system prompt on every turn, with Anthropic refusal scrub
                    effective_prompt = system_prompt or self.system_prompt
                    if effective_prompt:
                        from openclaw.agents.context import scrub_anthropic_refusal_magic
                        is_anthropic = "anthropic" in candidate_model.lower() or "claude" in candidate_model.lower()
                        if is_anthropic:
                            effective_prompt = scrub_anthropic_refusal_magic(effective_prompt)
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

                        # Trim tool call names before any other processing
                        _trim_tool_call_names_in_event(pi_event)

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
                                    if _is_abort_error(synthetic):
                                        # Clean abort — exit silently, no retry
                                        event_queue.put_nowait(_SENTINEL)
                                        return
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
                            logger.debug(f"[{session_id[:8]}] Starting _run_prompt with message length: {len(message)}")
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
                            from openclaw.agents.context_window_guard import resolve_and_guard_context_window
                    
                            # Dynamically resolve context window using guard
                            provider = candidate_model.split('/')[0] if '/' in candidate_model else 'google'
                            model_id = candidate_model.split('/')[-1] if '/' in candidate_model else candidate_model
                    
                            # Get model context window if available
                            model_context_window = None
                            if hasattr(_pi_session, '_agent') and hasattr(_pi_session._agent, '_model'):
                                agent_model = _pi_session._agent._model
                                if hasattr(agent_model, 'contextWindow'):
                                    model_context_window = agent_model.contextWindow
                    
                            # Resolve and guard context window
                            guard_result = resolve_and_guard_context_window(
                                cfg=self.config,
                                provider=provider,
                                model_id=model_id,
                                model_context_window=model_context_window,
                                default_tokens=1_048_576,
                            )
                    
                            context_window = guard_result.tokens
                    
                            # Log warnings if needed
                            if guard_result.should_block:
                                logger.error(
                                    f"Context window too small: {context_window} tokens < 16K "
                                    f"(source: {guard_result.source})"
                                )
                            elif guard_result.should_warn:
                                logger.warning(
                                    f"Context window is small: {context_window} tokens < 32K "
                                    f"(source: {guard_result.source})"
                                )
                            else:
                                logger.debug(f"Context window: {context_window} tokens (source: {guard_result.source})")
                    
                            # Use nonlocal to modify the outer scope variable
                            nonlocal context_tokens
                            context_tokens = 0
                    
                            try:
                                if hasattr(_pi_session, '_conversation_history'):
                                    # Phase 5: Apply context pruning before token estimation
                                    try:
                                        from openclaw.agents.context_pruning.pruner import prune_context_messages
                                        from openclaw.agents.context_pruning.cache_ttl import read_last_cache_ttl_timestamp
                                
                                        # Get context pruning settings from config (ensure config is not None)
                                        agents_config = (self.config or {}).get('agents', {})
                                        defaults = agents_config.get('defaults', {})
                                        pruning_config = defaults.get('contextPruning', {})
                                
                                        context_pruning_settings = {
                                            'mode': pruning_config.get('mode', 'off'),
                                            'ttl': pruning_config.get('ttl', '5m'),
                                            'softTrimRatio': pruning_config.get('softTrimRatio', 0.3),
                                            'hardClearRatio': pruning_config.get('hardClearRatio', 0.5),
                                            'keepLastAssistants': pruning_config.get('keepLastAssistants', 3),
                                            'softTrim': pruning_config.get('softTrim', {
                                                'maxChars': 4000,
                                                'headChars': 1500,
                                                'tailChars': 1500,
                                            }),
                                            'hardClear': pruning_config.get('hardClear', {
                                                'enabled': True,
                                                'placeholder': '[Old tool result content cleared]',
                                            }),
                                            'tools': pruning_config.get('tools', {
                                                'prunable': ['Read', 'Grep', 'Shell'],
                                            }),
                                            'minPrunableToolChars': pruning_config.get('minPrunableToolChars', 50000),
                                        }
                                
                                        # Get last cache touch timestamp for TTL mode
                                        last_cache_touch = None
                                        if hasattr(self, 'session_manager') and self.session_manager:
                                            last_cache_touch = read_last_cache_ttl_timestamp(self.session_manager)
                                
                                        original_len = len(_pi_session._conversation_history)
                                        pruned_history = prune_context_messages(
                                            messages=_pi_session._conversation_history,
                                            settings=context_pruning_settings,
                                            ctx={'model': {'contextWindow': context_window}},
                                            last_cache_touch_at=last_cache_touch,
                                        )
                                
                                        if pruned_history != _pi_session._conversation_history:
                                            _pi_session._conversation_history = pruned_history
                                            logger.debug(f"Context pruning applied: {original_len} messages processed")
                                        else:
                                            logger.debug("Context pruning: no changes needed")
                                    except Exception as prune_exc:
                                        logger.debug(f"Context pruning skipped: {prune_exc}")
                            
                                    context_tokens = estimate_messages_tokens(_pi_session._conversation_history)
                                    logger.debug(f"Estimated context tokens: {context_tokens}")
                            
                                    # Phase 3: Auto-compaction trigger (Safeguard)
                                    # Get compaction settings from config (ensure config is not None)
                                    agents_config = (self.config or {}).get('agents', {})
                                    defaults = agents_config.get('defaults', {})
                                    compaction_config = defaults.get('compaction', {})
                            
                                    compaction_settings = {
                                        'enabled': compaction_config.get('enabled', True),
                                        'mode': compaction_config.get('mode', 'safeguard'),
                                        'reserveTokens': compaction_config.get('reserveTokens', 16384),
                                        'keepRecentTokens': compaction_config.get('keepRecentTokens', 20000),
                                    }

                                    if should_compact(context_tokens, context_window, compaction_settings):
                                        logger.warning(
                                            f"Auto-compaction triggered: {context_tokens} tokens "
                                            f"exceeds threshold ({context_window - compaction_settings['reserveTokens']})"
                                        )
                                
                                        # Phase 3: Execute compaction (300s hard timeout — mirrors TS compactionSafetyTimeout)
                                        try:
                                            compaction_result = await asyncio.wait_for(
                                                self._execute_compaction(
                                                    session_id=session_id,
                                                    pi_session=_pi_session,
                                                    context_window=context_window,
                                                    compaction_settings=compaction_settings,
                                                ),
                                                timeout=300.0,
                                            )
                                            if compaction_result and isinstance(compaction_result, dict):
                                                summary = compaction_result.get('summary', '')
                                                logger.info(f"Compaction completed: {summary[:100]}...")
                                            else:
                                                logger.info("Using history limiting as fallback compaction strategy")
                                        except Exception as e:
                                            logger.error(f"Compaction failed: {e}", exc_info=True)
                                            logger.info("Falling back to history limiting")
                                    elif context_tokens > context_window * 0.9:
                                        logger.warning(
                                            f"Context tokens ({context_tokens}) approaching limit ({context_window})"
                                        )
                            except Exception as e:
                                logger.debug(f"Token estimation failed: {e}")
                    
                            # --- Plugin Hook: llm_input (observe prompt before LLM) ---
                            if self._hook_runner and self._hook_runner.has_hooks("llm_input"):
                                try:
                                    await self._hook_runner.run_llm_input(
                                        {"message": message, "model": candidate_model},
                                        self._build_agent_ctx(session_id),
                                    )
                                except Exception as exc:
                                    logger.debug(f"llm_input hook failed: {exc}")

                            logger.debug(f"[{session_id[:8]}] Calling pi_session.prompt")
                            if _active_handle is not None:
                                _active_handle.is_streaming = True
                            try:
                                # Build provider-specific extra params (cache_control, OpenRouter headers, etc.)
                                _extra_params = self._build_extra_params(provider, model_id)
                                import inspect as _inspect
                                _prompt_sig = _inspect.signature(_pi_session.prompt)
                                if "extra_params" in _prompt_sig.parameters and _extra_params:
                                    await _pi_session.prompt(message, pi_images, extra_params=_extra_params)
                                else:
                                    await _pi_session.prompt(message, pi_images)
                            finally:
                                if _active_handle is not None:
                                    _active_handle.is_streaming = False
                            logger.debug(f"[{session_id[:8]}] pi_session.prompt completed")

                            # --- Plugin Hook: llm_output (observe LLM output) ---
                            if self._hook_runner and self._hook_runner.has_hooks("llm_output"):
                                try:
                                    await self._hook_runner.run_llm_output(
                                        {"model": candidate_model},
                                        self._build_agent_ctx(session_id),
                                    )
                                except Exception as exc:
                                    logger.debug(f"llm_output hook failed: {exc}")
                        except Exception as exc:
                            if _is_abort_error(exc):
                                # Deliberate abort — exit cleanly without retry or error event
                                logger.info("[%s] Run aborted cleanly", session_id[:8])
                            elif _is_quota_error(exc):
                                logger.error(f"[{session_id[:8]}] _run_prompt error: {exc}", exc_info=True)
                                _quota_error.append(exc)
                            else:
                                logger.error(f"[{session_id[:8]}] _run_prompt error: {exc}", exc_info=True)
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
                            try:
                                event = await event_queue.get()
                                if event is _SENTINEL:
                                    break
                                collected_events.append(event)
                            except Exception as queue_exc:
                                logger.error(f"[{session_id[:8]}] Event queue get error: {queue_exc}", exc_info=True)
                                break
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
                        await _release_attempt_lock()
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
                        try:
                            await self._dispatch_event(ev)
                            yield ev
                        except Exception as dispatch_exc:
                            logger.error(f"[{session_id[:8]}] Event dispatch error: {dispatch_exc}", exc_info=True)
                            yield Event(
                                type=EventType.ERROR,
                                source="pi-runtime",
                                session_id=session_id,
                                data={"message": f"Event dispatch failed: {dispatch_exc}"},
                            )

                    # Phase 2: Update session token statistics after successful run
                    try:
                        from openclaw.agents.session_entry import update_session_entry_tokens
                        from openclaw.agents.usage import normalize_usage, persist_run_session_usage

                        # Extract raw usage from events (take the last usage event with data)
                        raw_usage: dict[str, Any] = {}
                        input_tokens = 0
                        output_tokens = 0
                        for evt in collected_events:
                            if hasattr(evt, 'data') and isinstance(evt.data, dict):
                                u = evt.data.get('usage', {})
                                if u:
                                    raw_usage.update(u)
                                    input_tokens += u.get('input_tokens', 0) or u.get('inputTokens', 0)
                                    output_tokens += u.get('output_tokens', 0) or u.get('outputTokens', 0)

                        # Normalise usage across providers (mirrors TS normalizeUsage)
                        norm = normalize_usage(raw_usage or None, provider=provider)
                        if norm.get("input_tokens") or norm.get("output_tokens"):
                            persist_run_session_usage(
                                session_id,
                                norm,
                                session_manager=getattr(self, "session_manager", None),
                            )
                            logger.debug(
                                "Usage (normalised): in=%s out=%s cache_read=%s cache_create=%s",
                                norm.get("input_tokens"),
                                norm.get("output_tokens"),
                                norm.get("cache_read_tokens"),
                                norm.get("cache_creation_tokens"),
                            )

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

                    # --- Plugin Hook: agent_end (fire-and-forget, parallel) ---
                    if self._hook_runner and self._hook_runner.has_hooks("agent_end") and not _quota_error:
                        try:
                            asyncio.create_task(self._hook_runner.run_agent_end(
                                {"session_key": session_id, "model": candidate_model},
                                self._build_agent_ctx(session_id),
                            ))
                        except Exception as exc:
                            logger.debug(f"agent_end hook failed: {exc}")

                    # If quota error and NO more fallbacks — check auth profile rotation
                    if _quota_error:
                        _auth_error = True
                        # Try next auth profile before giving up
                        if current_profile_idx + 1 < len(auth_profile_ids):
                            pid = auth_profile_ids[current_profile_idx]
                            if pid and self._rotation_manager:
                                self._rotation_manager.mark_failure(pid, reason="rate_limit", is_rate_limit=True)
                            current_profile_idx += 1
                            self.evict_session(session_id)
                            logger.info("Auth profile rotated to index %d, retrying", current_profile_idx)
                            break  # break inner candidates loop to retry in outer loop
                        # No more profiles — emit error and return
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

                    # Mark auth profile as good on success
                    if not _quota_error and auth_profile_ids and current_profile_idx < len(auth_profile_ids):
                        pid = auth_profile_ids[current_profile_idx]
                        if pid and self._rotation_manager:
                            self._rotation_manager.mark_success(pid)

                    await _release_attempt_lock()
                    return  # done — either success or exhausted all candidates

                    # end of inner candidates loop

                # Outer retry: if _auth_error was set and we broke out for rotation, continue
                if _auth_error and current_profile_idx < len(auth_profile_ids):
                    continue

                # Outer retry: context overflow — try compaction then truncation
                if _context_overflow:
                    pi_session_for_compact = self._pool.get(session_id)
                    if pi_session_for_compact and overflow_compaction_attempts < self.MAX_OVERFLOW_COMPACTION_ATTEMPTS:
                        overflow_compaction_attempts += 1
                        try:
                            agents_config = (self.config or {}).get("agents", {})
                            defaults = agents_config.get("defaults", {})
                            compaction_config = defaults.get("compaction", {})
                            compaction_settings = {
                                "enabled": compaction_config.get("enabled", True),
                                "mode": compaction_config.get("mode", "safeguard"),
                                "reserveTokens": compaction_config.get("reserveTokens", 16384),
                                "keepRecentTokens": compaction_config.get("keepRecentTokens", 20000),
                            }
                            result = await asyncio.wait_for(
                                self._execute_compaction(
                                    session_id, pi_session_for_compact, 1_048_576, compaction_settings
                                ),
                                timeout=300.0,
                            )
                            if result:
                                logger.info("Retry compaction succeeded, retrying turn")
                                continue
                        except Exception as compact_exc:
                            logger.warning("Retry compaction failed: %s", compact_exc)
                    # Compaction exhausted — try truncation
                    if pi_session_for_compact:
                        truncated = await self._truncate_oversized_tool_results(session_id, pi_session_for_compact)
                        if truncated:
                            logger.info("Truncated oversized results, retrying turn")
                            continue

                # No retry condition met — exit
                break

            # end of outer retry loop

            if last_error:
                yield Event(
                    type=EventType.ERROR,
                    source="pi-runtime",
                    session_id=session_id,
                    data={"message": str(last_error)},
                )

        finally:
            # Deregister active run — runs on normal exit AND GeneratorExit/cancellation
            if _active_handle is not None:
                clear_active_embedded_run(session_id, _active_handle.run_id)

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
