"""
Node management service

Manages distributed node registration, pairing, and command invocation.
"""

import logging
import secrets
import time
from typing import Any, Dict, Optional, List
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class NodeInfo:
    """Node information"""
    id: str
    capabilities: Dict[str, Any] = field(default_factory=dict)
    registered_at: float = field(default_factory=time.time)
    status: str = "active"  # active | inactive | error
    public_key: Optional[str] = None
    last_seen: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PairRequest:
    """Node pairing request"""
    request_id: str
    node_id: str
    nonce: str = ""
    signature: str = ""
    display_name: Optional[str] = None
    platform: Optional[str] = None
    version: Optional[str] = None
    caps: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    requested_at: float = field(default_factory=time.time)
    status: str = "pending"  # pending | approved | rejected
    token: Optional[str] = None


class NodeManager:
    """
    Node management service
    
    Handles:
    - Node registration
    - Node pairing/authentication
    - Command invocation
    - Node status tracking
    """
    
    def __init__(self):
        """Initialize node manager"""
        self.nodes: Dict[str, NodeInfo] = {}
        self.pending_pairs: Dict[str, PairRequest] = {}
        self.tokens: Dict[str, str] = {}  # token -> node_id mapping
        self.pending_invocations: Dict[str, Dict[str, Any]] = {}
    
    def register_node(
        self,
        node_id: str,
        capabilities: Dict[str, Any],
        public_key: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> NodeInfo:
        """
        Register a node
        
        Args:
            node_id: Node identifier
            capabilities: Node capabilities
            public_key: Node public key for authentication
            metadata: Additional metadata
            
        Returns:
            NodeInfo
        """
        node = NodeInfo(
            id=node_id,
            capabilities=capabilities,
            public_key=public_key,
            metadata=metadata or {}
        )
        
        self.nodes[node_id] = node
        logger.info(f"Registered node: {node_id}")
        
        return node
    
    def request_pairing(
        self,
        node_id: str,
        nonce: str = "",
        signature: str = "",
        *,
        request_id: str | None = None,
        display_name: str | None = None,
        platform: str | None = None,
        version: str | None = None,
        caps: list[str] | None = None,
        commands: list[str] | None = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PairRequest:
        """
        Request node pairing
        
        Args:
            node_id: Node identifier
            nonce: Nonce for replay protection
            signature: Signature of nonce
            
        Returns:
            PairRequest
        """
        request = PairRequest(
            request_id=request_id or secrets.token_urlsafe(12),
            node_id=node_id,
            nonce=nonce,
            signature=signature,
            display_name=display_name,
            platform=platform,
            version=version,
            caps=caps or [],
            commands=commands or [],
            metadata=metadata or {},
        )
        self.pending_pairs[request.request_id] = request
        logger.info(f"Node pairing requested: {node_id}")
        
        # TODO: Broadcast node.pair.requested event
        
        return request
    
    def approve_pairing(self, request_or_node_id: str) -> Optional[str]:
        """
        Approve node pairing
        
        Args:
            node_id: Node identifier
            
        Returns:
            Access token or None if request not found
        """
        request = self.pending_pairs.get(request_or_node_id)
        if request is None:
            request = next((r for r in self.pending_pairs.values() if r.node_id == request_or_node_id), None)
        if not request:
            logger.warning(f"No pending pair request for node/request: {request_or_node_id}")
            return None
        
        # Generate token
        token = secrets.token_urlsafe(32)
        request.status = "approved"
        request.token = token
        
        # Store token mapping
        self.tokens[token] = request.node_id
        
        # Remove from pending
        self.pending_pairs.pop(request.request_id, None)
        
        logger.info(f"Node pairing approved: {request.node_id}")
        
        # TODO: Broadcast node.pair.resolved event
        
        return token
    
    def reject_pairing(self, request_or_node_id: str, reason: Optional[str] = None):
        """
        Reject node pairing
        
        Args:
            node_id: Node identifier
            reason: Rejection reason
        """
        request = self.pending_pairs.get(request_or_node_id)
        if request is None:
            request = next((r for r in self.pending_pairs.values() if r.node_id == request_or_node_id), None)
        if not request:
            logger.warning(f"No pending pair request for node/request: {request_or_node_id}")
            return
        
        request.status = "rejected"
        
        # Remove from pending
        self.pending_pairs.pop(request.request_id, None)
        
        logger.info(f"Node pairing rejected: {request.node_id}, reason: {reason}")
        
        # TODO: Broadcast node.pair.rejected event
    
    def list_nodes(self) -> List[Dict[str, Any]]:
        """
        List all nodes
        
        Returns:
            List of node info dictionaries
        """
        nodes = []
        for node in self.nodes.values():
            nodes.append({
                "id": node.id,
                "capabilities": node.capabilities,
                "status": node.status,
                "registeredAt": node.registered_at,
                "lastSeen": node.last_seen,
                "metadata": node.metadata
            })
        return nodes
    
    def list_pending_pairs(self) -> List[Dict[str, Any]]:
        """
        List pending pairing requests
        
        Returns:
            List of pending pair requests
        """
        pairs = []
        for request in self.pending_pairs.values():
            pairs.append({
                "requestId": request.request_id,
                "nodeId": request.node_id,
                "displayName": request.display_name,
                "platform": request.platform,
                "version": request.version,
                "caps": request.caps,
                "commands": request.commands,
                "requestedAt": request.requested_at,
                "status": request.status,
            })
        return pairs

    def list_paired_nodes(self) -> List[Dict[str, Any]]:
        """List paired nodes inferred from issued tokens."""
        rows: list[dict[str, Any]] = []
        for token, node_id in self.tokens.items():
            node = self.nodes.get(node_id)
            metadata = node.metadata if node and isinstance(node.metadata, dict) else {}
            capabilities = node.capabilities if node and isinstance(node.capabilities, dict) else {}
            rows.append(
                {
                    "nodeId": node_id,
                    "status": "paired",
                    "token": token,
                    "displayName": metadata.get("displayName"),
                    "platform": metadata.get("platform"),
                    "version": metadata.get("version"),
                    "coreVersion": metadata.get("coreVersion"),
                    "uiVersion": metadata.get("uiVersion"),
                    "deviceFamily": metadata.get("deviceFamily"),
                    "modelIdentifier": metadata.get("modelIdentifier"),
                    "remoteIp": metadata.get("remoteIp"),
                    "caps": capabilities.get("types", []),
                    "commands": metadata.get("commands", []),
                    "permissions": metadata.get("permissions"),
                    "pathEnv": metadata.get("pathEnv"),
                }
            )
        return rows
    
    def get_node(self, node_id: str) -> Optional[NodeInfo]:
        """
        Get node by ID
        
        Args:
            node_id: Node identifier
            
        Returns:
            NodeInfo or None
        """
        return self.nodes.get(node_id)
    
    def verify_token(self, token: str) -> Optional[str]:
        """
        Verify node token
        
        Args:
            token: Access token
            
        Returns:
            Node ID or None if invalid
        """
        return self.tokens.get(token)

    def verify_pairing(self, token: str) -> dict[str, Any]:
        node_id = self.verify_token(token)
        return {"ok": bool(node_id), "nodeId": node_id}

    def rename_node(self, node_id: str, name: str) -> bool:
        node = self.nodes.get(node_id)
        if not node:
            return False
        node.metadata = {**(node.metadata or {}), "displayName": name}
        return True
    
    async def invoke_node(
        self,
        node_id: str,
        command: str,
        params: Optional[Dict[str, Any]] = None,
        *,
        timeout_ms: int | None = None,
        idempotency_key: str | None = None,
    ) -> Dict[str, Any]:
        """
        Invoke command on a node
        
        Args:
            node_id: Node identifier
            command: Command to execute
            params: Command parameters
            
        Returns:
            Command result
        """
        node = self.nodes.get(node_id)
        if not node:
            raise ValueError(f"Node not found: {node_id}")
        
        if node.status != "active":
            raise ValueError(f"Node is not active: {node_id}")
        
        allowed_commands = node.metadata.get("commands") if isinstance(node.metadata, dict) else None
        if isinstance(allowed_commands, list) and allowed_commands and command not in allowed_commands:
            raise ValueError(f"Node command not allowed: {command}")

        logger.info(f"Invoking command on node {node_id}: {command}")
        invocation_id = idempotency_key or secrets.token_urlsafe(16)
        payload = {
            "nodeId": node_id,
            "command": command,
            "params": params or {},
            "timeoutMs": timeout_ms,
            "ts": int(time.time() * 1000),
            "status": "queued",
            "invocationId": invocation_id,
        }
        self.pending_invocations[invocation_id] = payload
        return {
            **payload
        }

    def resolve_invoke_result(self, invocation_id: str | None, result: Any) -> Dict[str, Any] | None:
        """Resolve a previously queued invocation result."""
        if not invocation_id:
            return None
        inv = self.pending_invocations.get(invocation_id)
        if inv is None:
            return None
        inv["status"] = "completed"
        inv["result"] = result
        inv["completedAt"] = int(time.time() * 1000)
        return inv


# Global node manager instance
_node_manager: Optional[NodeManager] = None


def get_node_manager() -> NodeManager:
    """Get global node manager instance"""
    global _node_manager
    if _node_manager is None:
        _node_manager = NodeManager()
    return _node_manager


def set_node_manager(manager: NodeManager):
    """Set global node manager instance"""
    global _node_manager
    _node_manager = manager
