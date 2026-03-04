"""Plugin Hook Runner.

Python equivalent of TypeScript src/plugins/hooks.ts createHookRunner().

Provides typed execution of all 24 plugin lifecycle hooks with:
- Priority ordering (higher priority runs first)
- Parallel execution for void hooks (asyncio.gather)
- Sequential execution for modifying hooks (result merging)
- Synchronous execution for sync-only hooks (tool_result_persist, before_message_write)
- Error isolation (errors caught and logged, don't break other hooks)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

from .types import PluginRegistry, TypedPluginHookRegistration

logger = logging.getLogger(__name__)


def _get_hooks_for_name(
    registry: PluginRegistry,
    hook_name: str,
) -> list[TypedPluginHookRegistration]:
    """Get all hooks for a given hook name, sorted by priority (higher first)."""
    return sorted(
        [h for h in registry.typed_hooks if h.hook_name == hook_name],
        key=lambda h: h.priority,
        reverse=True,
    )


class PluginHookRunner:
    """
    Typed plugin hook runner.

    Mirrors TypeScript createHookRunner() return value.

    Usage:
        runner = PluginHookRunner(registry, catch_errors=True)

        # Before sending to LLM
        result = await runner.run_before_model_resolve(event, ctx)
        if result and result.get("model_override"):
            model = result["model_override"]

        # Observe tool calls
        result = await runner.run_before_tool_call(event, ctx)
        if result and result.get("block"):
            raise BlockedError(result.get("block_reason", "blocked"))
    """

    def __init__(
        self,
        registry: PluginRegistry,
        catch_errors: bool = True,
    ) -> None:
        self._registry = registry
        self._catch_errors = catch_errors

    # =========================================================================
    # Internal execution helpers
    # =========================================================================

    async def _run_void_hook(
        self,
        hook_name: str,
        event: dict[str, Any],
        ctx: dict[str, Any],
    ) -> None:
        """Run void hooks in parallel (fire-and-forget style)."""
        hooks = _get_hooks_for_name(self._registry, hook_name)
        if not hooks:
            return

        logger.debug(f"[hooks] running {hook_name} ({len(hooks)} handlers, parallel)")

        async def _run_one(hook: TypedPluginHookRegistration) -> None:
            try:
                result = hook.handler(event, ctx)
                if asyncio.isfuture(result) or asyncio.iscoroutine(result):
                    await result
            except Exception as exc:
                msg = f"[hooks] {hook_name} handler from {hook.plugin_id} failed: {exc}"
                if self._catch_errors:
                    logger.error(msg)
                else:
                    raise RuntimeError(msg) from exc

        await asyncio.gather(*[_run_one(h) for h in hooks], return_exceptions=False)

    async def _run_modifying_hook(
        self,
        hook_name: str,
        event: dict[str, Any],
        ctx: dict[str, Any],
        merge_fn: Callable[[dict | None, dict], dict] | None = None,
    ) -> dict[str, Any] | None:
        """Run modifying hooks sequentially (priority order), merging results."""
        hooks = _get_hooks_for_name(self._registry, hook_name)
        if not hooks:
            return None

        logger.debug(f"[hooks] running {hook_name} ({len(hooks)} handlers, sequential)")

        result: dict[str, Any] | None = None

        for hook in hooks:
            try:
                handler_result = hook.handler(event, ctx)
                if asyncio.isfuture(handler_result) or asyncio.iscoroutine(handler_result):
                    handler_result = await handler_result

                if handler_result is not None:
                    if merge_fn is not None and result is not None:
                        result = merge_fn(result, handler_result)
                    else:
                        result = handler_result
            except Exception as exc:
                msg = f"[hooks] {hook_name} handler from {hook.plugin_id} failed: {exc}"
                if self._catch_errors:
                    logger.error(msg)
                else:
                    raise RuntimeError(msg) from exc

        return result

    def _run_sync_hook(
        self,
        hook_name: str,
        event: dict[str, Any],
        ctx: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Run sync-only hooks sequentially. Guard against async handlers."""
        hooks = _get_hooks_for_name(self._registry, hook_name)
        if not hooks:
            return None

        current_message = event.get("message")
        result: dict[str, Any] | None = None

        for hook in hooks:
            try:
                out = hook.handler({**event, "message": current_message} if current_message else event, ctx)

                # Guard against accidental async handlers
                if hasattr(out, "__await__") or asyncio.iscoroutine(out):
                    msg = (
                        f"[hooks] {hook_name} handler from {hook.plugin_id} returned a coroutine; "
                        f"this hook is synchronous — result ignored."
                    )
                    if self._catch_errors:
                        logger.warning(msg)
                        continue
                    raise RuntimeError(msg)

                if out is not None:
                    # For before_message_write: check block
                    if hook_name == "before_message_write" and isinstance(out, dict):
                        if out.get("block"):
                            return {"block": True}
                        new_msg = out.get("message")
                        if new_msg is not None:
                            current_message = new_msg
                    # For tool_result_persist: propagate message
                    elif hook_name == "tool_result_persist" and isinstance(out, dict):
                        new_msg = out.get("message")
                        if new_msg is not None:
                            current_message = new_msg
                    result = out

            except Exception as exc:
                msg = f"[hooks] {hook_name} handler from {hook.plugin_id} failed: {exc}"
                if self._catch_errors:
                    logger.error(msg)
                else:
                    raise RuntimeError(msg) from exc

        # Return modified message if it changed
        if current_message is not None and current_message != event.get("message"):
            return {"message": current_message}
        return result

    # =========================================================================
    # Result merge helpers
    # =========================================================================

    @staticmethod
    def _merge_before_model_resolve(
        acc: dict | None, nxt: dict
    ) -> dict:
        """Higher-priority hooks win — keep first defined override."""
        return {
            "model_override": (acc or {}).get("model_override") or nxt.get("model_override"),
            "provider_override": (acc or {}).get("provider_override") or nxt.get("provider_override"),
        }

    @staticmethod
    def _merge_before_prompt_build(
        acc: dict | None, nxt: dict
    ) -> dict:
        acc = acc or {}
        acc_prepend = acc.get("prepend_context")
        nxt_prepend = nxt.get("prepend_context")
        merged_prepend: str | None
        if acc_prepend and nxt_prepend:
            merged_prepend = f"{acc_prepend}\n\n{nxt_prepend}"
        else:
            merged_prepend = nxt_prepend or acc_prepend
        return {
            "system_prompt": nxt.get("system_prompt") or acc.get("system_prompt"),
            "prepend_context": merged_prepend,
        }

    @staticmethod
    def _merge_before_agent_start(
        acc: dict | None, nxt: dict
    ) -> dict:
        acc = acc or {}
        return {
            **PluginHookRunner._merge_before_prompt_build(acc, nxt),
            **PluginHookRunner._merge_before_model_resolve(acc, nxt),
        }

    @staticmethod
    def _merge_message_sending(
        acc: dict | None, nxt: dict
    ) -> dict:
        acc = acc or {}
        return {
            "content": nxt.get("content") or acc.get("content"),
            "cancel": nxt.get("cancel") or acc.get("cancel"),
        }

    @staticmethod
    def _merge_before_tool_call(
        acc: dict | None, nxt: dict
    ) -> dict:
        acc = acc or {}
        return {
            "params": nxt.get("params") or acc.get("params"),
            "block": nxt.get("block") or acc.get("block"),
            "block_reason": nxt.get("block_reason") or acc.get("block_reason"),
        }

    @staticmethod
    def _merge_subagent_spawning(acc: dict | None, nxt: dict) -> dict:
        """Merge subagent_spawning results. Error status wins; first non-default fields win."""
        acc = acc or {}
        # "error" status wins over "ok"
        status = "error" if (nxt.get("status") == "error" or acc.get("status") == "error") else "ok"
        return {
            "status": status,
            "error": nxt.get("error") or acc.get("error"),
            "thread_binding_ready": nxt.get("thread_binding_ready") or acc.get("thread_binding_ready", False),
        }

    @staticmethod
    def _merge_subagent_delivery_target(acc: dict | None, nxt: dict) -> dict:
        """Merge subagent_delivery_target results. First non-None origin wins."""
        acc = acc or {}
        return {
            "origin": nxt.get("origin") or acc.get("origin"),
        }

    # =========================================================================
    # Agent Hooks
    # =========================================================================

    async def run_before_model_resolve(
        self, event: dict[str, Any], ctx: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Run before_model_resolve — allows plugins to override provider/model."""
        return await self._run_modifying_hook(
            "before_model_resolve", event, ctx,
            merge_fn=self._merge_before_model_resolve,
        )

    async def run_before_prompt_build(
        self, event: dict[str, Any], ctx: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Run before_prompt_build — allows plugins to inject system prompt/context."""
        return await self._run_modifying_hook(
            "before_prompt_build", event, ctx,
            merge_fn=self._merge_before_prompt_build,
        )

    async def run_before_agent_start(
        self, event: dict[str, Any], ctx: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Run before_agent_start — legacy compatibility combining model + prompt build."""
        return await self._run_modifying_hook(
            "before_agent_start", event, ctx,
            merge_fn=self._merge_before_agent_start,
        )

    async def run_llm_input(self, event: dict[str, Any], ctx: dict[str, Any]) -> None:
        """Run llm_input — observe exact input payload sent to LLM (parallel)."""
        await self._run_void_hook("llm_input", event, ctx)

    async def run_llm_output(self, event: dict[str, Any], ctx: dict[str, Any]) -> None:
        """Run llm_output — observe exact output from LLM (parallel)."""
        await self._run_void_hook("llm_output", event, ctx)

    async def run_agent_end(self, event: dict[str, Any], ctx: dict[str, Any]) -> None:
        """Run agent_end — agent run completed (parallel)."""
        await self._run_void_hook("agent_end", event, ctx)

    async def run_before_compaction(self, event: dict[str, Any], ctx: dict[str, Any]) -> None:
        """Run before_compaction (parallel)."""
        await self._run_void_hook("before_compaction", event, ctx)

    async def run_after_compaction(self, event: dict[str, Any], ctx: dict[str, Any]) -> None:
        """Run after_compaction (parallel)."""
        await self._run_void_hook("after_compaction", event, ctx)

    async def run_before_reset(self, event: dict[str, Any], ctx: dict[str, Any]) -> None:
        """Run before_reset — fired on /new or /reset before messages are cleared (parallel)."""
        await self._run_void_hook("before_reset", event, ctx)

    # =========================================================================
    # Message Hooks
    # =========================================================================

    async def run_message_received(self, event: dict[str, Any], ctx: dict[str, Any]) -> None:
        """Run message_received (parallel)."""
        await self._run_void_hook("message_received", event, ctx)

    async def run_message_sending(
        self, event: dict[str, Any], ctx: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Run message_sending — allows plugins to modify/cancel outgoing messages (sequential)."""
        return await self._run_modifying_hook(
            "message_sending", event, ctx,
            merge_fn=self._merge_message_sending,
        )

    async def run_message_sent(self, event: dict[str, Any], ctx: dict[str, Any]) -> None:
        """Run message_sent (parallel)."""
        await self._run_void_hook("message_sent", event, ctx)

    # =========================================================================
    # Tool Hooks
    # =========================================================================

    async def run_before_tool_call(
        self, event: dict[str, Any], ctx: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Run before_tool_call — allows plugins to modify/block tool calls (sequential)."""
        return await self._run_modifying_hook(
            "before_tool_call", event, ctx,
            merge_fn=self._merge_before_tool_call,
        )

    async def run_after_tool_call(self, event: dict[str, Any], ctx: dict[str, Any]) -> None:
        """Run after_tool_call (parallel)."""
        await self._run_void_hook("after_tool_call", event, ctx)

    def run_tool_result_persist(
        self, event: dict[str, Any], ctx: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Run tool_result_persist — SYNCHRONOUS, on hot path (sequential).

        Returns dict with 'message' key if any handler modified the message.
        """
        return self._run_sync_hook("tool_result_persist", event, ctx)

    # =========================================================================
    # Message Write Hooks
    # =========================================================================

    def run_before_message_write(
        self, event: dict[str, Any], ctx: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Run before_message_write — SYNCHRONOUS, on hot path (sequential).

        Returns {'block': True} to block write, or {'message': modified_msg}.
        """
        return self._run_sync_hook("before_message_write", event, ctx)

    # =========================================================================
    # Session Hooks
    # =========================================================================

    async def run_session_start(self, event: dict[str, Any], ctx: dict[str, Any]) -> None:
        """Run session_start (parallel)."""
        await self._run_void_hook("session_start", event, ctx)

    async def run_session_end(self, event: dict[str, Any], ctx: dict[str, Any]) -> None:
        """Run session_end (parallel)."""
        await self._run_void_hook("session_end", event, ctx)

    # =========================================================================
    # Gateway Hooks
    # =========================================================================

    async def run_gateway_start(self, event: dict[str, Any], ctx: dict[str, Any]) -> None:
        """Run gateway_start (parallel)."""
        await self._run_void_hook("gateway_start", event, ctx)

    async def run_gateway_stop(self, event: dict[str, Any], ctx: dict[str, Any]) -> None:
        """Run gateway_stop (parallel)."""
        await self._run_void_hook("gateway_stop", event, ctx)

    # =========================================================================
    # Subagent Hooks (mirrors TS PluginHookHandlerMap subagent entries)
    # =========================================================================

    async def run_subagent_spawning(
        self, event: dict[str, Any], ctx: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Run subagent_spawning — modifying (sequential).

        Allows plugins to block or modify subagent spawn.
        Returns merged result with 'status' ("ok"|"error") and optional 'thread_binding_ready'.
        """
        return await self._run_modifying_hook(
            "subagent_spawning",
            event,
            ctx,
            merge_fn=self._merge_subagent_spawning,
        )

    async def run_subagent_delivery_target(
        self, event: dict[str, Any], ctx: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Run subagent_delivery_target — modifying (sequential).

        Allows plugins to override the delivery target origin for the subagent.
        Returns merged result with optional 'origin' dict.
        """
        return await self._run_modifying_hook(
            "subagent_delivery_target",
            event,
            ctx,
            merge_fn=self._merge_subagent_delivery_target,
        )

    async def run_subagent_spawned(self, event: dict[str, Any], ctx: dict[str, Any]) -> None:
        """Run subagent_spawned — void (parallel). Fired after subagent successfully created."""
        await self._run_void_hook("subagent_spawned", event, ctx)

    async def run_subagent_ended(self, event: dict[str, Any], ctx: dict[str, Any]) -> None:
        """Run subagent_ended — void (parallel). Fired after subagent run completes."""
        await self._run_void_hook("subagent_ended", event, ctx)

    # =========================================================================
    # Utility
    # =========================================================================

    def has_hooks(self, hook_name: str) -> bool:
        """Return True if any hooks are registered for the given hook name."""
        return any(h.hook_name == hook_name for h in self._registry.typed_hooks)

    def get_hook_count(self, hook_name: str) -> int:
        """Return number of registered hooks for the given hook name."""
        return sum(1 for h in self._registry.typed_hooks if h.hook_name == hook_name)


__all__ = ["PluginHookRunner"]
