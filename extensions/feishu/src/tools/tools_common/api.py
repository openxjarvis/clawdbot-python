"""Feishu API call helpers.

Mirrors: clawdbot-feishu/src/tools-common/feishu-api.ts
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Iterable

logger = logging.getLogger(__name__)

# Error codes that indicate a transient failure worth retrying
_DEFAULT_RETRYABLE_CODES: frozenset[int] = frozenset([429, 1254290, 1254291, 1255040])
_DEFAULT_BACKOFF_MS: list[int] = [350, 900, 1800]


def json_result(data: Any) -> dict[str, Any]:
    """Wrap data in the standard tool output format."""
    return {
        "content": [{"type": "text", "text": json.dumps(data, indent=2, ensure_ascii=False)}],
        "details": data,
    }


def error_result(err: Exception | str) -> dict[str, Any]:
    """Wrap an error message in the standard tool output format."""
    msg = str(err)
    logger.debug("Feishu tool error: %s", msg)
    return json_result({"error": msg})


def feishu_ok(response: Any) -> bool:
    """Return True if the lark_oapi response indicates success."""
    return bool(getattr(response, "success", lambda: False)())


def _extract_feishu_error(err: Any) -> tuple[int | None, str]:
    """Extract (code, message) from a lark_oapi error or exception."""
    if isinstance(err, (list, tuple)) and len(err) >= 2:
        inner = err[1]
        code = getattr(inner, "code", None) or (inner.get("code") if isinstance(inner, dict) else None)
        msg = getattr(inner, "msg", None) or (inner.get("msg") if isinstance(inner, dict) else None) or str(inner)
        return code, str(msg)
    code = getattr(err, "code", None)
    msg = getattr(err, "msg", None) or getattr(err, "message", None) or str(err)
    return code, str(msg)


async def run_feishu_api_call(
    context: str,
    fn: Callable,
    retryable_codes: Iterable[int] | None = None,
    backoff_ms: list[int] | None = None,
) -> Any:
    """Execute a sync lark_oapi SDK call in a thread with retry on transient errors.

    Args:
        context: Human-readable name for error messages (e.g. "docx.document.get").
        fn: Zero-argument callable that performs the synchronous SDK call.
        retryable_codes: Error codes that trigger a retry. Defaults to common transient codes.
        backoff_ms: Delay between retries in milliseconds. Length determines max additional attempts.
    """
    codes = frozenset(retryable_codes) if retryable_codes is not None else _DEFAULT_RETRYABLE_CODES
    delays = backoff_ms if backoff_ms is not None else _DEFAULT_BACKOFF_MS
    max_attempts = len(delays) + 1
    loop = asyncio.get_running_loop()

    last_err: Exception | None = None
    for attempt in range(max_attempts):
        try:
            response = await loop.run_in_executor(None, fn)
            if not feishu_ok(response):
                code = getattr(response, "code", None)
                msg = getattr(response, "msg", "") or ""
                log_id = getattr(response, "request_id", None) or getattr(response, "x_tt_logid", None)
                detail = f"{context} failed: {msg}, code={code}" + (f", log_id={log_id}" if log_id else "")
                if code in codes and attempt < max_attempts - 1:
                    logger.debug("Retryable Feishu error (attempt %d/%d): %s", attempt + 1, max_attempts, detail)
                    await asyncio.sleep(delays[attempt] / 1000)
                    continue
                raise RuntimeError(detail)
            return response
        except RuntimeError:
            raise
        except Exception as e:
            code, _ = _extract_feishu_error(e)
            if code in codes and attempt < max_attempts - 1:
                logger.debug("Retryable Feishu exception (attempt %d/%d): %s", attempt + 1, max_attempts, e)
                await asyncio.sleep(delays[attempt] / 1000)
                last_err = e
                continue
            raise RuntimeError(f"{context} failed: {e}") from e

    raise RuntimeError(f"{context} failed after {max_attempts} attempts") from last_err
