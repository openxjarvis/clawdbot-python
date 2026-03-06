"""
NodeBashOperations — routes bash execution to a paired remote node.

Used when exec.host = "node". Sends a system.run command to the specified
node via NodeManager.invoke_node(), then streams back the output.

Mirrors TS src/agents/bash-tools.exec.ts node host path.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Callable

from .operations import BashOperations

logger = logging.getLogger(__name__)


class NodeBashOperations(BashOperations):
    """
    Bash operations that execute on a paired remote node via NodeManager.invoke_node().

    The node must be registered and active. Commands are sent as system.run
    requests; the node's _handle_system_run() runs them locally.
    """

    def __init__(self, node_id: str):
        self.node_id = node_id

    async def exec(
        self,
        command: str,
        cwd: str,
        on_data: Callable[[bytes], None],
        signal: asyncio.Event | None = None,
        timeout: int | None = None,
        env: dict[str, str] | None = None,
    ) -> dict[str, int | None]:
        from openclaw.nodes.manager import get_node_manager

        manager = get_node_manager()

        params: dict = {
            "command": ["sh", "-c", command],
            "cwd": cwd,
            "approved": True,  # Gateway has already done approval check
        }
        if env:
            params["env"] = env
        if timeout:
            params["timeoutMs"] = timeout * 1000

        try:
            result = await manager.invoke_node(
                self.node_id,
                "system.run",
                params,
                timeout_ms=(timeout * 1000) if timeout else 30_000,
            )
        except Exception as exc:
            raise RuntimeError(
                f"Node invoke failed for node '{self.node_id}': {exc}"
            ) from exc

        # result is the invocation record (queued payload); the actual output
        # arrives via node.invoke.result WebSocket event. For sync compat,
        # surface the queued result if available.
        payload = result.get("result", {}) or {}
        stdout: str = payload.get("stdout", "") or payload.get("output", "") or ""
        stderr: str = payload.get("stderr", "") or ""
        exit_code: int | None = payload.get("exitCode")

        combined = stdout
        if stderr:
            combined = combined + stderr if combined else stderr

        if combined:
            on_data(combined.encode("utf-8", errors="replace"))

        return {"exit_code": exit_code}


__all__ = ["NodeBashOperations"]
