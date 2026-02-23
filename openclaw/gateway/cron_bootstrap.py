"""Cron service bootstrap for Gateway

Aligned with TypeScript openclaw/src/gateway/server-cron.ts (buildGatewayCronService).

Key responsibilities:
1. Resolve store path from config
2. Create CronService with properly wired callbacks:
   - enqueue_system_event  (in-memory queue — mirrors TS system-events.ts)
   - request_heartbeat_now (wake signal)
   - run_heartbeat_once    (drain queue + run agent turn + broadcast)
   - run_isolated_agent_job
   - on_event (broadcast + run log)
3. Load existing jobs from store
4. Return GatewayCronState (start is deferred)
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..cron import CronService
    from ..cron.types import CronJob
    from .types import GatewayDeps, GatewayCronState, BroadcastFn

logger = logging.getLogger(__name__)


async def build_gateway_cron_service(
    config: dict[str, Any] | Any,
    deps: "GatewayDeps",
    broadcast: "BroadcastFn",
) -> "GatewayCronState":
    """
    Build and initialize cron service for Gateway.

    Matches TypeScript buildGatewayCronService():
    - Wires enqueueSystemEvent, requestHeartbeatNow, runHeartbeatOnce,
      runIsolatedAgentJob, and onEvent callbacks.
    - Loads jobs from disk.
    - Returns GatewayCronState (service.start() is deferred to after
      channel_manager is ready).
    """
    from ..cron import CronService
    from ..cron.store import CronStore, CronRunLog
    from ..cron.isolated_agent.run import run_cron_isolated_agent_turn
    from .types import GatewayCronState

    # ------------------------------------------------------------------
    # Resolve config dict
    # ------------------------------------------------------------------
    config_dict = _resolve_config_dict(config)
    cron_config: dict[str, Any] = (config_dict or {}).get("cron") or {}
    store_path = _resolve_store_path(cron_config)
    store_path.parent.mkdir(parents=True, exist_ok=True)
    log_dir = store_path.parent / "logs"

    logger.info(f"Cron store path: {store_path}")

    cron_enabled = (
        os.getenv("OPENCLAW_SKIP_CRON") != "1"
        and cron_config.get("enabled", True)
    )

    if not cron_enabled:
        logger.info("Cron service is disabled")
        service = CronService(cron_enabled=False)
        return GatewayCronState(cron=service, store_path=store_path, enabled=False)

    # ------------------------------------------------------------------
    # Migrate store if needed
    # ------------------------------------------------------------------
    store = CronStore(store_path)
    store.migrate_if_needed()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_session_key(agent_id: str | None, session_key: str | None) -> str:
        """Resolve the canonical session key for the given agent/session target."""
        if session_key and session_key.strip():
            return session_key.strip()
        # Default: the main WebUI session
        return "main"

    # ------------------------------------------------------------------
    # Callback: enqueue_system_event
    # Mirrors TS: enqueueSystemEvent(text, {sessionKey, contextKey})
    # ------------------------------------------------------------------
    def enqueue_system_event(
        text: str,
        agent_id: str | None = None,
        session_key: str | None = None,
        context_key: str | None = None,
    ) -> None:
        """Enqueue a system event into the in-memory queue for the given session."""
        from openclaw.infra.system_events import enqueue_system_event as _enqueue
        key = _resolve_session_key(agent_id, session_key)
        logger.info(f"cron: enqueue system event to session={key!r}: {text[:80]!r}")
        _enqueue(text, session_key=key, context_key=context_key)

    # ------------------------------------------------------------------
    # Callback: request_heartbeat_now
    # Mirrors TS: requestHeartbeatNow(opts)
    # ------------------------------------------------------------------
    def request_heartbeat_now(
        reason: str | None = None,
        agent_id: str | None = None,
        session_key: str | None = None,
    ) -> None:
        """Schedule an immediate heartbeat run as a fire-and-forget async task."""
        key = _resolve_session_key(agent_id, session_key)
        logger.info(f"cron: request_heartbeat_now reason={reason!r} session={key!r}")
        asyncio.ensure_future(
            _run_heartbeat_async(key, reason=reason, deps=deps, broadcast=broadcast)
        )

    # ------------------------------------------------------------------
    # Callback: run_heartbeat_once
    # Mirrors TS: runHeartbeatOnce(opts) -> HeartbeatRunResult
    # ------------------------------------------------------------------
    async def run_heartbeat_once(
        reason: str | None = None,
        agent_id: str | None = None,
        session_key: str | None = None,
    ) -> dict[str, Any]:
        """Drain the system event queue and run an agent turn on the session."""
        key = _resolve_session_key(agent_id, session_key)
        return await _run_heartbeat_async(key, reason=reason, deps=deps, broadcast=broadcast)

    # ------------------------------------------------------------------
    # Callback: run_isolated_agent_job
    # Matches TS: state.deps.runIsolatedAgentJob({job, message})
    # ------------------------------------------------------------------
    async def run_isolated_agent(job: "CronJob", message: str) -> dict[str, Any]:
        """Run isolated agent for cron job."""

        async def _agent_run(job: "CronJob", message: str) -> dict[str, Any]:
            try:
                cm = deps.get_channel_manager()
                runtime = cm.default_runtime if cm else None
                if runtime is None:
                    logger.warning("cron: no runtime for isolated agent job")
                    return {
                        "status": "error",
                        "error": "isolated agent runtime not configured",
                        "delivered": False,
                    }

                agent_id = getattr(job, "agent_id", None) or "default"
                base_key = f"cron:{job.id}"
                session_key = (
                    f"{agent_id}:{base_key}"
                    if agent_id and agent_id != "default"
                    else base_key
                )

                session = deps.session_manager.get_or_create_session_by_key(session_key)
                tools = (cm.tools if cm else None) or []
                system_prompt = cm.system_prompt if cm else None

                response_text = ""
                async for event in runtime.run_turn(
                    session, message, tools=tools, system_prompt=system_prompt
                ):
                    evt_type = getattr(event, "type", "")
                    if evt_type in ("text", "text_delta"):
                        data = getattr(event, "data", {}) or {}
                        chunk = data.get("text") or data.get("delta") or ""
                        response_text += str(chunk) if chunk else ""

                return {
                    "status": "ok",
                    "summary": response_text.strip(),
                    "output_text": response_text,
                    "delivered": False,
                    "session_id": str(session.id) if hasattr(session, "id") else None,
                    "session_key": session_key,
                    "error": None,
                }
            except Exception as e:
                logger.error(f"cron: isolated agent error: {e}", exc_info=True)
                return {"status": "error", "error": str(e), "delivered": False}

        return await run_cron_isolated_agent_turn(
            job=job,
            run_agent_fn=_agent_run,
            message=message,
        )

    # ------------------------------------------------------------------
    # Callback: on_event (broadcast + run log on "finished")
    # ------------------------------------------------------------------
    def on_event(event: dict[str, Any]) -> None:
        if not event:
            return
        try:
            broadcast("cron", event, {"dropIfSlow": True})

            action = event.get("action")
            job_id = event.get("jobId")

            if action == "started":
                logger.info(f"Cron job started: {job_id}")
            elif action == "finished":
                status = event.get("status")
                duration_ms = event.get("durationMs", 0)
                logger.info(
                    f"Cron job finished: {job_id}, status={status}, duration={duration_ms}ms"
                )
                if status == "error":
                    logger.error(f"Cron job error {job_id}: {event.get('error')}")

                # Append run log
                try:
                    runs_dir = log_dir.parent / "runs"
                    run_log = CronRunLog(runs_dir, job_id)
                    import time as _time
                    run_log.append({
                        "ts": event.get("ts") or int(_time.time() * 1000),
                        "jobId": job_id,
                        "action": "finished",
                        "status": status,
                        "error": event.get("error"),
                        "summary": event.get("summary"),
                        "runAtMs": event.get("runAtMs"),
                        "durationMs": duration_ms,
                        "nextRunAtMs": event.get("nextRunAtMs"),
                        "sessionId": event.get("sessionId"),
                        "sessionKey": event.get("sessionKey"),
                        "model": event.get("model"),
                        "provider": event.get("provider"),
                        "usage": event.get("usage"),
                    })
                except Exception as e:
                    logger.warning(f"Failed to append run log: {e}")

        except Exception as e:
            logger.error(f"Error handling cron event: {e}", exc_info=True)

    # ------------------------------------------------------------------
    # Create service
    # ------------------------------------------------------------------
    service = CronService(
        store_path=store_path,
        log_dir=log_dir,
        cron_enabled=cron_enabled,
        enqueue_system_event=enqueue_system_event,
        request_heartbeat_now=request_heartbeat_now,
        run_heartbeat_once=run_heartbeat_once,
        run_isolated_agent_job=run_isolated_agent,
        on_event=on_event,
    )

    # Load jobs
    jobs = store.load()
    for job in jobs:
        service.jobs[job.id] = job

    logger.info(f"Cron service initialized with {len(jobs)} jobs (start deferred)")

    return GatewayCronState(
        cron=service,
        store_path=store_path,
        enabled=cron_enabled,
    )


# ---------------------------------------------------------------------------
# Heartbeat execution helper
# ---------------------------------------------------------------------------

async def _run_heartbeat_async(
    session_key: str,
    *,
    reason: str | None,
    deps: Any,
    broadcast: Any,
) -> dict[str, Any]:
    """
    Core heartbeat runner.

    Drains the system event queue for the session, runs an agent turn with the
    queued text(s), broadcasts results to WebSocket clients, and optionally
    delivers via active channels (e.g., Telegram).

    Returns a dict matching TS HeartbeatRunResult:
      {"status": "ran" | "skipped" | "error", "reason": str | None}
    """
    from openclaw.infra.system_events import drain_system_events

    events = drain_system_events(session_key)
    if not events:
        logger.debug(f"cron: heartbeat skipped (no events) for session={session_key!r}")
        return {"status": "skipped", "reason": "no-events"}

    message = "\n".join(events)
    logger.info(
        f"cron: running heartbeat for session={session_key!r}, "
        f"events={len(events)}, reason={reason!r}"
    )

    # -- Get dependencies lazily --
    cm = deps.get_channel_manager()
    if not cm:
        logger.warning("cron: channel_manager not ready, re-queuing system events")
        # Re-enqueue so they can be delivered later
        from openclaw.infra.system_events import enqueue_system_event as _enqueue
        for e in events:
            _enqueue(e, session_key=session_key)
        return {"status": "skipped", "reason": "channel-manager-not-ready"}

    runtime = cm.default_runtime
    if not runtime:
        logger.warning("cron: no runtime available for heartbeat")
        return {"status": "error", "reason": "runtime not available"}

    # -- Get/create session --
    try:
        session = deps.session_manager.get_or_create_session_by_key(session_key)
    except Exception as e:
        logger.error(f"cron: failed to get session {session_key!r}: {e}")
        return {"status": "error", "reason": f"session error: {e}"}

    tools = (cm.tools if cm else None) or []
    system_prompt = cm.system_prompt if cm else None
    run_id = str(uuid.uuid4())

    # -- Broadcast start --
    _broadcast_chat(broadcast, session_key, run_id, "start")

    # -- Save user message to transcript (it's a system event, not a real user msg) --
    # We skip saving the "user" side for system events — just save the agent response.

    # -- Run agent turn --
    response_text = ""
    try:
        from openclaw.events import EventType as _ET
        async for event in runtime.run_turn(
            session,
            message,
            tools=tools,
            system_prompt=system_prompt,
        ):
            evt_type = getattr(event, "type", "")
            if evt_type in (_ET.TEXT, _ET.TEXT_DELTA, "text", "text_delta"):
                data = getattr(event, "data", {}) or {}
                chunk = data.get("text") or data.get("delta") or ""
                chunk = str(chunk) if chunk else ""
                if chunk:
                    response_text += chunk
                    _broadcast_chat(broadcast, session_key, run_id, "delta", text=chunk)

            elif evt_type in (_ET.ERROR, "error", "agent.error"):
                data = getattr(event, "data", {}) or {}
                err_msg = data.get("message", "Unknown error")
                logger.error(f"cron: heartbeat agent error for session={session_key!r}: {err_msg}")

    except Exception as e:
        logger.error(f"cron: heartbeat run_turn failed: {e}", exc_info=True)
        _broadcast_chat(broadcast, session_key, run_id, "error", error=str(e))
        return {"status": "error", "reason": str(e)}

    # -- Broadcast final --
    _broadcast_chat(broadcast, session_key, run_id, "final")

    # -- Deliver via active channels (e.g., Telegram) --
    if response_text:
        asyncio.ensure_future(
            _deliver_via_channels(session_key, response_text, cm)
        )

    logger.info(
        f"cron: heartbeat complete for session={session_key!r}, "
        f"response={len(response_text)} chars"
    )
    return {"status": "ran", "reason": reason}


def _broadcast_chat(
    broadcast: Any,
    session_key: str,
    run_id: str,
    state: str,
    *,
    text: str | None = None,
    error: str | None = None,
) -> None:
    """Broadcast a chat event to WebSocket clients."""
    payload: dict[str, Any] = {
        "runId": run_id,
        "sessionKey": session_key,
        "state": state,
    }
    if text is not None:
        payload["message"] = {
            "role": "assistant",
            "content": [{"type": "text", "text": text}],
            "timestamp": int(datetime.now(UTC).timestamp() * 1000),
        }
    if error is not None:
        payload["errorMessage"] = error
    try:
        broadcast("chat", payload, {})
    except Exception as e:
        logger.debug(f"cron: broadcast error: {e}")


async def _deliver_via_channels(
    session_key: str,
    response_text: str,
    cm: Any,
) -> None:
    """
    Attempt to deliver the heartbeat response to active channel sessions
    associated with the same agent.

    For now, we iterate over all running channels and send to any that have
    an active session linked to the same agent as session_key.
    This mirrors TS deliverOutboundPayloads at a simplified level.
    """
    try:
        # Find Telegram or other channels to deliver to
        running = cm.list_running() if hasattr(cm, "list_running") else []
        all_session_keys = _list_all_session_keys(cm)
        for ch_id in running:
            channel = cm.get_channel(ch_id)
            if not channel:
                continue
            # Look for telegram-based sessions associated with the same agent
            # Session keys for Telegram look like: agent:main:telegram:direct:<id>
            # The "main" part matches our heartbeat session key "main"
            agent_part = _extract_agent_part(session_key)
            for sk in all_session_keys:
                if agent_part and agent_part in sk and "telegram" in sk:
                    # Extract chat_id from session key
                    chat_id = _extract_telegram_chat_id(sk)
                    if chat_id:
                        try:
                            await channel.send_text(target=chat_id, text=response_text)
                            logger.info(
                                f"cron: delivered heartbeat to telegram chat_id={chat_id}"
                            )
                        except Exception as e:
                            logger.warning(
                                f"cron: failed to deliver to telegram chat_id={chat_id}: {e}"
                            )
    except Exception as e:
        logger.debug(f"cron: _deliver_via_channels error: {e}")


def _extract_agent_part(session_key: str) -> str | None:
    """Extract agent identifier from session key like 'main' or 'agent:main:...'."""
    parts = session_key.split(":")
    if len(parts) >= 2 and parts[0] == "agent":
        return parts[1]
    return session_key  # Use as-is for simple keys like "main"


def _extract_telegram_chat_id(session_key: str) -> str | None:
    """Extract Telegram chat_id from session key like 'agent:main:telegram:direct:8366053063'."""
    parts = session_key.split(":")
    # Format: agent:<agent>:telegram:direct:<chat_id> or agent:<agent>:telegram:group:<chat_id>
    if len(parts) >= 5 and "telegram" in parts:
        return parts[-1]
    return None


def _list_all_session_keys(cm: Any) -> list[str]:
    """List all known session keys (best-effort)."""
    try:
        sm = getattr(cm, "session_manager", None)
        if sm:
            # Use the session store (most complete) or fallback to _sessions dict
            if hasattr(sm, "_get_session_store"):
                store = sm._get_session_store()
                return list(store.keys()) if store else []
            elif hasattr(sm, "_sessions"):
                return list(sm._sessions.keys())
    except Exception:
        pass
    return []


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _resolve_config_dict(config: Any) -> dict[str, Any]:
    if config is None:
        return {}
    if hasattr(config, "model_dump"):
        return config.model_dump()
    if hasattr(config, "__dict__") and not isinstance(config, dict):
        return config.__dict__
    if isinstance(config, dict):
        return config
    return {}


def _resolve_store_path(cron_config: dict[str, Any] | None) -> Path:
    if not cron_config:
        cron_config = {}
    store_path_str = cron_config.get("store", "~/.openclaw/cron/jobs.json")
    if store_path_str.startswith("~"):
        return Path.home() / store_path_str[2:]
    return Path(store_path_str).expanduser()


def resolve_cron_store_path(config: dict[str, Any] | None) -> Path:
    if not config:
        config = {}
    cron_config = config.get("cron") or {}
    return _resolve_store_path(cron_config)


def is_cron_enabled(config: dict[str, Any] | None) -> bool:
    if os.getenv("OPENCLAW_SKIP_CRON") == "1":
        return False
    if not config:
        return True
    cron_config = config.get("cron") or {}
    return cron_config.get("enabled", True)
