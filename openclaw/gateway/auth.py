"""
Gateway authentication

Matches TypeScript src/gateway/auth.ts with timing-safe comparisons
and structured error codes.
"""
from __future__ import annotations

import hmac
import logging
from enum import Enum
from typing import NamedTuple

logger = logging.getLogger(__name__)


class AuthMode(str, Enum):
    """Gateway authentication mode."""
    NONE = "none"
    TOKEN = "token"
    PASSWORD = "password"
    TRUSTED_PROXY = "trusted-proxy"


class AuthMethod(str, Enum):
    """Authentication method used."""
    TOKEN = "token"
    PASSWORD = "password"
    TAILSCALE = "tailscale"
    DEVICE_TOKEN = "device-token"
    LOCAL_DIRECT = "local-direct"
    TRUSTED_PROXY = "trusted-proxy"


class AuthResult(NamedTuple):
    """Result of authentication attempt."""
    ok: bool
    method: AuthMethod | None = None
    user: str | None = None
    reason: str | None = None
    rate_limited: bool = False
    retry_after_ms: int | None = None


def safe_equal(a: str, b: str) -> bool:
    """
    Timing-safe string comparison (matches TS safeEqual lines 35-39).
    
    Uses hmac.compare_digest which is timing-safe in Python.
    Buffers are same length first (quick reject, then timing-safe compare).
    
    Args:
        a: First string
        b: Second string
    
    Returns:
        True if strings are equal
    """
    if len(a) != len(b):
        return False
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def is_loopback_address(ip: str | None) -> bool:
    """
    Check if IP is loopback (matches TS isLoopbackAddress lines 46-62).
    
    Args:
        ip: IP address string
    
    Returns:
        True if loopback
    """
    if not ip:
        return False
    
    if ip == "127.0.0.1":
        return True
    if ip.startswith("127."):
        return True
    if ip == "::1":
        return True
    if ip.startswith("::ffff:127."):
        return True
    
    return False


def _header_value(headers: dict[str, str] | None, key: str) -> str | None:
    if not headers:
        return None
    return headers.get(key.lower())


def _resolve_host_name(host_header: str | None) -> str:
    if not host_header:
        return ""
    host = host_header.strip().lower()
    if host.startswith("[") and "]" in host:
        return host[1 : host.index("]")]
    if ":" in host:
        return host.split(":", 1)[0]
    return host


def _is_trusted_proxy_address(remote_addr: str | None, trusted_proxies: list[str] | None) -> bool:
    if not remote_addr or not trusted_proxies:
        return False
    if remote_addr in trusted_proxies:
        return True
    return any(remote_addr.startswith(prefix.rstrip("*")) for prefix in trusted_proxies if prefix.endswith("*"))


def is_local_direct_request(
    client_ip: str | None,
    host_header: str | None,
    headers: dict[str, str] | None = None,
    remote_addr: str | None = None,
    trusted_proxies: list[str] | None = None,
) -> bool:
    """
    Local-direct detection aligned with TS gateway auth net checks.
    """
    if not is_loopback_address(client_ip):
        return False
    host = _resolve_host_name(host_header)
    host_is_local = host in ("localhost", "127.0.0.1", "::1")
    host_is_tailscale_serve = host.endswith(".ts.net")
    has_forwarded = bool(
        _header_value(headers, "x-forwarded-for")
        or _header_value(headers, "x-real-ip")
        or _header_value(headers, "x-forwarded-host")
    )
    remote_is_trusted_proxy = _is_trusted_proxy_address(remote_addr, trusted_proxies)
    return (host_is_local or host_is_tailscale_serve) and (not has_forwarded or remote_is_trusted_proxy)


