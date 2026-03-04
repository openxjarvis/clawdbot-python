"""ACP control-plane dispatch manager — mirrors src/acp/control-plane/"""
from .manager import get_acp_session_manager, AcpSessionManager

__all__ = ["get_acp_session_manager", "AcpSessionManager"]
