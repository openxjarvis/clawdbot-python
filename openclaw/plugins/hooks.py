"""Plugin hook runner — mirrors src/plugins/hooks.ts"""
from __future__ import annotations

import asyncio
import inspect
import logging
from dataclasses import dataclass
from typing import Any, Callable

from .types import (
    PLUGIN_HOOK_NAMES,
    PluginHookAfterCompactionEvent,
    PluginHookAfterToolCallEvent,
    PluginHookAgentContext,
    PluginHookAgentEndEvent,
    PluginHookBeforeAgentStartEvent,
    PluginHookBeforeAgentStartResult,
    PluginHookBeforeCompactionEvent,
    PluginHookBeforeMessageWriteEvent,
    PluginHookBeforeMessageWriteResult,
    PluginHookBeforeModelResolveEvent,
    PluginHookBeforeModelResolveResult,
    PluginHookBeforePromptBuildEvent,
    PluginHookBeforePromptBuildResult,
    PluginHookBeforeResetEvent,
    PluginHookBeforeToolCallEvent,
    PluginHookBeforeToolCallResult,
    PluginHookGatewayContext,
    PluginHookGatewayStartEvent,
    PluginHookGatewayStopEvent,
    PluginHookLlmInputEvent,
    PluginHookLlmOutputEvent,
    PluginHookMessageContext,
    PluginHookMessageReceivedEvent,
    PluginHookMessageSendingEvent,
    PluginHookMessageSendingResult,
    PluginHookMessageSentEvent,
    PluginHookRegistration,
    PluginHookSessionContext,
    PluginHookSessionEndEvent,
    PluginHookSessionStartEvent,
    PluginHookToolContext,
    PluginHookToolResultPersistContext,
    PluginHookToolResultPersistEvent,
    PluginHookToolResultPersistResult,
)

logger = logging.getLogger(__name__)


@dataclass
class HookRunnerOptions:
    catch_errors: bool = True
    logger: Any = None  # HookRunnerLogger


def _get_hooks_for_name(
    typed_hooks: list[PluginHookRegistration],
    hook_name: str,
) -> list[PluginHookRegistration]:
    """Return hooks filtered by name, sorted by priority descending."""
    return sorted(
        [h for h in typed_hooks if h.hook_name == hook_name],
        key=lambda h: h.priority,
        reverse=True,
    )


