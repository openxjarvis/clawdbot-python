"""Failover error types and helpers.

Aligned with TypeScript openclaw/src/agents/failover-error.ts and
src/agents/pi-embedded-helpers/errors.ts.
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Any


class FailoverReason(str, Enum):
    """Retryable failure categories — mirrors TS FailoverReason type."""

    AUTH = "auth"
    FORMAT = "format"
    RATE_LIMIT = "rate_limit"
    BILLING = "billing"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


class FailoverError(Exception):
    """Structured error that signals the fallback chain to try the next model.

    Mirrors TS FailoverError class (failover-error.ts).
    """

    name = "FailoverError"

    def __init__(
        self,
        message: str,
        *,
        reason: FailoverReason = FailoverReason.UNKNOWN,
        provider: str | None = None,
        model: str | None = None,
        profile_id: str | None = None,
        status: int | None = None,
        code: str | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.reason = reason
        self.provider = provider
        self.model = model
        self.profile_id = profile_id
        self.status = status
        self.code = code
        self.__cause__ = cause

    def to_dict(self) -> dict[str, Any]:
        return {
            "message": self.message,
            "reason": self.reason.value,
            "provider": self.provider,
            "model": self.model,
            "profile_id": self.profile_id,
            "status": self.status,
            "code": self.code,
        }


# ---------------------------------------------------------------------------
# Regex patterns (mirrors TS constants)
# ---------------------------------------------------------------------------

_TIMEOUT_HINT_RE = re.compile(
    r"timeout|timed out|deadline exceeded|context deadline exceeded"
    r"|stop reason:\s*abort|reason:\s*abort|unhandled stop reason:\s*abort",
    re.IGNORECASE,
)
_ABORT_TIMEOUT_RE = re.compile(
    r"request was aborted|request aborted",
    re.IGNORECASE,
)
_CONTEXT_WINDOW_TOO_SMALL_RE = re.compile(
    r"context window.*(too small|minimum is)",
    re.IGNORECASE,
)
_CONTEXT_OVERFLOW_HINT_RE = re.compile(
    r"context.*overflow"
    r"|context window.*(too (?:large|long)|exceed|over|limit|max(?:imum)?|requested|sent|tokens)"
    r"|prompt.*(too (?:large|long)|exceed|over|limit|max(?:imum)?)"
    r"|(?:request|input).*(?:context|window|length|token).*(too (?:large|long)|exceed|over|limit|max(?:imum)?)",
    re.IGNORECASE,
)
_RATE_LIMIT_HINT_RE = re.compile(
    r"rate limit|too many requests|requests per (?:minute|hour|day)|quota|throttl|429\b",
    re.IGNORECASE,
)
_CONTEXT_OVERFLOW_HEAD_RE = re.compile(
    r"^(?:context overflow:|request_too_large\b|request size exceeds\b"
    r"|request exceeds the maximum size\b|context length exceeded\b"
    r"|maximum context length\b|prompt is too long\b|exceeds model context window\b)",
    re.IGNORECASE,
)
_BILLING_RE = re.compile(
    r"^(?:error[:\s-]+)?billing(?:\s+error)?(?:[:\s-]+|$)"
    r"|^(?:error[:\s-]+)?(?:credit balance|insufficient credits?|payment required|http\s*402\b)",
    re.IGNORECASE,
)
_AUTH_ERROR_RE = re.compile(
    r"authentication|unauthorized|invalid api key|api key.*invalid|invalid.*api key"
    r"|credentials|permission denied|access denied|forbidden|401\b|403\b",
    re.IGNORECASE,
)
_RATE_LIMIT_ERROR_RE = re.compile(
    r"rate.?limit|too many requests|requests per (?:minute|hour|day)|quota.*exceeded|throttl|429\b",
    re.IGNORECASE,
)
_OVERLOADED_RE = re.compile(
    r"overloaded|model.*unavailable|capacity.*exceeded|service.*unavailable",
    re.IGNORECASE,
)
_TRANSIENT_HTTP_RE = re.compile(
    r"\b(?:500|502|503|521|522|523|524|529)\b",
)
_TIMEOUT_MSG_RE = re.compile(
    r"timeout|timed out|request timeout|deadline exceeded",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_status_code(err: Any) -> int | None:
    """Extract HTTP status code from error object."""
    if not err or not isinstance(err, (Exception, dict)):
        return None
    for attr in ("status", "status_code", "statusCode"):
        candidate = getattr(err, attr, None)
        if candidate is None and isinstance(err, dict):
            candidate = err.get(attr)
        if isinstance(candidate, int):
            return candidate
        if isinstance(candidate, str) and candidate.isdigit():
            return int(candidate)
    return None


def _get_error_code(err: Any) -> str | None:
    """Extract error code string from error object."""
    code = getattr(err, "code", None)
    if isinstance(code, str):
        trimmed = code.strip()
        return trimmed or None
    return None


def _get_error_message(err: Any) -> str:
    """Extract message string from any error-like value."""
    if isinstance(err, Exception):
        return str(err)
    if isinstance(err, str):
        return err
    if isinstance(err, dict):
        msg = err.get("message")
        if isinstance(msg, str):
            return msg
    return ""


def _has_timeout_hint(err: Any) -> bool:
    if not err:
        return False
    if type(err).__name__ == "TimeoutError":
        return True
    msg = _get_error_message(err)
    return bool(msg and _TIMEOUT_HINT_RE.search(msg))


# ---------------------------------------------------------------------------
# Public API — mirrors TS exports from failover-error.ts
# ---------------------------------------------------------------------------

def is_failover_error(err: Any) -> bool:
    """Return True if err is a FailoverError. Mirrors TS isFailoverError()."""
    return isinstance(err, FailoverError)


def is_timeout_error(err: Any) -> bool:
    """Return True if err represents a timeout. Mirrors TS isTimeoutError()."""
    if _has_timeout_hint(err):
        return True
    if not err or not isinstance(err, Exception):
        return False
    if type(err).__name__ != "AbortError":
        return False
    msg = _get_error_message(err)
    if msg and _ABORT_TIMEOUT_RE.search(msg):
        return True
    cause = getattr(err, "__cause__", None)
    reason = getattr(err, "reason", None)
    return _has_timeout_hint(cause) or _has_timeout_hint(reason)


def resolve_failover_status(reason: FailoverReason) -> int | None:
    """Map a FailoverReason to its canonical HTTP status. Mirrors TS resolveFailoverStatus()."""
    mapping = {
        FailoverReason.BILLING: 402,
        FailoverReason.RATE_LIMIT: 429,
        FailoverReason.AUTH: 401,
        FailoverReason.TIMEOUT: 408,
        FailoverReason.FORMAT: 400,
    }
    return mapping.get(reason)


def is_rate_limit_error_message(msg: str) -> bool:
    return bool(msg and _RATE_LIMIT_ERROR_RE.search(msg))


def is_auth_error_message(msg: str) -> bool:
    return bool(msg and _AUTH_ERROR_RE.search(msg))


def is_overloaded_error_message(msg: str) -> bool:
    return bool(msg and _OVERLOADED_RE.search(msg))


def is_transient_http_error(msg: str) -> bool:
    return bool(msg and _TRANSIENT_HTTP_RE.search(msg))


def is_timeout_error_message(msg: str) -> bool:
    return bool(msg and _TIMEOUT_MSG_RE.search(msg))


def is_billing_error_message(msg: str) -> bool:
    return bool(msg and _BILLING_RE.search(msg))


def is_likely_context_overflow_error(error_message: str | None) -> bool:
    """Return True if message looks like a context-window overflow.

    Mirrors TS isLikelyContextOverflowError() from pi-embedded-helpers/errors.ts.
    Excludes rate-limit messages that superficially match the overflow pattern.
    """
    if not error_message:
        return False
    if _CONTEXT_WINDOW_TOO_SMALL_RE.search(error_message):
        return False
    if is_rate_limit_error_message(error_message):
        return False
    if _CONTEXT_OVERFLOW_HEAD_RE.search(error_message):
        return True
    if _RATE_LIMIT_HINT_RE.search(error_message):
        return False
    return bool(_CONTEXT_OVERFLOW_HINT_RE.search(error_message))


def classify_failover_reason(raw: str) -> FailoverReason | None:
    """Classify a raw error string into a FailoverReason. Mirrors TS classifyFailoverReason()."""
    if is_transient_http_error(raw):
        return FailoverReason.TIMEOUT
    if is_rate_limit_error_message(raw):
        return FailoverReason.RATE_LIMIT
    if is_overloaded_error_message(raw):
        return FailoverReason.RATE_LIMIT
    if is_billing_error_message(raw):
        return FailoverReason.BILLING
    if is_timeout_error_message(raw):
        return FailoverReason.TIMEOUT
    if is_auth_error_message(raw):
        return FailoverReason.AUTH
    return None


def resolve_failover_reason_from_error(err: Any) -> FailoverReason | None:
    """Infer FailoverReason from any error object. Mirrors TS resolveFailoverReasonFromError()."""
    if is_failover_error(err):
        return err.reason

    status = _get_status_code(err)
    if status == 402:
        return FailoverReason.BILLING
    if status == 429:
        return FailoverReason.RATE_LIMIT
    if status in (401, 403):
        return FailoverReason.AUTH
    if status == 408:
        return FailoverReason.TIMEOUT
    if status in (502, 503, 504):
        return FailoverReason.TIMEOUT
    if status == 529:
        return FailoverReason.RATE_LIMIT
    if status == 400:
        return FailoverReason.FORMAT

    code = (_get_error_code(err) or "").upper()
    if code in ("ETIMEDOUT", "ESOCKETTIMEDOUT", "ECONNRESET", "ECONNABORTED"):
        return FailoverReason.TIMEOUT

    if is_timeout_error(err):
        return FailoverReason.TIMEOUT

    msg = _get_error_message(err)
    if not msg:
        return None
    return classify_failover_reason(msg)


def describe_failover_error(err: Any) -> dict[str, Any]:
    """Return a structured description of an error. Mirrors TS describeFailoverError()."""
    if is_failover_error(err):
        return {
            "message": err.message,
            "reason": err.reason,
            "status": err.status,
            "code": err.code,
        }
    message = _get_error_message(err) or str(err)
    return {
        "message": message,
        "reason": resolve_failover_reason_from_error(err),
        "status": _get_status_code(err),
        "code": _get_error_code(err),
    }


def coerce_to_failover_error(
    err: Any,
    context: dict[str, str | None] | None = None,
) -> FailoverError | None:
    """Convert any error into a FailoverError if it is retryable, else return None.

    Mirrors TS coerceToFailoverError().
    context keys: "provider", "model", "profile_id"
    """
    if is_failover_error(err):
        return err
    reason = resolve_failover_reason_from_error(err)
    if reason is None:
        return None

    ctx = context or {}
    message = _get_error_message(err) or str(err)
    status = _get_status_code(err) or resolve_failover_status(reason)
    code = _get_error_code(err)

    return FailoverError(
        message,
        reason=reason,
        provider=ctx.get("provider"),
        model=ctx.get("model"),
        profile_id=ctx.get("profile_id"),
        status=status,
        code=code,
        cause=err if isinstance(err, BaseException) else None,
    )


# Keep FallbackError as a backward-compat alias
FallbackError = FailoverError

__all__ = [
    "FailoverReason",
    "FailoverError",
    "FallbackError",
    "is_failover_error",
    "is_timeout_error",
    "is_likely_context_overflow_error",
    "coerce_to_failover_error",
    "describe_failover_error",
    "resolve_failover_reason_from_error",
    "classify_failover_reason",
    "resolve_failover_status",
    "is_rate_limit_error_message",
    "is_auth_error_message",
    "is_billing_error_message",
    "is_transient_http_error",
    "is_timeout_error_message",
    "is_overloaded_error_message",
]
