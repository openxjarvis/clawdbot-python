"""Canvas tool for node canvas control.

Aligned with TypeScript openclaw/src/agents/tools/canvas-tool.ts

Supports:
- present/hide: Show or hide the canvas window on a node
- navigate: Navigate the canvas to a URL
- eval: Evaluate JavaScript in the canvas
- snapshot: Capture a screenshot of the canvas
- a2ui_push/a2ui_reset: Push or reset A2UI JSONL layout
"""
from __future__ import annotations

import json
import logging
from typing import Any, Literal

from .base import AgentTool, ToolResult

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
                    "description": "Present target URL (for present action)",
                },
                "x": {"type": "number", "description": "X position for canvas window"},
                "y": {"type": "number", "description": "Y position for canvas window"},
                "width": {"type": "number", "description": "Canvas window width"},
                "height": {"type": "number", "description": "Canvas window height"},
                "url": {
                    "type": "string",
                    "description": "URL to navigate to (for navigate action)",
                },
                "javaScript": {
                    "type": "string",
                    "description": "JavaScript code to evaluate (for eval action)",
                },
                "outputFormat": {
                    "type": "string",
                    "enum": CANVAS_SNAPSHOT_FORMATS,
                    "description": "Output format for snapshot",
                },
                "maxWidth": {"type": "number", "description": "Maximum width for snapshot"},
                "quality": {"type": "number", "description": "Image quality (0-100)"},
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

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        """Execute canvas action. Matches TS canvas-tool.ts execute logic (lines 61-186)"""
        action = params.get("action", "")

        if not action:
            return ToolResult(success=False, content="", error="action required")

        try:
            node_id = await self._resolve_node_id(params)

            if action == "present":
                placement = {}
                for k in ["x", "y", "width", "height"]:
                    if k in params:
                        placement[k] = params[k]

                invoke_params: dict[str, Any] = {}
                present_target = params.get("target") or params.get("url")
                if present_target:
                    invoke_params["url"] = present_target
                if placement:
                    invoke_params["placement"] = placement

                await self._invoke_node_command(node_id, "canvas.present", invoke_params, params)
                return ToolResult(
                    success=True,
                    content=json.dumps({"ok": True}, indent=2),
                    metadata={"ok": True},
                )

            elif action == "hide":
                await self._invoke_node_command(node_id, "canvas.hide", None, params)
                return ToolResult(
                    success=True,
                    content=json.dumps({"ok": True}, indent=2),
                    metadata={"ok": True},
                )

            elif action == "navigate":
                url = params.get("url") or params.get("target")
                if not url:
                    return ToolResult(success=False, content="", error="url required")
                await self._invoke_node_command(node_id, "canvas.navigate", {"url": url}, params)
                return ToolResult(
                    success=True,
                    content=json.dumps({"ok": True}, indent=2),
                    metadata={"ok": True},
                )

            elif action == "eval":
                javascript = params.get("javaScript")
                if not javascript:
                    return ToolResult(success=False, content="", error="javaScript required")
                raw = await self._invoke_node_command(
                    node_id, "canvas.eval", {"javaScript": javascript}, params
                )
                result = raw.get("payload", {}).get("result")
                if result:
                    return ToolResult(success=True, content=result, metadata={"result": result})
                return ToolResult(
                    success=True,
                    content=json.dumps({"ok": True}, indent=2),
                    metadata={"ok": True},
                )

            elif action == "snapshot":
                format_raw = params.get("outputFormat", "png").lower()
                fmt = "jpeg" if format_raw in ["jpg", "jpeg"] else "png"
                raw = await self._invoke_node_command(
                    node_id,
                    "canvas.snapshot",
                    {
                        "format": fmt,
                        "maxWidth": params.get("maxWidth"),
                        "quality": params.get("quality"),
                    },
                    params,
                )
                payload = raw.get("payload", {})
                base64_data = payload.get("base64", "")
                return ToolResult(
                    success=True,
                    content=f"Canvas snapshot captured (format: {fmt})",
                    metadata={"format": fmt, "base64_length": len(base64_data)},
                )

            elif action == "a2ui_push":
                jsonl = params.get("jsonl", "").strip()
                jsonl_path = params.get("jsonlPath", "").strip()

                if not jsonl and jsonl_path:
                    try:
                        with open(jsonl_path, "r", encoding="utf-8") as f:
                            jsonl = f.read()
                    except Exception as e:
                        return ToolResult(
                            success=False,
                            content="",
                            error=f"Failed to read jsonlPath: {e}",
                        )

                if not jsonl:
                    return ToolResult(success=False, content="", error="jsonl or jsonlPath required")

                await self._invoke_node_command(
                    node_id, "canvas.a2ui.pushJSONL", {"jsonl": jsonl}, params
                )
                return ToolResult(
                    success=True,
                    content=json.dumps({"ok": True}, indent=2),
                    metadata={"ok": True},
                )

            elif action == "a2ui_reset":
                await self._invoke_node_command(node_id, "canvas.a2ui.reset", None, params)
                return ToolResult(
                    success=True,
                    content=json.dumps({"ok": True}, indent=2),
                    metadata={"ok": True},
                )

            else:
                return ToolResult(success=False, content="", error=f"Unknown action: {action}")

        except Exception as e:
            logger.error(f"Canvas tool error: {e}", exc_info=True)
            return ToolResult(success=False, content="", error=str(e))

    async def _resolve_node_id(self, params: dict[str, Any]) -> str:
        """Resolve node ID from params or defaults"""
        node = params.get("node")
        if node:
            return str(node)
        return "default-node"

    async def _invoke_node_command(
        self,
        node_id: str,
        command: str,
        invoke_params: dict[str, Any] | None,
        tool_params: dict[str, Any],
    ) -> dict[str, Any]:
        """Invoke node command via gateway."""
        gateway_url = tool_params.get("gatewayUrl")
        timeout_ms = tool_params.get("timeoutMs", 20000)

        logger.info(
            f"Canvas invoke: node={node_id}, command={command}, "
            f"params={invoke_params}, timeout={timeout_ms}ms"
        )

        # TODO: Implement actual gateway call
        return {"ok": True, "payload": {}}


def create_canvas_tool(config: dict[str, Any] | None = None) -> CanvasTool:
    """Create canvas tool instance. Matches TS createCanvasTool()"""
    return CanvasTool(config=config)
