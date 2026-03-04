"""ACP session manager singleton facade — mirrors src/acp/control-plane/manager.ts

Provides getAcpSessionManager() which returns the process-wide singleton instance.
"""
from __future__ import annotations

from .manager_core import AcpSessionManager

_instance: AcpSessionManager | None = None


def get_acp_session_manager() -> AcpSessionManager:
    """Return the process-wide AcpSessionManager singleton."""
    global _instance
    if _instance is None:
        _instance = AcpSessionManager()
    return _instance


def _reset_acp_session_manager_for_tests() -> None:
    """Reset the singleton — for use in tests only."""
    global _instance
    _instance = None
