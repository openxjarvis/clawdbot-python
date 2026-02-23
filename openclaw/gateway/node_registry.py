"""
Node registry for managing connected nodes and their subscriptions.

Fully aligned with TypeScript openclaw/src/gateway/node-registry.ts.

Adds:
- NodeInvokeResult type
- invoke() with asyncio-based pending invoke tracking and timeout
- resolve_invoke_result() for matching node.invoke.result responses
- unregister cleanup of pending invokes on disconnect
"""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class NodeInvokeResult:
    """Result from a node.invoke call — mirrors TS NodeInvokeResult."""
    ok: bool
    payload: Any = None
    payload_json: str | None = None
    error: dict[str, str] | None = None


@dataclass
class NodeEntry:
    """Registered node information"""

    nodeId: str
    connId: str  # WebSocket connection ID
    deviceId: str
    capabilities: list[str] = field(default_factory=list)
    subscriptions: dict[str, list[str]] = field(default_factory=dict)  # event_type -> [subscription_ids]
    connected_at: float = field(default_factory=time.time)
    last_ping_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)
    # WebSocket send callable (injected on register): async fn(event, payload)
    _send_event: Any = field(default=None, repr=False, compare=False)


class NodeRegistry:
    """
    Registry of connected nodes with subscription management.
    
    This registry tracks:
    - Connected nodes and their metadata
    - Node capabilities
    - Event subscriptions for targeted delivery
    - Connection health (ping tracking)
    
    Usage:
        registry = NodeRegistry()
        
        # Register node
        registry.register_node(
            node_id="node_123",
            conn_id="conn_456",
            device_id="device_789",
            capabilities=["execute", "approve"]
        )
        
        # Subscribe to events
        registry.subscribe(
            node_id="node_123",
            event_type="exec.approval.requested",
            subscription_id="sub_001"
        )
        
        # Get subscribers for event
        subscribers = registry.get_subscribers("exec.approval.requested")
        
        # Update ping
        registry.update_ping("node_123")
        
        # Unregister on disconnect
        registry.unregister_node("node_123")
    """
    
    def __init__(self):
        """Initialize node registry"""
        self._nodes: dict[str, NodeEntry] = {}  # nodeId -> NodeEntry
        self._conn_to_node: dict[str, str] = {}  # connId -> nodeId
        self._device_to_nodes: dict[str, set[str]] = {}  # deviceId -> {nodeIds}
        # Pending invokes: invocationId -> (future, nodeId, command, timer_handle)
        self._pending_invokes: dict[str, tuple[asyncio.Future[NodeInvokeResult], str, str, asyncio.TimerHandle | None]] = {}
    
    def register_node(
        self,
        node_id: str,
        conn_id: str,
        device_id: str,
        capabilities: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        send_event: Any = None,
    ) -> NodeEntry:
        """
        Register connected node.
        
        Args:
            node_id: Unique node ID
            conn_id: WebSocket connection ID
            device_id: Device ID
            capabilities: Node capabilities
            metadata: Additional metadata
            
        Returns:
            Registered node entry
        """
        node = NodeEntry(
            nodeId=node_id,
            connId=conn_id,
            deviceId=device_id,
            capabilities=capabilities or [],
            subscriptions={},
            connected_at=time.time(),
            last_ping_at=time.time(),
            metadata=metadata or {},
            _send_event=send_event,
        )
        
        self._nodes[node_id] = node
        self._conn_to_node[conn_id] = node_id
        
        # Track device -> nodes mapping
        if device_id not in self._device_to_nodes:
            self._device_to_nodes[device_id] = set()
        self._device_to_nodes[device_id].add(node_id)
        
        return node
    
    def unregister_node(self, node_id: str) -> NodeEntry | None:
        """Unregister node on disconnect, cancelling any pending invokes."""
        node = self._nodes.pop(node_id, None)
        if node:
            self._conn_to_node.pop(node.connId, None)
            device_nodes = self._device_to_nodes.get(node.deviceId)
            if device_nodes:
                device_nodes.discard(node_id)
                if not device_nodes:
                    del self._device_to_nodes[node.deviceId]

            # Cancel pending invokes for this node — mirrors TS unregister()
            to_cancel = [
                inv_id for inv_id, (_, nid, _, _) in self._pending_invokes.items()
                if nid == node_id
            ]
            for inv_id in to_cancel:
                fut, _, cmd, timer = self._pending_invokes.pop(inv_id)
                if timer is not None:
                    timer.cancel()
                if not fut.done():
                    fut.set_result(NodeInvokeResult(
                        ok=False,
                        error={"code": "DISCONNECTED", "message": f"node disconnected ({cmd})"},
                    ))

        return node

    async def invoke(
        self,
        *,
        node_id: str,
        command: str,
        params: Any = None,
        timeout_ms: int = 30_000,
        idempotency_key: str | None = None,
    ) -> NodeInvokeResult:
        """Send a command invocation to a connected node and await the result.

        Mirrors TS NodeRegistry.invoke().
        Returns NodeInvokeResult immediately if the node is not connected.
        Times out with TIMEOUT error if the node doesn't respond.
        """
        node = self._nodes.get(node_id)
        if node is None:
            return NodeInvokeResult(
                ok=False,
                error={"code": "NOT_CONNECTED", "message": "node not connected"},
            )

        import json
        invocation_id = str(uuid.uuid4())
        payload = {
            "id": invocation_id,
            "nodeId": node_id,
            "command": command,
            "paramsJSON": json.dumps(params) if params is not None else None,
            "timeoutMs": timeout_ms,
            "idempotencyKey": idempotency_key,
        }

        # Send to node
        send = node._send_event
        if send is None:
            return NodeInvokeResult(
                ok=False,
                error={"code": "UNAVAILABLE", "message": "node has no send_event callback"},
            )
        try:
            await send("node.invoke.request", payload)
        except Exception as exc:
            return NodeInvokeResult(
                ok=False,
                error={"code": "UNAVAILABLE", "message": f"failed to send invoke: {exc}"},
            )

        loop = asyncio.get_event_loop()
        future: asyncio.Future[NodeInvokeResult] = loop.create_future()

        def _on_timeout() -> None:
            if invocation_id in self._pending_invokes:
                del self._pending_invokes[invocation_id]
            if not future.done():
                future.set_result(NodeInvokeResult(
                    ok=False,
                    error={"code": "TIMEOUT", "message": "node invoke timed out"},
                ))

        timer = loop.call_later(timeout_ms / 1000.0, _on_timeout)
        self._pending_invokes[invocation_id] = (future, node_id, command, timer)
        return await future

    def resolve_invoke_result(
        self,
        *,
        invocation_id: str,
        node_id: str,
        ok: bool,
        payload: Any = None,
        payload_json: str | None = None,
        error: dict[str, str] | None = None,
    ) -> bool:
        """Resolve a pending invoke with the result from node.invoke.result.

        Returns True if a matching pending invoke was found and resolved,
        False if the invocation was not found (e.g. timed out).

        Mirrors TS NodeRegistry.handleInvokeResult().
        """
        entry = self._pending_invokes.get(invocation_id)
        if entry is None:
            return False
        future, pending_node_id, _, timer = entry
        if pending_node_id != node_id:
            return False
        if timer is not None:
            timer.cancel()
        del self._pending_invokes[invocation_id]
        if not future.done():
            future.set_result(NodeInvokeResult(
                ok=ok,
                payload=payload,
                payload_json=payload_json,
                error=error,
            ))
        return True
    
    def get_node(self, node_id: str) -> NodeEntry | None:
        """
        Get node by ID.
        
        Args:
            node_id: Node ID
            
        Returns:
            Node entry if found, None otherwise
        """
        return self._nodes.get(node_id)
    
    def get_node_by_conn(self, conn_id: str) -> NodeEntry | None:
        """
        Get node by connection ID.
        
        Args:
            conn_id: Connection ID
            
        Returns:
            Node entry if found, None otherwise
        """
        node_id = self._conn_to_node.get(conn_id)
        return self._nodes.get(node_id) if node_id else None
    
    def get_nodes_by_device(self, device_id: str) -> list[NodeEntry]:
        """
        Get all nodes for a device.
        
        Args:
            device_id: Device ID
            
        Returns:
            List of node entries for device
        """
        node_ids = self._device_to_nodes.get(device_id, set())
        return [self._nodes[node_id] for node_id in node_ids if node_id in self._nodes]
    
    def subscribe(
        self, 
        node_id: str, 
        event_type: str, 
        subscription_id: str
    ) -> bool:
        """
        Subscribe node to event type.
        
        Args:
            node_id: Node ID
            event_type: Event type to subscribe to
            subscription_id: Unique subscription ID
            
        Returns:
            True if subscribed successfully, False if node not found
        """
        node = self._nodes.get(node_id)
        if not node:
            return False
        
        if event_type not in node.subscriptions:
            node.subscriptions[event_type] = []
        
        if subscription_id not in node.subscriptions[event_type]:
            node.subscriptions[event_type].append(subscription_id)
        
        return True
    
    def unsubscribe(
        self, 
        node_id: str, 
        event_type: str, 
        subscription_id: str | None = None
    ) -> bool:
        """
        Unsubscribe node from event type.
        
        Args:
            node_id: Node ID
            event_type: Event type to unsubscribe from
            subscription_id: Specific subscription ID, or None to remove all
            
        Returns:
            True if unsubscribed, False if node not found
        """
        node = self._nodes.get(node_id)
        if not node:
            return False
        
        if event_type not in node.subscriptions:
            return False
        
        if subscription_id:
            # Remove specific subscription
            try:
                node.subscriptions[event_type].remove(subscription_id)
            except ValueError:
                pass
            
            # Remove event type if no more subscriptions
            if not node.subscriptions[event_type]:
                del node.subscriptions[event_type]
        else:
            # Remove all subscriptions for event type
            del node.subscriptions[event_type]
        
        return True
    
    def get_subscribers(self, event_type: str) -> list[NodeEntry]:
        """
        Get nodes subscribed to event type.
        
        Args:
            event_type: Event type
            
        Returns:
            List of subscribed node entries
        """
        return [
            node for node in self._nodes.values()
            if event_type in node.subscriptions
        ]
    
    def update_ping(self, node_id: str) -> bool:
        """
        Update last ping time for node.
        
        Args:
            node_id: Node ID
            
        Returns:
            True if updated, False if node not found
        """
        node = self._nodes.get(node_id)
        if node:
            node.last_ping_at = time.time()
            return True
        return False
    
    def list_nodes(self) -> list[NodeEntry]:
        """
        List all registered nodes.
        
        Returns:
            List of all node entries
        """
        return list(self._nodes.values())
    
    def list_nodes_by_capability(self, capability: str) -> list[NodeEntry]:
        """
        List nodes with specific capability.
        
        Args:
            capability: Capability to filter by
            
        Returns:
            List of nodes with capability
        """
        return [
            node for node in self._nodes.values()
            if capability in node.capabilities
        ]
    
    def count(self) -> int:
        """Get number of registered nodes"""
        return len(self._nodes)
    
    def clear(self) -> None:
        """Clear all nodes (for testing/reset)"""
        self._nodes.clear()
        self._conn_to_node.clear()
        self._device_to_nodes.clear()


__all__ = [
    "NodeEntry",
    "NodeInvokeResult",
    "NodeRegistry",
]