class AuthRateLimiter:
    """
    Small auth limiter used by gateway connect.
    """

    def __init__(self, limit: int = 8, window_ms: int = 60_000):
        self.limit = limit
        self.window_ms = window_ms
        self._buckets: dict[tuple[str, str], list[int]] = {}

    def _now_ms(self) -> int:
        import time

        return int(time.time() * 1000)

    def check(self, ip: str | None, scope: str) -> tuple[bool, int | None]:
        key = (ip or "unknown", scope)
        now = self._now_ms()
        cut = now - self.window_ms
        bucket = [ts for ts in self._buckets.get(key, []) if ts >= cut]
        self._buckets[key] = bucket
        if len(bucket) >= self.limit:
            retry_after_ms = max(0, self.window_ms - (now - bucket[0]))
            return False, retry_after_ms
        return True, None

    def record_failure(self, ip: str | None, scope: str) -> None:
        key = (ip or "unknown", scope)
        self._buckets.setdefault(key, []).append(self._now_ms())

    def reset(self, ip: str | None, scope: str) -> None:
        key = (ip or "unknown", scope)
        self._buckets.pop(key, None)


def authorize_gateway_token(
    config_token: str | None,
    request_token: str | None,
) -> AuthResult:
    """
    Authorize via token (matches TS token auth logic lines 263-273).
    
    Args:
        config_token: Expected token from config
        request_token: Token from request
    
    Returns:
        AuthResult
    """
    if not config_token:
        return AuthResult(ok=False, reason="token_missing_config")
    
    if not request_token:
        return AuthResult(ok=False, reason="token_missing")
    
    if not safe_equal(request_token, config_token):
        return AuthResult(ok=False, reason="token_mismatch")
    
    return AuthResult(ok=True, method=AuthMethod.TOKEN)


def authorize_gateway_password(
    config_password: str | None,
    request_password: str | None,
) -> AuthResult:
    """
    Authorize via password (matches TS password auth logic lines 276-287).
    
    Args:
        config_password: Expected password from config
        request_password: Password from request
    
    Returns:
        AuthResult
    """
    if not config_password:
        return AuthResult(ok=False, reason="password_missing_config")
    
    if not request_password:
        return AuthResult(ok=False, reason="password_missing")
    
    if not safe_equal(request_password, config_password):
        return AuthResult(ok=False, reason="password_mismatch")
    
    return AuthResult(ok=True, method=AuthMethod.PASSWORD)


