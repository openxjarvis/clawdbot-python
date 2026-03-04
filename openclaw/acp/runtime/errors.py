"""ACP runtime error types — mirrors src/acp/runtime/errors.ts"""
from __future__ import annotations

from typing import Any

ACP_ERROR_CODES = (
    "ACP_BACKEND_MISSING",
    "ACP_BACKEND_UNAVAILABLE",
    "ACP_BACKEND_UNSUPPORTED_CONTROL",
    "ACP_DISPATCH_DISABLED",
    "ACP_INVALID_RUNTIME_OPTION",
    "ACP_SESSION_INIT_FAILED",
    "ACP_TURN_FAILED",
)

AcpRuntimeErrorCode = str  # literal union of ACP_ERROR_CODES values


class AcpRuntimeError(Exception):
    """Typed ACP runtime error with a machine-readable code."""

    def __init__(
        self,
        code: AcpRuntimeErrorCode,
        message: str,
        *,
        cause: Any = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.cause = cause

    def __repr__(self) -> str:
        return f"AcpRuntimeError(code={self.code!r}, message={str(self)!r})"


def is_acp_runtime_error(value: Any) -> bool:
    return isinstance(value, AcpRuntimeError)


def to_acp_runtime_error(
    error: Any,
    *,
    fallback_code: AcpRuntimeErrorCode,
    fallback_message: str,
) -> AcpRuntimeError:
    if isinstance(error, AcpRuntimeError):
        return error
    if isinstance(error, Exception):
        return AcpRuntimeError(fallback_code, str(error), cause=error)
    return AcpRuntimeError(fallback_code, fallback_message, cause=error)


async def with_acp_runtime_error_boundary(
    run: Any,
    *,
    fallback_code: AcpRuntimeErrorCode,
    fallback_message: str,
) -> Any:
    """
    Wrap an awaitable coroutine in an AcpRuntimeError boundary.

    Any exception raised is converted to an AcpRuntimeError with the given
    fallback code and message if not already an AcpRuntimeError.
    """
    try:
        return await run()
    except Exception as exc:
        raise to_acp_runtime_error(
            exc,
            fallback_code=fallback_code,
            fallback_message=fallback_message,
        ) from exc
