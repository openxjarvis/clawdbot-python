"""Human-readable ACP runtime error text — mirrors src/acp/runtime/error-text.ts"""
from __future__ import annotations

from .errors import AcpRuntimeError, AcpRuntimeErrorCode, to_acp_runtime_error


def _resolve_acp_runtime_error_next_step(error: AcpRuntimeError) -> str | None:
    code = error.code
    if code in ("ACP_BACKEND_MISSING", "ACP_BACKEND_UNAVAILABLE"):
        return "Run `/acp doctor`, install/enable the backend plugin, then retry."
    if code == "ACP_DISPATCH_DISABLED":
        return "Enable `acp.dispatch.enabled=true` to allow thread-message ACP turns."
    if code == "ACP_SESSION_INIT_FAILED":
        return "If this session is stale, recreate it with `/acp spawn` and rebind the thread."
    if code == "ACP_INVALID_RUNTIME_OPTION":
        return "Use `/acp status` to inspect options and pass valid values."
    if code == "ACP_BACKEND_UNSUPPORTED_CONTROL":
        return "This backend does not support that control; use a supported command."
    if code == "ACP_TURN_FAILED":
        return "Retry, or use `/acp cancel` and send the message again."
    return None


def format_acp_runtime_error_text(error: AcpRuntimeError) -> str:
    next_step = _resolve_acp_runtime_error_next_step(error)
    base = f"ACP error ({error.code}): {error}"
    if not next_step:
        return base
    return f"{base}\nnext: {next_step}"


def to_acp_runtime_error_text(
    error: object,
    *,
    fallback_code: AcpRuntimeErrorCode,
    fallback_message: str,
) -> str:
    return format_acp_runtime_error_text(
        to_acp_runtime_error(
            error,
            fallback_code=fallback_code,
            fallback_message=fallback_message,
        )
    )
