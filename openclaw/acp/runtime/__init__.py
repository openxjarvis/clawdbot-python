"""ACP runtime backend plugin system — mirrors src/acp/runtime/"""
from .errors import AcpRuntimeError, ACP_ERROR_CODES, is_acp_runtime_error
from .types import AcpRuntime, AcpRuntimeHandle, AcpRuntimeEvent
from .registry import (
    register_acp_runtime_backend,
    unregister_acp_runtime_backend,
    get_acp_runtime_backend,
    require_acp_runtime_backend,
    AcpRuntimeBackend,
)

__all__ = [
    "AcpRuntimeError",
    "ACP_ERROR_CODES",
    "is_acp_runtime_error",
    "AcpRuntime",
    "AcpRuntimeHandle",
    "AcpRuntimeEvent",
    "AcpRuntimeBackend",
    "register_acp_runtime_backend",
    "unregister_acp_runtime_backend",
    "get_acp_runtime_backend",
    "require_acp_runtime_backend",
]
