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

        # Resolve job-level identifiers once so _agent_run can use them
        job_agent_id = getattr(job, "agent_id", None) or "default"
        base_session_key = (
            getattr(job, "session_key", None) or f"cron:{job.id}"
        ).strip()
        job_session_key = (
            f"{job_agent_id}:{base_session_key}"
            if job_agent_id and job_agent_id != "default"
            and not base_session_key.startswith(f"{job_agent_id}:")
            else base_session_key
        )

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

                session = deps.session_manager.get_or_create_session_by_key(job_session_key)
                tools = (cm.tools if cm else None) or []
                system_prompt = cm.system_prompt if cm else None

                # ----------------------------------------------------------
                # Model selection chain: mirrors TS runCronIsolatedAgentTurn
                # Priority: hooks.gmail.model > job.payload.model > session override > default
                # ----------------------------------------------------------
                model_override: str | None = None

                # 1. hooks.gmail.model override for Gmail hook sessions
                if base_session_key.startswith("hook:gmail:"):
                    try:
                        from openclaw.agents.model_selection import resolve_hooks_gmail_model
                        gmail_model = resolve_hooks_gmail_model(config_dict)
                        if gmail_model:
                            model_override = gmail_model
                    except Exception:
                        pass

                # 2. Job payload model override (agentTurn.model)
                if model_override is None:
                    payload_model = getattr(getattr(job, "payload", None), "model", None)
                    if payload_model and isinstance(payload_model, str) and payload_model.strip():
                        model_override = payload_model.strip()

                # 3. Session model override (user-set via /model command)
                if model_override is None:
                    try:
                        session_entry = getattr(session, "entry", None) or {}
                        if isinstance(session_entry, dict):
                            model_override = session_entry.get("modelOverride") or None
                        elif hasattr(session_entry, "modelOverride"):
                            model_override = session_entry.modelOverride or None
                    except Exception:
                        pass

                response_text = ""
                run_kwargs: dict[str, Any] = {
                    "tools": tools,
                    "system_prompt": system_prompt,
                }
                if model_override:
                    run_kwargs["model_override"] = model_override

                async for event in runtime.run_turn(session, message, **run_kwargs):
                    evt_type = getattr(event, "type", "")
                    if evt_type in ("text", "text_delta"):
                        data = getattr(event, "data", {}) or {}
                        chunk = data.get("text") or data.get("delta") or ""
                        response_text += str(chunk) if chunk else ""

                # Collect basic telemetry if runtime exposes it
                used_model: str | None = None
                used_provider: str | None = None
                usage: dict[str, Any] | None = None
                try:
                    last_meta = getattr(runtime, "last_run_meta", None)
                    if isinstance(last_meta, dict):
                        used_model = last_meta.get("model") or model_override
                        used_provider = last_meta.get("provider")
                        usage = last_meta.get("usage")
                except Exception:
                    pass

                return {
                    "status": "ok",
                    "summary": response_text.strip(),
                    "output_text": response_text,
                    "delivered": False,
                    "session_id": str(session.id) if hasattr(session, "id") else None,
                    "session_key": job_session_key,
                    "model": used_model or model_override,
                    "provider": used_provider,
                    "usage": usage,
                    "error": None,
                }
            except Exception as e:
                logger.error(f"cron: isolated agent error: {e}", exc_info=True)
                return {"status": "error", "error": str(e), "delivered": False}

        return await run_cron_isolated_agent_turn(
            job=job,
            run_agent_fn=_agent_run,
            message=message,
            session_key=job_session_key,
            config=config,
            agent_id=job_agent_id,
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
    Deliver the heartbeat response to active channel sessions (e.g. Telegram).

    Uses split_media_from_output to extract MEDIA: tokens from the agent response
    (mirrors TS splitMediaFromOutput / deliverReplies). The cleaned text is sent
    first, then any media files are sent as attachments.
    """
    from pathlib import Path
    from openclaw.auto_reply.media_parse import split_media_from_output
    from openclaw.media.mime import detect_mime, media_kind_from_mime, MediaKind

    try:
        running = cm.list_running() if hasattr(cm, "list_running") else []
        all_session_keys = _list_all_session_keys(cm)
        agent_part = _extract_agent_part(session_key)

        # Resolve cron session workspace for relative-path media resolution
        _cron_workspace: str | None = None
        try:
            sm = getattr(cm, "session_manager", None)
            if sm:
                _cron_session = sm.get_or_create_session_by_key(session_key)
                if _cron_session:
                    from openclaw.agents.session_workspace import resolve_session_workspace_dir
                    _cron_workspace = str(resolve_session_workspace_dir(
                        workspace_root=_cron_session.workspace_dir,
                        session_key=session_key,
                    ))
        except Exception:
            pass

        # Parse MEDIA: tokens — strip them from display text, collect URLs
        media_result = split_media_from_output(response_text)
        display_text = media_result.text if media_result.text is not None else response_text
        all_media: list[str] = []
        if media_result.media_url:
            all_media.append(media_result.media_url)
        if media_result.media_urls:
            all_media.extend(media_result.media_urls)

        for ch_id in running:
            channel = cm.get_channel(ch_id)
            if not channel:
                continue
            for sk in all_session_keys:
                if agent_part and agent_part in sk and "telegram" in sk:
                    chat_id = _extract_telegram_chat_id(sk)
                    if not chat_id:
                        continue

                    # Send text (without MEDIA: lines)
                    if display_text:
                        try:
                            await channel.send_text(target=chat_id, text=display_text)
                            logger.info(f"cron: delivered text to telegram chat_id={chat_id}")
                        except Exception as e:
                            logger.warning(f"cron: send_text failed chat_id={chat_id}: {e}")

                    # Send media files extracted from MEDIA: tokens
                    for media_url in all_media:
                        try:
                            # Resolve relative paths against known workspace locations
                            resolved_url = media_url
                            if not media_url.startswith(("http://", "https://", "file://", "/")):
                                # Search order:
                                # 1. cron session workspace
                                # 2. all agent workspaces under ~/.openclaw/workspace/
                                #    (covers files made in Telegram / other sessions)
                                # 3. CWD
                                # 4. home dir
                                search_dirs = []
                                if _cron_workspace:
                                    search_dirs.append(Path(_cron_workspace))
                                _oc_workspace_root = Path.home() / ".openclaw" / "workspace"
                                if _oc_workspace_root.is_dir():
                                    try:
                                        for _ws_dir in sorted(
                                            _oc_workspace_root.iterdir(),
                                            key=lambda p: p.stat().st_mtime,
                                            reverse=True,  # newest workspaces first
                                        ):
                                            if _ws_dir.is_dir() and _ws_dir not in search_dirs:
                                                search_dirs.append(_ws_dir)
                                    except Exception:
                                        pass
                                search_dirs.append(Path.cwd())
                                search_dirs.append(Path.home())
                                for search_dir in search_dirs:
                                    candidate = search_dir / media_url
                                    if candidate.exists():
                                        resolved_url = str(candidate)
                                        logger.info(f"cron: resolved relative path '{media_url}' -> {resolved_url}")
                                        break
                                else:
                                    # Not found anywhere — skip gracefully
                                    logger.warning(
                                        f"cron: media file '{media_url}' not found in any workspace, skipping"
                                    )
                                    continue

                            mime = detect_mime(resolved_url)
                            kind = media_kind_from_mime(mime)
                            media_type = kind.value if kind != MediaKind.UNKNOWN else "document"
                            await channel.send_media(
                                target=chat_id,
                                media_url=resolved_url,
                                media_type=media_type,
                            )
                            logger.info(
                                f"cron: delivered media {Path(resolved_url).name} "
                                f"(type={media_type}) to chat_id={chat_id}"
                            )
                        except Exception as e:
                            logger.warning(
                                f"cron: failed to send media {media_url} to chat_id={chat_id}: {e}"
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
