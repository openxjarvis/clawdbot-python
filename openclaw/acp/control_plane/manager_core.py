"""ACP session manager core — mirrors src/acp/control-plane/manager.core.ts

The AcpSessionManager orchestrates ACP backend sessions:
- Ensures runtime handles via the registered backend plugin
- Serializes per-session operations via SessionActorQueue
- Caches active runtime handles (RuntimeCache) with idle TTL eviction
- Manages session state / identity persistence via session_meta helpers
- Tracks turn latency and error metrics for observability
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, AsyncIterator, Callable

from openclaw.acp.runtime.errors import (
    AcpRuntimeError,
    to_acp_runtime_error,
    with_acp_runtime_error_boundary,
)
from openclaw.acp.runtime.registry import require_acp_runtime_backend
from openclaw.acp.runtime.session_identity import (
    create_identity_from_ensure,
    identity_equals,
    is_session_identity_pending,
    merge_session_identity,
    resolve_runtime_handle_identifiers_from_identity,
    resolve_session_identity_from_meta,
)
from openclaw.acp.runtime.session_meta import (
    list_acp_session_entries,
    read_acp_session_entry,
    upsert_acp_session_meta,
)
from .manager_types import (
    AcpCloseSessionInput,
    AcpCloseSessionResult,
    AcpInitializeSessionInput,
    AcpManagerObservabilitySnapshot,
    AcpRunTurnInput,
    AcpSessionResolution,
    AcpSessionStatus,
    AcpStartupIdentityReconcileResult,
    ActiveTurnState,
    TurnLatencyStats,
)
from .manager_utils import (
    create_unsupported_control_error,
    normalize_actor_key,
    normalize_acp_error_code,
    normalize_session_key,
    resolve_acp_agent_from_session_key,
    resolve_missing_meta_error,
    resolve_runtime_idle_ttl_ms,
)
from .runtime_cache import CachedRuntimeState, RuntimeCache
from .runtime_options import (
    build_runtime_control_signature,
    merge_runtime_options,
    normalize_runtime_options,
    normalize_text,
    resolve_runtime_options_from_meta,
    runtime_options_equal,
    validate_runtime_mode_input,
    validate_runtime_option_patch,
)
from .session_actor_queue import SessionActorQueue

logger = logging.getLogger(__name__)

_ACP_SESSION_KEY_PREFIX = "acp:"


def _is_acp_session_key(session_key: str) -> bool:
    return session_key.strip().lower().startswith(_ACP_SESSION_KEY_PREFIX)


class AcpSessionManager:
    """
    Central control-plane dispatcher for ACP backend sessions.

    Thread-safe (single asyncio event loop) via SessionActorQueue per-key
    serialization.
    """

    def __init__(self) -> None:
        self._actor_queue = SessionActorQueue()
        self._runtime_cache = RuntimeCache()
        self._active_turns: dict[str, ActiveTurnState] = {}
        self._turn_stats = TurnLatencyStats()
        self._error_counts: dict[str, int] = {}
        self._evicted_count = 0
        self._last_evicted_at: float | None = None

    # ------------------------------------------------------------------
    # Public high-level API
    # ------------------------------------------------------------------

    def resolve_session(self, session_key: str, cfg: Any = None) -> AcpSessionResolution:
        key = normalize_session_key(session_key)
        if not key:
            return AcpSessionResolution(kind="none", session_key=key)
        entry = read_acp_session_entry(key)
        if entry and entry.get("acp"):
            return AcpSessionResolution(kind="ready", session_key=key, meta=entry["acp"])
        if _is_acp_session_key(key):
            return AcpSessionResolution(
                kind="stale",
                session_key=key,
                error=resolve_missing_meta_error(key),
            )
        return AcpSessionResolution(kind="none", session_key=key)

    async def initialize_session(self, input: AcpInitializeSessionInput) -> dict[str, Any]:
        key = normalize_session_key(input.session_key)
        if not key:
            raise AcpRuntimeError("ACP_SESSION_INIT_FAILED", "ACP session key is required.")

        agent = (input.agent or resolve_acp_agent_from_session_key(key)).strip().lower()
        await self._evict_idle_runtime_handles(cfg=input.cfg)

        async def _do() -> dict[str, Any]:
            backend = require_acp_runtime_backend(
                getattr(input, "backend_id", None) or self._resolve_backend_id(input.cfg)
            )
            runtime = backend.runtime
            initial_opts = validate_runtime_option_patch({"cwd": input.cwd} if input.cwd else {})
            requested_cwd = initial_opts.get("cwd")

            handle = await with_acp_runtime_error_boundary(
                lambda: runtime.ensure_session({
                    "sessionKey": key,
                    "agent": agent,
                    "mode": input.mode,
                    **({"cwd": requested_cwd} if requested_cwd else {}),
                }),
                fallback_code="ACP_SESSION_INIT_FAILED",
                fallback_message="Could not initialize ACP session runtime.",
            )

            effective_cwd = normalize_text(handle.get("cwd")) or requested_cwd
            effective_opts = normalize_runtime_options({**initial_opts, **({"cwd": effective_cwd} if effective_cwd else {})})
            now = int(time.time() * 1000)
            initial_identity = merge_session_identity(
                None,
                create_identity_from_ensure(handle, now),
                now,
            ) or {"state": "pending", "source": "ensure", "lastUpdatedAt": now}

            meta: dict[str, Any] = {
                "backend": handle.get("backend") or backend.id,
                "agent": agent,
                "runtimeSessionName": handle.get("runtimeSessionName", ""),
                "identity": initial_identity,
                "mode": input.mode,
                "state": "idle",
                "lastActivityAt": now,
            }
            if effective_cwd:
                meta["cwd"] = effective_cwd
            if effective_opts:
                meta["runtimeOptions"] = effective_opts

            try:
                await upsert_acp_session_meta(key, lambda _c, _e: meta)
            except Exception as exc:
                try:
                    await runtime.close({"handle": handle, "reason": "init-meta-failed"})
                except Exception:
                    pass
                raise exc

            self._set_cached_state(key, CachedRuntimeState(
                runtime=runtime,
                handle=handle,
                backend=handle.get("backend") or backend.id,
                agent=agent,
                mode=input.mode,
                cwd=effective_cwd,
            ))
            return {"runtime": runtime, "handle": handle, "meta": meta}

        return await self._actor_queue.run(normalize_actor_key(key), _do)

    async def run_turn(self, input: AcpRunTurnInput) -> None:
        key = normalize_session_key(input.session_key)
        if not key:
            raise AcpRuntimeError("ACP_SESSION_INIT_FAILED", "ACP session key is required.")

        await self._evict_idle_runtime_handles(cfg=input.cfg)

        async def _do() -> None:
            resolution = self.resolve_session(key, input.cfg)
            if resolution.kind == "none":
                raise AcpRuntimeError("ACP_SESSION_INIT_FAILED", f"Session is not ACP-enabled: {key}")
            if resolution.kind == "stale":
                raise resolution.error

            result = await self._ensure_runtime_handle(key, resolution.meta, cfg=input.cfg)
            runtime = result["runtime"]
            handle = result["handle"]
            meta = result["meta"]
            actor_key = normalize_actor_key(key)
            turn_started = time.time()

            await self._set_session_state(key, "running", clear_last_error=True)

            cancel_event = asyncio.Event()
            active_turn = ActiveTurnState(runtime=runtime, handle=handle, cancel_event=cancel_event)
            self._active_turns[actor_key] = active_turn

            stream_error: AcpRuntimeError | None = None
            try:
                async for event in runtime.run_turn({
                    "handle": handle,
                    "text": input.text,
                    "mode": input.mode,
                    "requestId": input.request_id,
                }):
                    if cancel_event.is_set():
                        break
                    if event.get("type") == "error":
                        stream_error = AcpRuntimeError(
                            normalize_acp_error_code(event.get("code")),
                            (event.get("message") or "ACP turn failed.").strip(),
                        )
                    if input.on_event:
                        await input.on_event(event) if asyncio.iscoroutinefunction(input.on_event) else input.on_event(event)
                if stream_error:
                    raise stream_error
                self._record_turn_completion(turn_started)
                await self._set_session_state(key, "idle", clear_last_error=True)
            except Exception as exc:
                acp_err = to_acp_runtime_error(exc, fallback_code="ACP_TURN_FAILED", fallback_message="ACP turn failed.")
                self._record_turn_completion(turn_started, error_code=acp_err.code)
                await self._set_session_state(key, "error", last_error=str(acp_err))
                raise acp_err
            finally:
                if self._active_turns.get(actor_key) is active_turn:
                    del self._active_turns[actor_key]
                if meta.get("mode") == "oneshot":
                    try:
                        await runtime.close({"handle": handle, "reason": "oneshot-complete"})
                    except Exception:
                        pass
                    finally:
                        self._clear_cached_state(key)

        await self._actor_queue.run(normalize_actor_key(key), _do)

    async def cancel_session(self, session_key: str, reason: str = "user-cancel", cfg: Any = None) -> None:
        key = normalize_session_key(session_key)
        if not key:
            raise AcpRuntimeError("ACP_SESSION_INIT_FAILED", "ACP session key is required.")
        actor_key = normalize_actor_key(key)
        active = self._active_turns.get(actor_key)
        if active:
            if active.cancel_event:
                active.cancel_event.set()
            try:
                await with_acp_runtime_error_boundary(
                    lambda: active.runtime.cancel({"handle": active.handle, "reason": reason}),
                    fallback_code="ACP_TURN_FAILED",
                    fallback_message="ACP cancel failed.",
                )
            except Exception:
                pass
            return

        async def _do() -> None:
            resolution = self.resolve_session(key, cfg)
            if resolution.kind == "none":
                raise AcpRuntimeError("ACP_SESSION_INIT_FAILED", f"Session is not ACP-enabled: {key}")
            if resolution.kind == "stale":
                raise resolution.error
            result = await self._ensure_runtime_handle(key, resolution.meta, cfg=cfg)
            await with_acp_runtime_error_boundary(
                lambda: result["runtime"].cancel({"handle": result["handle"], "reason": reason}),
                fallback_code="ACP_TURN_FAILED",
                fallback_message="ACP cancel failed.",
            )
            await self._set_session_state(key, "idle", clear_last_error=True)

        await self._actor_queue.run(actor_key, _do)

    async def close_session(
        self,
        session_key: str,
        reason: str,
        *,
        clear_meta: bool = False,
        allow_backend_unavailable: bool = False,
        require_acp_session: bool = True,
        cfg: Any = None,
    ) -> AcpCloseSessionResult:
        key = normalize_session_key(session_key)
        if not key:
            raise AcpRuntimeError("ACP_SESSION_INIT_FAILED", "ACP session key is required.")

        async def _do() -> AcpCloseSessionResult:
            resolution = self.resolve_session(key, cfg)
            if resolution.kind == "none":
                if require_acp_session:
                    raise AcpRuntimeError("ACP_SESSION_INIT_FAILED", f"Session is not ACP-enabled: {key}")
                return AcpCloseSessionResult(runtime_closed=False, meta_cleared=False)
            if resolution.kind == "stale":
                if require_acp_session:
                    raise resolution.error
                return AcpCloseSessionResult(runtime_closed=False, meta_cleared=False)

            runtime_closed = False
            runtime_notice: str | None = None
            try:
                result = await self._ensure_runtime_handle(key, resolution.meta, cfg=cfg)
                await with_acp_runtime_error_boundary(
                    lambda: result["runtime"].close({"handle": result["handle"], "reason": reason}),
                    fallback_code="ACP_TURN_FAILED",
                    fallback_message="ACP close failed.",
                )
                runtime_closed = True
                self._clear_cached_state(key)
            except AcpRuntimeError as exc:
                if allow_backend_unavailable and exc.code in ("ACP_BACKEND_MISSING", "ACP_BACKEND_UNAVAILABLE"):
                    self._clear_cached_state(key)
                    runtime_notice = str(exc)
                else:
                    raise

            meta_cleared = False
            if clear_meta:
                await upsert_acp_session_meta(key, lambda _c, _e: None)
                meta_cleared = True

            return AcpCloseSessionResult(
                runtime_closed=runtime_closed,
                runtime_notice=runtime_notice,
                meta_cleared=meta_cleared,
            )

        return await self._actor_queue.run(normalize_actor_key(key), _do)

    async def get_session_status(self, session_key: str, cfg: Any = None) -> AcpSessionStatus:
        key = normalize_session_key(session_key)
        if not key:
            raise AcpRuntimeError("ACP_SESSION_INIT_FAILED", "ACP session key is required.")

        async def _do() -> AcpSessionStatus:
            resolution = self.resolve_session(key, cfg)
            if resolution.kind == "none":
                raise AcpRuntimeError("ACP_SESSION_INIT_FAILED", f"Session is not ACP-enabled: {key}")
            if resolution.kind == "stale":
                raise resolution.error
            result = await self._ensure_runtime_handle(key, resolution.meta, cfg=cfg)
            runtime = result["runtime"]
            handle = result["handle"]
            meta = result["meta"]
            caps = await self._resolve_runtime_capabilities(runtime, handle)
            runtime_status = None
            if hasattr(runtime, "get_status"):
                try:
                    runtime_status = await with_acp_runtime_error_boundary(
                        lambda: runtime.get_status({"handle": handle}),
                        fallback_code="ACP_TURN_FAILED",
                        fallback_message="Could not read ACP runtime status.",
                    )
                except Exception:
                    pass
            identity = resolve_session_identity_from_meta(meta)
            return AcpSessionStatus(
                session_key=key,
                backend=handle.get("backend") or meta.get("backend", ""),
                agent=meta.get("agent", ""),
                state=meta.get("state"),
                mode=meta.get("mode", "persistent"),
                runtime_options=resolve_runtime_options_from_meta(meta),
                capabilities=caps,
                identity=identity,
                runtime_status=runtime_status,
                last_activity_at=meta.get("lastActivityAt", 0),
                last_error=meta.get("lastError"),
            )

        return await self._actor_queue.run(normalize_actor_key(key), _do)

    def get_observability_snapshot(self, cfg: Any = None) -> dict[str, Any]:
        completed = self._turn_stats.completed + self._turn_stats.failed
        avg_latency = round(self._turn_stats.total_ms / completed) if completed > 0 else 0
        return {
            "runtimeCache": {
                "activeSessions": self._runtime_cache.size(),
                "idleTtlMs": resolve_runtime_idle_ttl_ms(cfg),
                "evictedTotal": self._evicted_count,
                **({"lastEvictedAt": self._last_evicted_at} if self._last_evicted_at else {}),
            },
            "turns": {
                "active": len(self._active_turns),
                "queueDepth": self._actor_queue.get_total_pending_count(),
                "completed": self._turn_stats.completed,
                "failed": self._turn_stats.failed,
                "averageLatencyMs": avg_latency,
                "maxLatencyMs": self._turn_stats.max_ms,
            },
            "errorsByCode": dict(sorted(self._error_counts.items())),
        }

    async def reconcile_pending_session_identities(self, cfg: Any = None) -> AcpStartupIdentityReconcileResult:
        result = AcpStartupIdentityReconcileResult()
        try:
            sessions = await list_acp_session_entries()
        except Exception as exc:
            logger.debug("acp-manager: startup identity scan failed: %s", exc)
            result.failed += 1
            return result

        for session in sessions:
            if not session.get("acp") or not session.get("sessionKey"):
                continue
            current_identity = resolve_session_identity_from_meta(session["acp"])
            if not is_session_identity_pending(current_identity):
                continue
            result.checked += 1
            try:
                resolution = self.resolve_session(session["sessionKey"], cfg)
                if resolution.kind == "ready":
                    result.resolved += 1
            except Exception as exc:
                result.failed += 1
                logger.debug("acp-manager: startup reconcile failed for %s: %s", session["sessionKey"], exc)

        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_backend_id(self, cfg: Any) -> str | None:
        if not cfg:
            return None
        acp = getattr(cfg, "acp", None) or {}
        return (acp.get("backend") if isinstance(acp, dict) else getattr(acp, "backend", None)) or None

    async def _ensure_runtime_handle(
        self, session_key: str, meta: dict, cfg: Any = None
    ) -> dict[str, Any]:
        agent = (meta.get("agent") or resolve_acp_agent_from_session_key(session_key)).strip().lower()
        mode = meta.get("mode", "persistent")
        runtime_options = resolve_runtime_options_from_meta(meta)
        cwd = runtime_options.get("cwd") or normalize_text(meta.get("cwd"))
        backend_id = (meta.get("backend") or self._resolve_backend_id(cfg) or "").strip()

        cached = self._runtime_cache.get(normalize_actor_key(session_key))
        if cached:
            backend_match = not backend_id or cached.backend == backend_id
            if (backend_match and cached.agent == agent and cached.mode == mode
                    and (cached.cwd or "") == (cwd or "")):
                return {"runtime": cached.runtime, "handle": cached.handle, "meta": meta}
            self._clear_cached_state(session_key)

        backend = require_acp_runtime_backend(backend_id or None)
        runtime = backend.runtime
        handle = await with_acp_runtime_error_boundary(
            lambda: runtime.ensure_session({
                "sessionKey": session_key,
                "agent": agent,
                "mode": mode,
                **({"cwd": cwd} if cwd else {}),
            }),
            fallback_code="ACP_SESSION_INIT_FAILED",
            fallback_message="Could not initialize ACP session runtime.",
        )

        effective_cwd = normalize_text(handle.get("cwd")) or cwd
        next_opts = normalize_runtime_options({**runtime_options, **({"cwd": effective_cwd} if effective_cwd else {})})
        now = int(time.time() * 1000)
        prev_identity = resolve_session_identity_from_meta(meta)
        next_identity = merge_session_identity(
            prev_identity,
            create_identity_from_ensure(handle, now),
            now,
        )
        if not identity_equals(prev_identity, next_identity):
            updated_meta = {**meta, "identity": next_identity} if next_identity else meta
            if next_opts:
                updated_meta["runtimeOptions"] = next_opts
            if effective_cwd:
                updated_meta["cwd"] = effective_cwd
            try:
                await upsert_acp_session_meta(session_key, lambda _c, _e: updated_meta)
                meta = updated_meta
            except Exception:
                pass

        self._set_cached_state(session_key, CachedRuntimeState(
            runtime=runtime,
            handle=handle,
            backend=handle.get("backend") or backend.id,
            agent=agent,
            mode=mode,
            cwd=effective_cwd,
        ))
        return {"runtime": runtime, "handle": handle, "meta": meta}

    def _get_cached_state(self, session_key: str) -> CachedRuntimeState | None:
        return self._runtime_cache.get(normalize_actor_key(session_key))

    def _set_cached_state(self, session_key: str, state: CachedRuntimeState) -> None:
        self._runtime_cache.set(normalize_actor_key(session_key), state)

    def _clear_cached_state(self, session_key: str) -> None:
        self._runtime_cache.clear(normalize_actor_key(session_key))

    async def _resolve_runtime_capabilities(self, runtime: Any, handle: dict) -> dict:
        if hasattr(runtime, "get_capabilities"):
            try:
                return await runtime.get_capabilities({"handle": handle}) or {}
            except Exception:
                pass
        return {"controls": []}

    async def _set_session_state(
        self,
        session_key: str,
        state: str,
        *,
        clear_last_error: bool = False,
        last_error: str | None = None,
    ) -> None:
        def _mutate(current: dict | None, _entry: Any) -> dict | None:
            if current is None:
                return None
            updated = {**current, "state": state, "lastActivityAt": int(time.time() * 1000)}
            if clear_last_error:
                updated.pop("lastError", None)
            elif last_error is not None:
                updated["lastError"] = last_error
            return updated
        try:
            await upsert_acp_session_meta(session_key, _mutate)
        except Exception:
            pass

    def _record_turn_completion(self, started_at: float, error_code: str | None = None) -> None:
        elapsed_ms = (time.time() - started_at) * 1000
        if error_code:
            self._turn_stats.failed += 1
            self._error_counts[error_code] = self._error_counts.get(error_code, 0) + 1
        else:
            self._turn_stats.completed += 1
        self._turn_stats.total_ms += elapsed_ms
        if elapsed_ms > self._turn_stats.max_ms:
            self._turn_stats.max_ms = elapsed_ms

    async def _evict_idle_runtime_handles(self, cfg: Any = None) -> None:
        idle_ttl_ms = resolve_runtime_idle_ttl_ms(cfg)
        if idle_ttl_ms <= 0:
            return
        candidates = self._runtime_cache.collect_idle_candidates(idle_ttl_ms)
        for snapshot in candidates:
            state = snapshot.state
            try:
                await state.runtime.close({"handle": state.handle, "reason": "idle-eviction"})
            except Exception:
                pass
            finally:
                self._runtime_cache.clear(snapshot.actor_key)
                self._evicted_count += 1
                self._last_evicted_at = time.time()
