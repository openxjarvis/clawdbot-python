"""ACP spawn cleanup — mirrors src/acp/control-plane/spawn.ts

Provides cleanup logic when an ACP spawn fails partway through.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def cleanup_failed_acp_spawn(
    session_key: str,
    *,
    should_delete_session: bool = False,
    delete_transcript: bool = False,
    runtime_close_handle: dict | None = None,
    cfg: Any = None,
) -> None:
    """
    Best-effort cleanup after a failed ACP spawn:
    1. Close the runtime handle (if any)
    2. Close via the ACP session manager
    3. Unbind the session binding
    4. Optionally delete the gateway session

    All steps are fire-and-forget — failures are logged but do not propagate.
    """
    if runtime_close_handle:
        runtime = runtime_close_handle.get("runtime")
        handle = runtime_close_handle.get("handle")
        if runtime and handle:
            try:
                await runtime.close({"handle": handle, "reason": "spawn-failed"})
            except Exception as exc:
                logger.debug(
                    "acp-spawn: runtime cleanup close failed for %s: %s", session_key, exc
                )

    from openclaw.acp.control_plane.manager import get_acp_session_manager
    try:
        manager = get_acp_session_manager()
        await manager.close_session(
            session_key=session_key,
            reason="spawn-failed",
            allow_backend_unavailable=True,
            require_acp_session=False,
            cfg=cfg,
        )
    except Exception as exc:
        logger.debug(
            "acp-spawn: manager cleanup close failed for %s: %s", session_key, exc
        )

    if not should_delete_session:
        return

    try:
        from openclaw.gateway.rpc_client import call_gateway
        await call_gateway(
            method="sessions.delete",
            params={
                "key": session_key,
                "deleteTranscript": delete_transcript,
                "emitLifecycleHooks": False,
            },
        )
    except Exception as exc:
        logger.debug("acp-spawn: gateway delete failed for %s: %s", session_key, exc)
