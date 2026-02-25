"""Nodes tool for device control (camera, screen, location, notifications)"""

import logging
from typing import Any

from .base import AgentTool, ToolResult

logger = logging.getLogger(__name__)


class NodesTool(AgentTool):
    """Control connected devices (nodes) - camera, screen recording, location, notifications"""

    def __init__(self):
        super().__init__()
        self.name = "nodes"
        self.description = (
            "Control connected devices for camera, screen recording, location, and notifications"
        )
        self._paired_nodes: dict[str, Any] = {}

    def get_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "status",
                        "describe",
                        "pending",
                        "approve",
                        "reject",
                        "notify",
                        "camera_snap",
                        "camera_list",
                        "camera_clip",
                        "screen_record",
                        "location_get",
                        "run",
                        "invoke",
                    ],
                    "description": "Node action to perform",
                },
                "node_id": {
                    "type": "string",
                    "description": "Node identifier (optional, uses default)",
                },
                "message": {
                    "type": "string",
                    "description": "Notification message (for notify action)",
                },
                "title": {"type": "string", "description": "Notification title"},
                "camera_id": {
                    "type": "string",
                    "description": "Camera identifier (for camera actions)",
                },
                "duration": {
                    "type": "integer",
                    "description": "Recording duration in seconds",
                    "default": 10,
                },
                "output_path": {"type": "string", "description": "Output file path for media"},
                "command": {
                    "type": "string",
                    "description": "System command to run (for run action)",
                },
            },
            "required": ["action"],
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        """Execute node action"""
        action = params.get("action", "")

        if not action:
            return ToolResult(success=False, content="", error="action required")

        try:
            if action == "status":
                return await self._status(params)
            elif action == "describe":
                return await self._describe(params)
            elif action == "pending":
                return await self._pending(params)
            elif action == "approve":
                return await self._approve(params)
            elif action == "reject":
                return await self._reject(params)
            elif action == "notify":
                return await self._notify(params)
            elif action == "camera_snap":
                return await self._camera_snap(params)
            elif action == "camera_list":
                return await self._camera_list(params)
            elif action == "camera_clip":
                return await self._camera_clip(params)
            elif action == "screen_record":
                return await self._screen_record(params)
            elif action == "location_get":
                return await self._location_get(params)
            elif action == "run":
                return await self._run_command(params)
            elif action == "invoke":
                return await self._invoke(params)
            else:
                return ToolResult(success=False, content="", error=f"Unknown action: {action}")

        except Exception as e:
            logger.error(f"Nodes tool error: {e}", exc_info=True)
            return ToolResult(success=False, content="", error=str(e))

    async def _status(self, params: dict[str, Any]) -> ToolResult:
        """Get nodes status"""
        if not self._paired_nodes:
            return ToolResult(success=True, content="No nodes paired", metadata={"count": 0})

        output = f"Paired nodes ({len(self._paired_nodes)}):\n\n"
        for node_id, node_info in self._paired_nodes.items():
            output += f"- **{node_id}**: {node_info.get('platform', 'unknown')}\n"

        return ToolResult(success=True, content=output, metadata={"count": len(self._paired_nodes)})

    async def _pending(self, params: dict[str, Any]) -> ToolResult:
        """List pending pairing requests (matches TS nodes-tool.ts pending action)"""
        logger.info("Checking pending node pairing requests")
        
        try:
            # Call gateway RPC
            from openclaw.gateway.rpc_client import create_client
            
            client = await create_client()
            result = await client.call("node.pair.pending", {})
            
            pending = result.get("pending", [])
            
            if not pending:
                return ToolResult(
                    success=True,
                    content="No pending pairing requests",
                    metadata={"pending": []},
                )
            
            content = f"Found {len(pending)} pending pairing request(s):\n\n"
            for req in pending:
                request_id = req.get("id", "unknown")
                node_name = req.get("name", "Unknown")
                content += f"- **{request_id}**: {node_name}\n"
            
            return ToolResult(
                success=True,
                content=content,
                metadata={"pending": pending, "count": len(pending)},
            )
        except Exception as e:
            logger.error(f"Failed to check pending requests: {e}", exc_info=True)
            return ToolResult(
                success=True,
                content="No pending pairing requests",
                metadata={"pending": []},
            )
    
    async def _approve(self, params: dict[str, Any]) -> ToolResult:
        """Approve pending pairing request (matches TS nodes-tool.ts approve action)"""
        request_id = params.get("requestId") or params.get("node_id")
        if not request_id:
            return ToolResult(success=False, content="", error="requestId required")
        
        logger.info(f"Approving node pairing request: {request_id}")
        
        try:
            # Call gateway RPC
            from openclaw.gateway.rpc_client import create_client
            
            client = await create_client()
            result = await client.call("node.pair.approve", {"requestId": request_id})
            
            if result.get("ok"):
                return ToolResult(
                    success=True,
                    content=f"✓ Approved pairing request: {request_id}",
                    metadata={"approved": request_id, "result": result},
                )
            else:
                error_msg = result.get("error", "Unknown error")
                return ToolResult(
                    success=False,
                    content="",
                    error=f"Failed to approve: {error_msg}",
                )
        except Exception as e:
            logger.error(f"Failed to approve pairing request: {e}", exc_info=True)
            return ToolResult(
                success=False,
                content="",
                error=f"Failed to approve: {e}",
            )
    
    async def _reject(self, params: dict[str, Any]) -> ToolResult:
        """Reject pending pairing request (matches TS nodes-tool.ts reject action)"""
        request_id = params.get("requestId") or params.get("node_id")
        if not request_id:
            return ToolResult(success=False, content="", error="requestId required")
        
        logger.info(f"Rejecting node pairing request: {request_id}")
        
        try:
            # Call gateway RPC
            from openclaw.gateway.rpc_client import create_client
            
            client = await create_client()
            result = await client.call("node.pair.reject", {"requestId": request_id})
            
            if result.get("ok"):
                return ToolResult(
                    success=True,
                    content=f"✗ Rejected pairing request: {request_id}",
                    metadata={"rejected": request_id, "result": result},
                )
            else:
                error_msg = result.get("error", "Unknown error")
                return ToolResult(
                    success=False,
                    content="",
                    error=f"Failed to reject: {error_msg}",
                )
        except Exception as e:
            logger.error(f"Failed to reject pairing request: {e}", exc_info=True)
            return ToolResult(
                success=False,
                content="",
                error=f"Failed to reject: {e}",
            )
    
    async def _invoke(self, params: dict[str, Any]) -> ToolResult:
        """Generic node invoke command (matches TS nodes-tool.ts invoke action)"""
        command = params.get("invokeCommand") or params.get("command")
        if not command:
            return ToolResult(success=False, content="", error="invokeCommand required")
        
        invoke_params_json = params.get("invokeParamsJson", "{}")
        node_id = params.get("node_id") or params.get("nodeId") or "default"
        
        try:
            import json as json_lib
            invoke_params = json_lib.loads(invoke_params_json)
        except json_lib.JSONDecodeError as e:
            return ToolResult(
                success=False,
                content="",
                error=f"Invalid invokeParamsJson: {e}",
            )
        
        logger.info(f"Invoking node command: {command} on {node_id} with params {invoke_params}")
        
        try:
            # Call gateway RPC
            from openclaw.gateway.rpc_client import create_client
            
            client = await create_client()
            result = await client.call("node.invoke", {
                "nodeId": node_id,
                "command": command,
                "params": invoke_params,
                "timeoutMs": params.get("timeoutMs", 30000),
            })
            
            if result.get("ok"):
                payload = result.get("payload", {})
                return ToolResult(
                    success=True,
                    content=f"✓ Invoked command: {command}",
                    metadata={"command": command, "result": payload},
                )
            else:
                error_info = result.get("error", "Unknown error")
                return ToolResult(
                    success=False,
                    content="",
                    error=f"Command failed: {error_info}",
                )
        except Exception as e:
            logger.error(f"Failed to invoke node command: {e}", exc_info=True)
            return ToolResult(
                success=False,
                content="",
                error=f"Failed to invoke: {e}",
            )
    
    async def _camera_clip(self, params: dict[str, Any]) -> ToolResult:
        """Record camera video clip (matches TS nodes-tool.ts camera_clip action)"""
        duration = params.get("duration", 5)
        output_path = params.get("output_path", "clip.mp4")
        
        logger.warning("camera_clip requires paired mobile device")
        return ToolResult(
            success=False,
            content="",
            error=f"Camera clip requires paired iOS/Android node (duration={duration}s, output={output_path})",
        )

    async def _describe(self, params: dict[str, Any]) -> ToolResult:
        """Describe a node's capabilities"""
        node_id = params.get("node_id", "default")

        if node_id not in self._paired_nodes:
            return ToolResult(
                success=False,
                content="",
                error=f"Node '{node_id}' not found. Use action='list' to see available nodes.",
            )

        node_info = self._paired_nodes[node_id]

        output = f"Node '{node_id}':\n"
        output += f"  Platform: {node_info.get('platform', 'unknown')}\n"
        output += f"  Capabilities: {', '.join(node_info.get('capabilities', []))}\n"

        return ToolResult(success=True, content=output, metadata=node_info)

    async def _camera_snap(self, params: dict[str, Any]) -> ToolResult:
        """Take camera snapshot"""
        params.get("output_path", "snapshot.jpg")
        params.get("camera_id", "0")

        # This would require iOS/Android node integration
        logger.warning("camera_snap requires paired mobile device")

        return ToolResult(
            success=False,
            content="",
            error="Camera snap requires paired iOS/Android node. This feature needs native app integration.",
        )

    async def _camera_list(self, params: dict[str, Any]) -> ToolResult:
        """List available cameras"""
        logger.warning("camera_list requires paired mobile device")

        return ToolResult(
            success=False, content="", error="Camera list requires paired iOS/Android node"
        )

    async def _screen_record(self, params: dict[str, Any]) -> ToolResult:
        """Record screen"""
        params.get("duration", 10)
        params.get("output_path", "recording.mp4")

        logger.warning("screen_record requires paired mobile device")

        return ToolResult(
            success=False, content="", error="Screen recording requires paired iOS/Android node"
        )

    async def _location_get(self, params: dict[str, Any]) -> ToolResult:
        """Get device location"""
        logger.warning("location_get requires paired mobile device")

        return ToolResult(
            success=False, content="", error="Location requires paired iOS/Android node"
        )

    async def _notify(self, params: dict[str, Any]) -> ToolResult:
        """Send notification to device"""
        message = params.get("message", "")
        params.get("title", "ClawdBot")

        if not message:
            return ToolResult(success=False, content="", error="message required")

        logger.warning("notify requires paired mobile device")

        return ToolResult(
            success=False, content="", error="Notifications require paired iOS/Android node"
        )

    async def _run_command(self, params: dict[str, Any]) -> ToolResult:
        """Run system command on node"""
        command = params.get("command", "")

        if not command:
            return ToolResult(success=False, content="", error="command required")

        logger.warning("run command requires paired mobile device")

        return ToolResult(
            success=False, content="", error="System.run requires paired iOS/Android node"
        )


# Note: Nodes tool requires native iOS/Android apps for full functionality:
# - Camera control needs device camera access
# - Screen recording needs screen capture permission
# - Location needs GPS/location services
# - Notifications need push notification setup
# - System.run needs secure command execution framework
#
# These features are available in the TypeScript version's native apps
# but require substantial development effort to port to Python.
