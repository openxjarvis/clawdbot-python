"""Telegram network enhancements

Handles proxy configuration, retry logic, error classification, and timeout settings.
"""
from __future__ import annotations

import logging
import os
import random
from typing import Any

logger = logging.getLogger(__name__)


def resolve_telegram_proxy(config: dict[str, Any]) -> str | None:
    """
    Resolve proxy configuration for Telegram.
    
    Supports SOCKS5 and HTTP proxies.
    
    Args:
        config: Telegram channel config
    
    Returns:
        Proxy URL or None
    """
    proxy = config.get("proxy")
    if proxy and isinstance(proxy, str):
        proxy = proxy.strip()
        if proxy:
            return proxy
    
    return None


def resolve_telegram_retry_config(config: dict[str, Any]) -> dict[str, Any]:
    """
    Resolve retry configuration for Telegram.
    
    Args:
        config: Telegram channel config
    
    Returns:
        Retry configuration dict with attempts, min_delay_ms, max_delay_ms, jitter
    """
    retry_config = config.get("retry", {})
    
    return {
        "attempts": retry_config.get("attempts", 3),
        "min_delay_ms": retry_config.get("minDelayMs", 1000),
        "max_delay_ms": retry_config.get("maxDelayMs", 30000),
        "jitter": retry_config.get("jitter", True),
    }


def calculate_retry_delay(
    attempt: int,
    min_delay_ms: int,
    max_delay_ms: int,
    jitter: bool = True,
) -> float:
    """
    Calculate retry delay with exponential backoff and optional jitter.
    
    Args:
        attempt: Current attempt number (0-indexed)
        min_delay_ms: Minimum delay in milliseconds
        max_delay_ms: Maximum delay in milliseconds
        jitter: Whether to add random jitter
    
    Returns:
        Delay in seconds
    """
    delay_ms = min(min_delay_ms * (2 ** attempt), max_delay_ms)
    
    if jitter:
        # Add random jitter (+/- 10%)
        jitter_factor = random.uniform(0.9, 1.1)
        delay_ms = delay_ms * jitter_factor
    
    return delay_ms / 1000


def is_retryable_telegram_error(error: Exception) -> bool:
    """
    Classify Telegram errors as retryable or not.
    
    Args:
        error: Exception from Telegram API
    
    Returns:
        True if error is retryable
    """
    error_str = str(error).lower()
    
    # Retryable errors
    retryable_patterns = [
        "network",
        "timeout",
        "connection",
        "temporary",
        "retry",
        "rate limit",
        "too many requests",
        "502",
        "503",
        "504",
    ]
    
    for pattern in retryable_patterns:
        if pattern in error_str:
            return True
    
    # Non-retryable errors
    non_retryable_patterns = [
        "bad request",
        "unauthorized",
        "forbidden",
        "not found",
        "400",
        "401",
        "403",
        "404",
    ]
    
    for pattern in non_retryable_patterns:
        if pattern in error_str:
            return False
    
    # Default: assume retryable for unknown errors
    return True


def resolve_telegram_timeout(config: dict[str, Any]) -> int | None:
    """
    Resolve timeout configuration for Telegram.
    
    Args:
        config: Telegram channel config
    
    Returns:
        Timeout in seconds or None
    """
    timeout = config.get("timeoutSeconds")
    
    if timeout is not None and isinstance(timeout, (int, float)):
        return max(1, int(timeout))
    
    return None


def resolve_auto_select_family(config: dict[str, Any]) -> bool | None:
    """
    Resolve autoSelectFamily network setting.
    
    Enables IPv4 fallback on broken IPv6 networks.
    
    Args:
        config: Telegram channel config
    
    Returns:
        True to enable, False to disable, None for default
    """
    network_config = config.get("network", {})
    
    # Check environment variables
    if os.environ.get("OPENCLAW_TELEGRAM_ENABLE_AUTO_SELECT_FAMILY"):
        return True
    
    if os.environ.get("OPENCLAW_TELEGRAM_DISABLE_AUTO_SELECT_FAMILY"):
        return False
    
    # Check config
    auto_select = network_config.get("autoSelectFamily")
    if isinstance(auto_select, bool):
        return auto_select
    
    return None


async def retry_telegram_request(
    func,
    retry_config: dict[str, Any],
    error_logger=None,
) -> Any:
    """
    Retry a Telegram API request with exponential backoff.
    
    Args:
        func: Async function to retry
        retry_config: Retry configuration
        error_logger: Optional logger for errors
    
    Returns:
        Function result
    
    Raises:
        Last exception if all retries fail
    """
    import asyncio
    
    attempts = retry_config.get("attempts", 3)
    min_delay_ms = retry_config.get("min_delay_ms", 1000)
    max_delay_ms = retry_config.get("max_delay_ms", 30000)
    jitter = retry_config.get("jitter", True)
    
    last_error = None
    
    for attempt in range(attempts):
        try:
            return await func()
        
        except Exception as exc:
            last_error = exc
            
            # Check if retryable
            if not is_retryable_telegram_error(exc):
                raise
            
            # Last attempt - don't wait
            if attempt == attempts - 1:
                raise
            
            # Calculate delay and wait
            delay_sec = calculate_retry_delay(
                attempt, min_delay_ms, max_delay_ms, jitter
            )
            
            if error_logger:
                error_logger(
                    "Telegram request failed (attempt %d/%d): %s. Retrying in %.1fs",
                    attempt + 1, attempts, exc, delay_sec
                )
            
            await asyncio.sleep(delay_sec)
    
    raise last_error
