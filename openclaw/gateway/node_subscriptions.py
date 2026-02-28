"""Node Subscription Manager.

Python equivalent of TypeScript src/gateway/server-node-subscriptions.ts.

Manages bidirectional mapping between node connections and session subscriptions,
enabling targeted event delivery to nodes watching specific sessions.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


class NodeSubscriptionManager:
    """
    Manages node-to-session subscriptions for targeted event delivery.

    Mirrors TypeScript NodeSubscriptionManager from server-node-subscriptions.ts.

    Architecture:
        - node_subscriptions: nodeId → Set[sessionKey]
        - session_subscribers: sessionKey → Set[nodeId]

    Usage:
        manager = NodeSubscriptionManager(get_node_send_fn)

        # Node subscribes to watch a session
        manager.subscribe("node_123", "session_abc")

        # Send event to all nodes watching a session
        await manager.send_to_session("session_abc", "agent.update", {"text": "..."})

        # Node disconnects — clean up all its subscriptions
        manager.unsubscribe_all("node_123")
    """

    def __init__(
        self,
        get_node_send_fn: Callable[[str], Callable | None] | None = None,
    ) -> None:
        """
        Args:
            get_node_send_fn: Optional callable that returns a per-node send function
                              given a node_id. The send function signature should be:
                              async (event: str, payload: dict) -> None
        """
        # nodeId → set of session keys the node is subscribed to
        self._node_subscriptions: dict[str, set[str]] = {}
        # sessionKey → set of node IDs subscribed to that session
        self._session_subscribers: dict[str, set[str]] = {}
        # lookup for node send functions
        self._get_node_send_fn = get_node_send_fn

    # =========================================================================
    # Subscription management
    # =========================================================================

    def subscribe(self, node_id: str, session_key: str) -> None:
        """Subscribe a node to a session's events.

        Args:
            node_id: The node identifier
            session_key: The session key to subscribe to
        """
        # nodeId → sessions
        if node_id not in self._node_subscriptions:
            self._node_subscriptions[node_id] = set()
        self._node_subscriptions[node_id].add(session_key)

        # sessionKey → nodes
        if session_key not in self._session_subscribers:
            self._session_subscribers[session_key] = set()
        self._session_subscribers[session_key].add(node_id)

        logger.debug(f"Node {node_id!r} subscribed to session {session_key!r}")

    def unsubscribe(self, node_id: str, session_key: str) -> None:
        """Unsubscribe a node from a specific session.

        Args:
            node_id: The node identifier
            session_key: The session key to unsubscribe from
        """
        if node_id in self._node_subscriptions:
            self._node_subscriptions[node_id].discard(session_key)
            if not self._node_subscriptions[node_id]:
                del self._node_subscriptions[node_id]

        if session_key in self._session_subscribers:
            self._session_subscribers[session_key].discard(node_id)
            if not self._session_subscribers[session_key]:
                del self._session_subscribers[session_key]

        logger.debug(f"Node {node_id!r} unsubscribed from session {session_key!r}")

    def unsubscribe_all(self, node_id: str) -> None:
        """Unsubscribe a node from all sessions (called on disconnect).

        Args:
            node_id: The node identifier to fully unsubscribe
        """
        sessions = self._node_subscriptions.pop(node_id, set())
        for session_key in sessions:
            if session_key in self._session_subscribers:
                self._session_subscribers[session_key].discard(node_id)
                if not self._session_subscribers[session_key]:
                    del self._session_subscribers[session_key]

        if sessions:
            logger.debug(f"Node {node_id!r} unsubscribed from all sessions ({len(sessions)} sessions)")

    # =========================================================================
    # Query
    # =========================================================================

    def get_subscribed_sessions(self, node_id: str) -> set[str]:
        """Get all session keys a node is subscribed to."""
        return set(self._node_subscriptions.get(node_id, set()))

    def get_session_subscribers(self, session_key: str) -> set[str]:
        """Get all node IDs subscribed to a session."""
        return set(self._session_subscribers.get(session_key, set()))

    def is_subscribed(self, node_id: str, session_key: str) -> bool:
        """Check if a node is subscribed to a session."""
        return session_key in self._node_subscriptions.get(node_id, set())

    # =========================================================================
    # Event delivery
    # =========================================================================

    async def send_to_session(
        self,
        session_key: str,
        event: str,
        payload: dict[str, Any],
    ) -> None:
        """Send an event to all nodes subscribed to a session.

        Args:
            session_key: Target session key
            event: Event name/type
            payload: Event payload dict
        """
        subscribers = self._session_subscribers.get(session_key, set())
        if not subscribers:
            return

        for node_id in list(subscribers):
            await self._send_to_node(node_id, event, payload)

    async def send_to_all_subscribed(
        self,
        event: str,
        payload: dict[str, Any],
    ) -> None:
        """Broadcast an event to all nodes that have any subscription.

        Args:
            event: Event name/type
            payload: Event payload dict
        """
        subscribed_nodes = set(self._node_subscriptions.keys())
        for node_id in subscribed_nodes:
            await self._send_to_node(node_id, event, payload)

    async def send_to_all_connected(
        self,
        event: str,
        payload: dict[str, Any],
        connected_node_ids: list[str] | None = None,
    ) -> None:
        """Broadcast an event to all connected nodes.

        Args:
            event: Event name/type
            payload: Event payload dict
            connected_node_ids: Optional explicit list of connected node IDs.
                                If None, falls back to all subscribed nodes.
        """
        target_nodes = connected_node_ids or list(self._node_subscriptions.keys())
        for node_id in target_nodes:
            await self._send_to_node(node_id, event, payload)

    async def _send_to_node(
        self,
        node_id: str,
        event: str,
        payload: dict[str, Any],
    ) -> None:
        """Send an event to a specific node."""
        if self._get_node_send_fn is None:
            logger.debug(f"No send function configured; dropping event {event!r} for node {node_id!r}")
            return

        send_fn = self._get_node_send_fn(node_id)
        if send_fn is None:
            logger.debug(f"No send function for node {node_id!r}; dropping event {event!r}")
            return

        try:
            result = send_fn(event, payload)
            if hasattr(result, "__await__"):
                await result
        except Exception as exc:
            logger.warning(f"Failed to send event {event!r} to node {node_id!r}: {exc}")

    # =========================================================================
    # Diagnostics
    # =========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Return subscription stats for diagnostics."""
        return {
            "subscribed_nodes": len(self._node_subscriptions),
            "tracked_sessions": len(self._session_subscribers),
            "total_subscriptions": sum(
                len(sessions) for sessions in self._node_subscriptions.values()
            ),
        }


__all__ = ["NodeSubscriptionManager"]