def authorize_gateway_connect(
    auth_mode: AuthMode,
    config_token: str | None = None,
    config_password: str | None = None,
    request_token: str | None = None,
    request_password: str | None = None,
    allow_tailscale: bool = False,
    client_ip: str | None = None,
    trusted_proxies: list[str] | None = None,
    headers: dict[str, str] | None = None,
    host_header: str | None = None,
    remote_addr: str | None = None,
    trusted_proxy_config: dict[str, object] | None = None,
    rate_limiter: AuthRateLimiter | None = None,
    rate_limit_scope: str = "shared-secret",
) -> AuthResult:
    """
    Main gateway connection authorization (matches TS authorizeGatewayConnect lines 238-291).
    
    Auth modes:
    - token: Requires matching token
    - password: Requires matching password
    - tailscale: Requires verified Tailscale user (if enabled)
    - local-direct: Auto-allow for loopback connections
    
    Args:
        auth_mode: Authentication mode
        config_token: Expected token from config
        config_password: Expected password from config
        request_token: Token from request
        request_password: Password from request
        allow_tailscale: Whether to allow Tailscale auth
        client_ip: Client IP address
        trusted_proxies: List of trusted proxy addresses
    
    Returns:
        AuthResult
    """
    # Check for local direct connection (bypass auth)
    if is_local_direct_request(
        client_ip=client_ip,
        host_header=host_header,
        headers=headers,
        remote_addr=remote_addr,
        trusted_proxies=trusted_proxies,
    ):
        logger.debug(f"Local direct request from {client_ip}, bypassing auth")
        return AuthResult(ok=True, method=AuthMethod.LOCAL_DIRECT)

    if rate_limiter is not None:
        allowed, retry_after_ms = rate_limiter.check(client_ip, rate_limit_scope)
        if not allowed:
            return AuthResult(
                ok=False,
                reason="rate_limited",
                rate_limited=True,
                retry_after_ms=retry_after_ms,
            )

    if auth_mode == AuthMode.TRUSTED_PROXY:
        if not trusted_proxy_config:
            return AuthResult(ok=False, reason="trusted_proxy_config_missing")
        if not trusted_proxies:
            return AuthResult(ok=False, reason="trusted_proxy_no_proxies_configured")
        if not _is_trusted_proxy_address(remote_addr, trusted_proxies):
            return AuthResult(ok=False, reason="trusted_proxy_untrusted_source")
        user_header = str(trusted_proxy_config.get("userHeader") or "").strip().lower()
        if not user_header:
            return AuthResult(ok=False, reason="trusted_proxy_user_header_missing")
        required_headers = trusted_proxy_config.get("requiredHeaders") or []
        for header in required_headers:
            if not _header_value(headers, str(header).lower()):
                return AuthResult(ok=False, reason=f"trusted_proxy_missing_header_{header}")
        user_value = (_header_value(headers, user_header) or "").strip()
        if not user_value:
            return AuthResult(ok=False, reason="trusted_proxy_user_missing")
        allow_users = trusted_proxy_config.get("allowUsers") or []
        if allow_users and user_value not in allow_users:
            return AuthResult(ok=False, reason="trusted_proxy_user_not_allowed")
        if rate_limiter is not None:
            rate_limiter.reset(client_ip, rate_limit_scope)
        return AuthResult(ok=True, method=AuthMethod.TRUSTED_PROXY, user=user_value)
    
    # Tailscale auth (if enabled)
    if allow_tailscale and client_ip:
        # TODO: Implement Tailscale whois lookup
        # For now, we don't have Tailscale integration in Python
        logger.debug("Tailscale auth not yet implemented in Python")
    
    # Token auth
    if auth_mode == AuthMode.TOKEN:
        res = authorize_gateway_token(config_token, request_token)
        if not res.ok and rate_limiter is not None:
            rate_limiter.record_failure(client_ip, rate_limit_scope)
        if res.ok and rate_limiter is not None:
            rate_limiter.reset(client_ip, rate_limit_scope)
        return res
    
    # Password auth
    if auth_mode == AuthMode.PASSWORD:
        res = authorize_gateway_password(config_password, request_password)
        if not res.ok and rate_limiter is not None:
            rate_limiter.record_failure(client_ip, rate_limit_scope)
        if res.ok and rate_limiter is not None:
            rate_limiter.reset(client_ip, rate_limit_scope)
        return res
    if auth_mode == AuthMode.NONE:
        return AuthResult(ok=True, method=None)
    return AuthResult(ok=False, reason="unauthorized")


def validate_auth_config(
    auth_mode: AuthMode, token: str | None, password: str | None, trusted_proxy: dict[str, object] | None = None
):
    """
    Validate auth configuration (matches TS guardGatewayAuth lines 225-235).
    
    Raises:
        ValueError: If configuration is invalid
    """
    if auth_mode == AuthMode.TOKEN and not token:
        raise ValueError(
            "gateway auth mode is token, but no token was configured "
            "(set gateway.auth.token or OPENCLAW_GATEWAY_TOKEN)"
        )
    
    if auth_mode == AuthMode.PASSWORD and not password:
        raise ValueError(
            "gateway auth mode is password, but no password was configured "
            "(set gateway.auth.password)"
        )
    if auth_mode == AuthMode.TRUSTED_PROXY:
        if not trusted_proxy:
            raise ValueError(
                "gateway auth mode is trusted-proxy, but no trusted proxy config was provided"
            )
        user_header = str(trusted_proxy.get("userHeader") or "").strip()
        if not user_header:
            raise ValueError(
                "gateway auth mode is trusted-proxy, but trustedProxy.userHeader is empty"
            )
