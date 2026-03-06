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
    Auth rate limiter — aligned with TS src/gateway/auth-rate-limit.ts.

    Features:
    - 4 named scopes: "default", "shared-secret", "device-token", "hook-auth"
    - maxAttempts=10 per scope within windowMs=60s
    - lockoutMs=300_000 (5-min lockout) after exceeding maxAttempts
    - Loopback IPs are always exempt from rate limiting
    """

    # Scope-specific defaults matching TS auth-rate-limit.ts
    SCOPE_LIMITS: dict[str, int] = {
        "default": 10,
        "shared-secret": 10,
        "device-token": 10,
        "hook-auth": 10,
    }

    def __init__(
        self,
        limit: int = 10,
        window_ms: int = 60_000,
        lockout_ms: int = 300_000,
    ):
        self.limit = limit
        self.window_ms = window_ms
        self.lockout_ms = lockout_ms  # 5-min lockout after maxAttempts exceeded
        self._buckets: dict[tuple[str, str], list[int]] = {}
        self._lockouts: dict[tuple[str, str], int] = {}  # key -> lockout_until_ms

    def _now_ms(self) -> int:
        import time
        return int(time.time() * 1000)

    def _scope_limit(self, scope: str) -> int:
        # If a custom limit was injected (not the default 10), always honour it.
        # Otherwise fall back to per-scope defaults (SCOPE_LIMITS).
        if self.limit != 10:
            return self.limit
        return self.SCOPE_LIMITS.get(scope, self.limit)

    def check(self, ip: str | None, scope: str) -> tuple[bool, int | None]:
        """Check if the request is allowed. Loopback IPs always pass."""
        if is_loopback_address(ip):
            return True, None

        key = (ip or "unknown", scope)
        now = self._now_ms()

        # Check lockout first
        lockout_until = self._lockouts.get(key)
        if lockout_until and now < lockout_until:
            retry_after_ms = lockout_until - now
            return False, retry_after_ms
        if lockout_until and now >= lockout_until:
            # Lockout expired — clear it and reset bucket
            del self._lockouts[key]
            self._buckets.pop(key, None)

        cut = now - self.window_ms
        bucket = [ts for ts in self._buckets.get(key, []) if ts >= cut]
        self._buckets[key] = bucket

        scope_limit = self._scope_limit(scope)
        if len(bucket) >= scope_limit:
            retry_after_ms = max(0, self.window_ms - (now - bucket[0]))
            return False, retry_after_ms
        return True, None

    def record_failure(self, ip: str | None, scope: str) -> None:
        """Record a failed auth attempt; triggers lockout after maxAttempts."""
        if is_loopback_address(ip):
            return

        key = (ip or "unknown", scope)
        now = self._now_ms()
        cut = now - self.window_ms
        bucket = [ts for ts in self._buckets.get(key, []) if ts >= cut]
        bucket.append(now)
        self._buckets[key] = bucket

        # Trigger lockout if limit exceeded
        scope_limit = self._scope_limit(scope)
        if len(bucket) >= scope_limit and key not in self._lockouts:
            self._lockouts[key] = now + self.lockout_ms

    def reset(self, ip: str | None, scope: str) -> None:
        """Reset rate limit state for an IP+scope (e.g. on successful auth)."""
        key = (ip or "unknown", scope)
        self._buckets.pop(key, None)
        self._lockouts.pop(key, None)


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


def _verify_tailscale_whois(client_ip: str, ts_login_header: str | None) -> AuthResult | None:
    """
    Verify Tailscale identity via local whois API (mirrors TS readTailscaleWhoisIdentity).

    Calls http://100.100.100.100/localapi/v0/whois?addr=<ip> to get the identity
    for the connecting IP, then cross-checks the tailscale-user-login header.

    Returns:
        AuthResult if Tailscale is running and the IP is a Tailscale peer.
        None if Tailscale is not running (e.g. non-Tailscale connection).
    """
    import urllib.request
    import urllib.error
    import json as _json

    try:
        url = f"http://100.100.100.100/localapi/v0/whois?addr={client_ip}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = _json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError:
        # Tailscale not running or peer not found — not a Tailscale connection
        return None
    except Exception as exc:
        logger.debug(f"Tailscale whois lookup failed for {client_ip}: {exc}")
        return None

    user_profile = data.get("UserProfile") or {}
    login_name: str = (user_profile.get("LoginName") or "").strip()

    if not login_name:
        # Could not identify user — treat as failed
        return AuthResult(ok=False, reason="tailscale_identity_unknown")

    # Cross-check the tailscale-user-login header if provided
    if ts_login_header and not safe_equal(ts_login_header.strip(), login_name):
        logger.warning(
            f"Tailscale whois mismatch: header '{ts_login_header}' != whois '{login_name}'"
        )
        return AuthResult(ok=False, reason="tailscale_login_mismatch")

    return AuthResult(ok=True, method=AuthMethod.TAILSCALE, user=login_name)


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
    
    # Tailscale auth — if enabled, verify via local Tailscale API whois endpoint
    if allow_tailscale and client_ip:
        ts_login = _header_value(headers, "tailscale-user-login")
        ts_result = _verify_tailscale_whois(client_ip, ts_login)
        if ts_result is not None:
            if ts_result.ok:
                if rate_limiter is not None:
                    rate_limiter.reset(client_ip, rate_limit_scope)
                return ts_result
            # Tailscale whois lookup failed — fall through to other auth methods
    
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