def create_hook_runner(typed_hooks: list[PluginHookRegistration], options: HookRunnerOptions | None = None):
    """Create a hook runner bound to the given hook registrations.

    Mirrors createHookRunner() from plugins/hooks.ts.
    """
    opts = options or HookRunnerOptions()
    _logger = opts.logger
    catch_errors = opts.catch_errors

    def _log_debug(msg: str) -> None:
        if _logger and hasattr(_logger, "debug") and _logger.debug:
            _logger.debug(msg)
        else:
            logger.debug(msg)

    def _log_error(msg: str) -> None:
        if _logger and hasattr(_logger, "error"):
            _logger.error(msg)
        else:
            logger.error(msg)

    def _log_warn(msg: str) -> None:
        if _logger and hasattr(_logger, "warn"):
            _logger.warn(msg)
        else:
            logger.warning(msg)

    # ------------------------------------------------------------------
    # Merge helpers
    # ------------------------------------------------------------------

    def _merge_before_model_resolve(
        acc: PluginHookBeforeModelResolveResult | None,
        nxt: PluginHookBeforeModelResolveResult,
    ) -> PluginHookBeforeModelResolveResult:
        return PluginHookBeforeModelResolveResult(
            model_override=acc.model_override if acc and acc.model_override else nxt.model_override,
            provider_override=acc.provider_override if acc and acc.provider_override else nxt.provider_override,
        )

    def _merge_before_prompt_build(
        acc: PluginHookBeforePromptBuildResult | None,
        nxt: PluginHookBeforePromptBuildResult,
    ) -> PluginHookBeforePromptBuildResult:
        prepend = (
            f"{acc.prepend_context}\n\n{nxt.prepend_context}"
            if acc and acc.prepend_context and nxt.prepend_context
            else (nxt.prepend_context or (acc.prepend_context if acc else None))
        )
        return PluginHookBeforePromptBuildResult(
            system_prompt=nxt.system_prompt or (acc.system_prompt if acc else None),
            prepend_context=prepend,
        )

    # ------------------------------------------------------------------
    # Core runners
    # ------------------------------------------------------------------

    async def _run_void_hook(hook_name: str, event: Any, ctx: Any) -> None:
        hooks = _get_hooks_for_name(typed_hooks, hook_name)
        if not hooks:
            return
        _log_debug(f"[hooks] running {hook_name} ({len(hooks)} handlers)")

        async def _call(hook: PluginHookRegistration) -> None:
            try:
                result = hook.handler(event, ctx)
                if inspect.isawaitable(result):
                    await result
            except Exception as err:
                msg = f"[hooks] {hook_name} handler from {hook.plugin_id} failed: {err}"
                if catch_errors:
                    _log_error(msg)
                else:
                    raise RuntimeError(msg) from err

        await asyncio.gather(*[_call(h) for h in hooks])

    async def _run_modifying_hook(
        hook_name: str,
        event: Any,
        ctx: Any,
        merge_fn: Callable[[Any, Any], Any] | None = None,
    ) -> Any | None:
        hooks = _get_hooks_for_name(typed_hooks, hook_name)
        if not hooks:
            return None
        _log_debug(f"[hooks] running {hook_name} ({len(hooks)} handlers, sequential)")

        result: Any = None
        for hook in hooks:
            try:
                handler_result = hook.handler(event, ctx)
                if inspect.isawaitable(handler_result):
                    handler_result = await handler_result

                if handler_result is not None:
                    if merge_fn and result is not None:
                        result = merge_fn(result, handler_result)
                    else:
                        result = handler_result
            except Exception as err:
                msg = f"[hooks] {hook_name} handler from {hook.plugin_id} failed: {err}"
                if catch_errors:
                    _log_error(msg)
                else:
                    raise RuntimeError(msg) from err

        return result

    # ------------------------------------------------------------------
    # Agent hooks
    # ------------------------------------------------------------------

    async def run_before_model_resolve(
        event: PluginHookBeforeModelResolveEvent,
        ctx: PluginHookAgentContext,
    ) -> PluginHookBeforeModelResolveResult | None:
        return await _run_modifying_hook("before_model_resolve", event, ctx, _merge_before_model_resolve)

    async def run_before_prompt_build(
        event: PluginHookBeforePromptBuildEvent,
        ctx: PluginHookAgentContext,
    ) -> PluginHookBeforePromptBuildResult | None:
        return await _run_modifying_hook("before_prompt_build", event, ctx, _merge_before_prompt_build)

    async def run_before_agent_start(
        event: PluginHookBeforeAgentStartEvent,
        ctx: PluginHookAgentContext,
    ) -> PluginHookBeforeAgentStartResult | None:
        def _merge_before_agent_start(acc: Any, nxt: Any) -> Any:
            pm = _merge_before_prompt_build(acc, nxt)
            mr = _merge_before_model_resolve(acc, nxt)
            return PluginHookBeforeAgentStartResult(
                system_prompt=pm.system_prompt,
                prepend_context=pm.prepend_context,
                model_override=mr.model_override,
                provider_override=mr.provider_override,
            )

        return await _run_modifying_hook("before_agent_start", event, ctx, _merge_before_agent_start)

    async def run_llm_input(event: PluginHookLlmInputEvent, ctx: PluginHookAgentContext) -> None:
        return await _run_void_hook("llm_input", event, ctx)

    async def run_llm_output(event: PluginHookLlmOutputEvent, ctx: PluginHookAgentContext) -> None:
        return await _run_void_hook("llm_output", event, ctx)

    async def run_agent_end(event: PluginHookAgentEndEvent, ctx: PluginHookAgentContext) -> None:
        return await _run_void_hook("agent_end", event, ctx)

    async def run_before_compaction(event: PluginHookBeforeCompactionEvent, ctx: PluginHookAgentContext) -> None:
        return await _run_void_hook("before_compaction", event, ctx)

    async def run_after_compaction(event: PluginHookAfterCompactionEvent, ctx: PluginHookAgentContext) -> None:
        return await _run_void_hook("after_compaction", event, ctx)

    async def run_before_reset(event: PluginHookBeforeResetEvent, ctx: PluginHookAgentContext) -> None:
        return await _run_void_hook("before_reset", event, ctx)

    # ------------------------------------------------------------------
    # Message hooks
    # ------------------------------------------------------------------

    async def run_message_received(event: PluginHookMessageReceivedEvent, ctx: PluginHookMessageContext) -> None:
        return await _run_void_hook("message_received", event, ctx)

    async def run_message_sending(
        event: PluginHookMessageSendingEvent,
        ctx: PluginHookMessageContext,
    ) -> PluginHookMessageSendingResult | None:
        def _merge(acc: PluginHookMessageSendingResult, nxt: PluginHookMessageSendingResult) -> PluginHookMessageSendingResult:
            return PluginHookMessageSendingResult(
                content=nxt.content or acc.content,
                cancel=nxt.cancel if nxt.cancel is not None else acc.cancel,
            )

        return await _run_modifying_hook("message_sending", event, ctx, _merge)

    async def run_message_sent(event: PluginHookMessageSentEvent, ctx: PluginHookMessageContext) -> None:
        return await _run_void_hook("message_sent", event, ctx)

    # ------------------------------------------------------------------
    # Tool hooks
    # ------------------------------------------------------------------

    async def run_before_tool_call(
        event: PluginHookBeforeToolCallEvent,
        ctx: PluginHookToolContext,
    ) -> PluginHookBeforeToolCallResult | None:
        def _merge(acc: PluginHookBeforeToolCallResult, nxt: PluginHookBeforeToolCallResult) -> PluginHookBeforeToolCallResult:
            return PluginHookBeforeToolCallResult(
                params=nxt.params or acc.params,
                block=nxt.block if nxt.block is not None else acc.block,
                block_reason=nxt.block_reason or acc.block_reason,
            )

        return await _run_modifying_hook("before_tool_call", event, ctx, _merge)

    async def run_after_tool_call(event: PluginHookAfterToolCallEvent, ctx: PluginHookToolContext) -> None:
        return await _run_void_hook("after_tool_call", event, ctx)

    def run_tool_result_persist(
        event: PluginHookToolResultPersistEvent,
        ctx: PluginHookToolResultPersistContext,
    ) -> PluginHookToolResultPersistResult | None:
        """Synchronous hook — tool_result_persist runs in hot path."""
        hooks = _get_hooks_for_name(typed_hooks, "tool_result_persist")
        if not hooks:
            return None

        current = event.message

        for hook in hooks:
            try:
                out = hook.handler({**event.__dict__, "message": current}, ctx)

                if out is not None and inspect.isawaitable(out):
                    msg = (
                        f"[hooks] tool_result_persist handler from {hook.plugin_id} returned a Promise; "
                        "this hook is synchronous and the result was ignored."
                    )
                    if catch_errors:
                        _log_warn(msg)
                        continue
                    raise RuntimeError(msg)

                if out and getattr(out, "message", None) is not None:
                    current = out.message
            except Exception as err:
                msg = f"[hooks] tool_result_persist handler from {hook.plugin_id} failed: {err}"
                if catch_errors:
                    _log_error(msg)
                else:
                    raise RuntimeError(msg) from err

        return PluginHookToolResultPersistResult(message=current)

    # ------------------------------------------------------------------
    # Message write hook (sync)
    # ------------------------------------------------------------------

    def run_before_message_write(
        event: PluginHookBeforeMessageWriteEvent,
        ctx: dict,
    ) -> PluginHookBeforeMessageWriteResult | None:
        """Synchronous hook — before_message_write runs on hot path."""
        hooks = _get_hooks_for_name(typed_hooks, "before_message_write")
        if not hooks:
            return None

        current = event.message

        for hook in hooks:
            try:
                out = hook.handler({**event.__dict__, "message": current}, ctx)

                if out is not None and inspect.isawaitable(out):
                    msg = (
                        f"[hooks] before_message_write handler from {hook.plugin_id} returned a coroutine; "
                        "this hook is synchronous and the result was ignored."
                    )
                    if catch_errors:
                        _log_warn(msg)
                        continue
                    raise RuntimeError(msg)

                if isinstance(out, PluginHookBeforeMessageWriteResult):
                    if out.block:
                        return PluginHookBeforeMessageWriteResult(block=True)
                    if out.message is not None:
                        current = out.message
            except Exception as err:
                msg = f"[hooks] before_message_write handler from {hook.plugin_id} failed: {err}"
                if catch_errors:
                    _log_error(msg)
                else:
                    raise RuntimeError(msg) from err

        if current is not event.message:
            return PluginHookBeforeMessageWriteResult(message=current)
        return None

    # ------------------------------------------------------------------
    # Session hooks
    # ------------------------------------------------------------------

    async def run_session_start(event: PluginHookSessionStartEvent, ctx: PluginHookSessionContext) -> None:
        return await _run_void_hook("session_start", event, ctx)

    async def run_session_end(event: PluginHookSessionEndEvent, ctx: PluginHookSessionContext) -> None:
        return await _run_void_hook("session_end", event, ctx)

    # ------------------------------------------------------------------
    # Gateway hooks
    # ------------------------------------------------------------------

    async def run_gateway_start(event: PluginHookGatewayStartEvent, ctx: PluginHookGatewayContext) -> None:
        return await _run_void_hook("gateway_start", event, ctx)

    async def run_gateway_stop(event: PluginHookGatewayStopEvent, ctx: PluginHookGatewayContext) -> None:
        return await _run_void_hook("gateway_stop", event, ctx)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def has_hooks(hook_name: str) -> bool:
        return any(h.hook_name == hook_name for h in typed_hooks)

    def get_hook_count(hook_name: str) -> int:
        return sum(1 for h in typed_hooks if h.hook_name == hook_name)

    return HookRunner(
        run_before_model_resolve=run_before_model_resolve,
        run_before_prompt_build=run_before_prompt_build,
        run_before_agent_start=run_before_agent_start,
        run_llm_input=run_llm_input,
        run_llm_output=run_llm_output,
        run_agent_end=run_agent_end,
        run_before_compaction=run_before_compaction,
        run_after_compaction=run_after_compaction,
        run_before_reset=run_before_reset,
        run_message_received=run_message_received,
        run_message_sending=run_message_sending,
        run_message_sent=run_message_sent,
        run_before_tool_call=run_before_tool_call,
        run_after_tool_call=run_after_tool_call,
        run_tool_result_persist=run_tool_result_persist,
        run_before_message_write=run_before_message_write,
        run_session_start=run_session_start,
        run_session_end=run_session_end,
        run_gateway_start=run_gateway_start,
        run_gateway_stop=run_gateway_stop,
        has_hooks=has_hooks,
        get_hook_count=get_hook_count,
    )


@dataclass
class HookRunner:
    """Returned by create_hook_runner — mirrors HookRunner type from hooks.ts."""

    run_before_model_resolve: Any
    run_before_prompt_build: Any
    run_before_agent_start: Any
    run_llm_input: Any
    run_llm_output: Any
    run_agent_end: Any
    run_before_compaction: Any
    run_after_compaction: Any
    run_before_reset: Any
    run_message_received: Any
    run_message_sending: Any
    run_message_sent: Any
    run_before_tool_call: Any
    run_after_tool_call: Any
    run_tool_result_persist: Any
    run_before_message_write: Any
    run_session_start: Any
    run_session_end: Any
    run_gateway_start: Any
    run_gateway_stop: Any
    has_hooks: Any
    get_hook_count: Any
