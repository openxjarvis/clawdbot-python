"""Canvas tool for node canvas control.

Aligned with TypeScript openclaw/src/agents/tools/canvas-tool.ts

Supports:
- present/hide: Show or hide the canvas window on a node
- navigate: Navigate the canvas to a URL
- eval: Evaluate JavaScript in the canvas
- snapshot: Capture a screenshot of the canvas (returns MEDIA: + image)
- a2ui_push/a2ui_reset: Push or reset A2UI JSONL layout
"""
from __future__ import annotations

import base64
import logging
import tempfile
import uuid
from pathlib import Path
from typing import Any

from ..types import AgentToolResult, TextContent
from .base import AgentTool, ToolResult
from .common_results import image_result, json_result

logger = logging.getLogger(__name__)


CANVAS_ACTIONS = [
    "present",
    "hide",
    "navigate",
    "eval",
    "snapshot",
    "a2ui_push",
    "a2ui_reset",
]

CANVAS_SNAPSHOT_FORMATS = ["png", "jpg", "jpeg"]


class CanvasTool(AgentTool):
    """
    Control node canvases (present/hide/navigate/eval/snapshot/A2UI).

    Matches TypeScript createCanvasTool() from canvas-tool.ts lines 53-188
    """

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__()
        self.name = "canvas"
        self.description = (
            "Control node canvases (present/hide/navigate/eval/snapshot/A2UI). "
            "Use snapshot to capture the rendered UI."
        )
        self.config = config or {}

    def get_schema(self) -> dict[str, Any]:
        """Get tool schema matching TS CanvasToolSchema (canvas-tool.ts lines 27-51)"""
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": CANVAS_ACTIONS,
                    "description": "Canvas action to perform",
                },
                "gatewayUrl": {
                    "type": "string",
                    "description": "Gateway WebSocket URL (optional)",
                },
                "gatewayToken": {
                    "type": "string",
                    "description": "Gateway auth token (optional)",
                },
                "timeoutMs": {
                    "type": "number",
                    "description": "Request timeout in milliseconds",
                },
                "node": {
                    "type": "string",
                    "description": "Node id or name",
                },
                "target": {
                    "type": "string",
                    "description": "Present target URL (for present action; alias for url)",
                },
                "x": {"type": "number", "description": "X position for canvas window"},
                "y": {"type": "number", "description": "Y position for canvas window"},
                "width": {"type": "number", "description": "Canvas window width"},
                "height": {"type": "number", "description": "Canvas window height"},
                "url": {
                    "type": "string",
                    "description": "URL to navigate to (for navigate action; alias for target)",
                },
                "javaScript": {
                    "type": "string",
                    "description": "JavaScript code to evaluate (for eval action)",
                },
                "outputFormat": {
                    "type": "string",
                    "enum": CANVAS_SNAPSHOT_FORMATS,
                    "description": "Output format for snapshot (png/jpg/jpeg)",
                },
                "maxWidth": {"type": "number", "description": "Maximum width for snapshot"},
                "quality": {"type": "number", "description": "Image quality 0-100"},
                "delayMs": {
                    "type": "number",
                    "description": "Delay before snapshot in milliseconds",
                },
                "jsonl": {
                    "type": "string",
                    "description": "A2UI JSONL content (for a2ui_push)",
                },
                "jsonlPath": {
                    "type": "string",
                    "description": "Path to A2UI JSONL file (for a2ui_push)",
                },
            },
            "required": ["action"],
        }

    async def _execute_impl(self, params: dict[str, Any]) -> ToolResult:
        """Execute canvas action. Matches TS canvas-tool.ts execute logic (lines 61-186)"""
        action = params.get("action", "")

        if not action:
            return ToolResult(success=False, content="", error="action required")

        # Fast-path param validation for actions with obvious required fields.
        # Validate BEFORE calling _resolve_node_id (which makes a gateway RPC call)
        # so we don't waste a round-trip on obviously invalid requests.
        early_error = self._validate_action_params(action, params)
        if early_error:
            return ToolResult(success=False, content="", error=early_error)

        try:
            node_id = await self._resolve_node_id(params)
            result = await self._dispatch_action(action, node_id, params)
            # result is an AgentToolResult; convert to legacy ToolResult
            text_parts = [
                c.text for c in result.content if hasattr(c, "text")
            ]
            content_str = "\n".join(text_parts)
            return ToolResult(
                success=True,
                content=content_str,
                metadata=result.details if isinstance(result.details, dict) else {"details": result.details},
            )
        except Exception as e:
            logger.error("Canvas tool error: %s", e, exc_info=True)
            return ToolResult(success=False, content="", error=str(e))

    def _validate_action_params(self, action: str, params: dict[str, Any]) -> str | None:
        """Return an error string if required action params are missing, else None.

        Called BEFORE node resolution to fail fast without a gateway round-trip.
        Mirrors TS readStringParam(..., {required: true}) calls in canvas-tool.ts.
        """
        if action == "eval":
            if not (params.get("javaScript") or "").strip():
                return "javaScript required"
        elif action == "navigate":
            url = (params.get("url") or "").strip() or (params.get("target") or "").strip()
            if not url:
                return "url required"
        elif action == "a2ui_push":
            jsonl = (params.get("jsonl") or "").strip()
            jsonl_path = (params.get("jsonlPath") or "").strip()
            if not jsonl and not jsonl_path:
                return "jsonl or jsonlPath required"
        return None

    async def _dispatch_action(
        self,
        action: str,
        node_id: str,
        params: dict[str, Any],
    ) -> AgentToolResult:
        """Dispatch canvas action. Returns AgentToolResult."""

        if action == "present":
            placement: dict[str, Any] = {}
            for k in ["x", "y", "width", "height"]:
                if isinstance(params.get(k), (int, float)):
                    placement[k] = params[k]

            invoke_params: dict[str, Any] = {}
            # Accept both `target` and `url` (TS canvas-tool.ts lines 88-96)
            present_target = (
                (params.get("target") or "").strip()
                or (params.get("url") or "").strip()
            ) or None
            if present_target:
                invoke_params["url"] = present_target
            if placement:
                invoke_params["placement"] = placement

            await self._invoke(node_id, "canvas.present", invoke_params, params)
            return json_result({"ok": True})

        elif action == "hide":
            await self._invoke(node_id, "canvas.hide", None, params)
            return json_result({"ok": True})

        elif action == "navigate":
            url = (
                (params.get("url") or "").strip()
                or (params.get("target") or "").strip()
            ) or None
            if not url:
                raise ValueError("url required")
            await self._invoke(node_id, "canvas.navigate", {"url": url}, params)
            return json_result({"ok": True})

        elif action == "eval":
            javascript = params.get("javaScript", "").strip()
            if not javascript:
                raise ValueError("javaScript required")
            raw = await self._invoke(node_id, "canvas.eval", {"javaScript": javascript}, params)
            result_val = raw.get("payload", {}).get("result") if isinstance(raw, dict) else None
            if result_val:
                return AgentToolResult(
                    content=[TextContent(text=str(result_val))],
                    details={"result": result_val},
                )
            return json_result({"ok": True})

        elif action == "snapshot":
            return await self._handle_snapshot(node_id, params)

        elif action == "a2ui_push":
            jsonl = (params.get("jsonl") or "").strip()
            jsonl_path = (params.get("jsonlPath") or "").strip()

            if not jsonl and jsonl_path:
                jsonl = Path(jsonl_path).read_text(encoding="utf-8")

            if not jsonl.strip():
                raise ValueError("jsonl or jsonlPath required")

            await self._invoke(node_id, "canvas.a2ui.pushJSONL", {"jsonl": jsonl}, params)
            return json_result({"ok": True})

        elif action == "a2ui_reset":
            await self._invoke(node_id, "canvas.a2ui.reset", None, params)
            return json_result({"ok": True})

        else:
            raise ValueError(f"Unknown action: {action}")

    async def _handle_snapshot(
        self,
        node_id: str,
        params: dict[str, Any],
    ) -> AgentToolResult:
        """Handle canvas snapshot action.

        Mirrors TS canvas-tool.ts snapshot case (lines 113-166):
        - Calls canvas.snapshot via node.invoke
        - Decodes base64 payload
        - Saves to temp file
        - Returns imageResult with MEDIA: prefix + embedded base64
        """
        format_raw = (params.get("outputFormat") or "png").lower()
        fmt = "jpeg" if format_raw in ("jpg", "jpeg") else "png"

        max_width = params.get("maxWidth")
        if not isinstance(max_width, (int, float)) or not (max_width == max_width):  # NaN check
            max_width = None

        quality = params.get("quality")
        if not isinstance(quality, (int, float)):
            quality = None

        invoke_params: dict[str, Any] = {"format": fmt}
        if max_width is not None:
            invoke_params["maxWidth"] = int(max_width)
        if quality is not None:
            invoke_params["quality"] = int(quality)

        raw = await self._invoke(node_id, "canvas.snapshot", invoke_params, params)

        payload = raw.get("payload", {}) if isinstance(raw, dict) else {}
        if not isinstance(payload, dict):
            payload = {}

        # TS: parseCanvasSnapshotPayload — validate fields
        payload_format = str(payload.get("format", fmt))
        base64_data = str(payload.get("base64", ""))

        if not base64_data:
            raise RuntimeError("canvas.snapshot returned no image data")

        # Save to temp file (mirrors TS canvasSnapshotTempPath + writeBase64ToFile)
        ext = "jpg" if payload_format == "jpeg" else payload_format
        tmp_path = Path(tempfile.gettempdir()) / f"canvas_snapshot_{uuid.uuid4().hex}.{ext}"
        tmp_path.write_bytes(base64.b64decode(base64_data))

        mime_type = "image/jpeg" if payload_format == "jpeg" else "image/png"

        return await image_result(
            label="canvas:snapshot",
            path=str(tmp_path),
            base64_data=base64_data,
            mime_type=mime_type,
            details={"format": payload_format},
        )

    async def _resolve_node_id(self, params: dict[str, Any]) -> str:
        """Resolve node ID from params via gateway query.

        Mirrors TS resolveNodeId(gatewayOpts, node, true) from nodes-utils.ts.
        Falls back to first connected node if no node specified (allowDefault=True).
        """
        from .nodes_utils import resolve_node_id
        node = (params.get("node") or "").strip() or None
        gateway_opts: dict[str, Any] = {}
        if params.get("gatewayUrl"):
            gateway_opts["url"] = params["gatewayUrl"]
        if params.get("gatewayToken"):
            gateway_opts["token"] = params["gatewayToken"]
        return await resolve_node_id(
            gateway_opts=gateway_opts,
            query=node,
            allow_default=True,
        )

    async def _invoke(
        self,
        node_id: str,
        command: str,
        invoke_params: dict[str, Any] | None,
        tool_params: dict[str, Any],
    ) -> dict[str, Any]:
        """Invoke a canvas command on a node via gateway RPC.

        Mirrors TS `invoke()` closure in canvas-tool.ts (lines 70-76):
        calls callGatewayTool("node.invoke", opts, { nodeId, command, params, idempotencyKey })
        """
        gateway_url = tool_params.get("gatewayUrl")
        gateway_token = tool_params.get("gatewayToken")
        timeout_ms = tool_params.get("timeoutMs", 20000)
        idempotency_key = str(uuid.uuid4())

        logger.info(
            "Canvas invoke: node=%s, command=%s, timeout=%sms",
            node_id, command, timeout_ms,
        )

        try:
            from openclaw.gateway.rpc_client import GatewayRPCClient, create_client

            if gateway_url:
                client = GatewayRPCClient(url=gateway_url, auth_token=gateway_token)
            else:
                client = await create_client()

            result = await client.call("node.invoke", {
                "nodeId": node_id,
                "command": command,
                "params": invoke_params or {},
                "timeoutMs": timeout_ms,
                "idempotencyKey": idempotency_key,
            })
            return result if isinstance(result, dict) else {"payload": result}

        except Exception as e:
            logger.error("Canvas invoke failed: %s", e, exc_info=True)
            raise


def create_canvas_tool(config: dict[str, Any] | None = None) -> CanvasTool:
    """Create canvas tool instance. Matches TS createCanvasTool()"""
    return CanvasTool(config=config)
