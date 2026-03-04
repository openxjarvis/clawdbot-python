"""Feishu SDK client factory.

Mirrors TypeScript: extensions/feishu/src/client.ts
Creates and caches lark_oapi.Client and lark_oapi.ws.Client instances.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .config import ResolvedFeishuAccount

logger = logging.getLogger(__name__)

# Module-level client caches — keyed by (app_id, domain_url)
_api_clients: dict[str, Any] = {}
_ws_clients: dict[str, Any] = {}


def _import_lark():
    """Lazy import lark_oapi so missing dep gives a clear message."""
    try:
        import lark_oapi as lark
        return lark
    except ImportError as e:
        raise ImportError(
            "lark_oapi is required for the Feishu channel. "
            "Install it with: pip install lark_oapi"
        ) from e


def create_feishu_client(account: ResolvedFeishuAccount) -> Any:
    """
    Return a cached lark_oapi.Client for the given account.

    Mirrors TS createFeishuClient().
    """
    lark = _import_lark()
    cache_key = f"{account.app_id}:{account.domain_url}"
    if cache_key in _api_clients:
        return _api_clients[cache_key]

    builder = (
        lark.Client.builder()
        .app_id(account.app_id)
        .app_secret(account.app_secret)
        .domain(account.domain_url)
        .app_type(lark.AppType.SELF)
        .log_level(lark.LogLevel.WARNING)
    )

    client = builder.build()
    _api_clients[cache_key] = client
    logger.debug(
        "[feishu] Created API client for account=%s domain=%s",
        account.account_id, account.domain_url,
    )
    return client


def create_feishu_ws_client(
    account: ResolvedFeishuAccount,
    event_handler: Any,
) -> Any:
    """
    Create a lark_oapi.ws.Client for WebSocket long connection.

    Mirrors TS createFeishuWSClient().
    Note: WS clients are NOT cached since they hold open connections.
    """
    lark = _import_lark()

    ws_client = lark.ws.Client(
        app_id=account.app_id,
        app_secret=account.app_secret,
        event_handler=event_handler,
        domain=account.domain_url,
        log_level=lark.LogLevel.WARNING,
    )
    logger.debug(
        "[feishu] Created WS client for account=%s domain=%s",
        account.account_id, account.domain_url,
    )
    return ws_client


def create_event_dispatcher(
    account: ResolvedFeishuAccount,
) -> Any:
    """
    Create an EventDispatcherHandler builder for the given account credentials.

    Returns the builder (not yet .build()); callers register handlers then call .build().
    Mirrors TS new Lark.EventDispatcher({ encryptKey, verificationToken }).
    """
    lark = _import_lark()
    builder = lark.EventDispatcherHandler.builder(
        encrypt_key=account.encrypt_key,
        verification_token=account.verification_token,
        level=lark.LogLevel.WARNING,
    )
    return builder


def clear_client_cache() -> None:
    """Clear all cached clients (useful for tests)."""
    _api_clients.clear()
    _ws_clients.clear()
