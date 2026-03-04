"""Standalone Feishu probe function.

Calls GET /open-apis/bot/v3/info to verify credentials and fetch bot identity,
independent of starting a monitor.

Used by:
  - Gateway health checks (openclaw channels status)
  - Channel onboarding / configure wizards
  - Any caller needing a quick credential verification

Mirrors TypeScript: extensions/feishu/src/probe.ts
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .config import ResolvedFeishuAccount

logger = logging.getLogger(__name__)

# Default timeout for probe requests (mirrors TS FEISHU_PROBE_REQUEST_TIMEOUT_MS)
FEISHU_PROBE_TIMEOUT_S: float = 10.0


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class FeishuProbeResult:
    """Result of a Feishu bot probe.

    Mirrors TS FeishuProbeResult (BaseProbeResult<string> & { appId, botName, botOpenId }).
    """
    ok: bool
    account_id: str
    app_id: str | None = None
    bot_name: str | None = None
    bot_open_id: str | None = None
    error: str | None = None
    latency_ms: float | None = None


# ---------------------------------------------------------------------------
# Probe implementation
# ---------------------------------------------------------------------------

async def probe_feishu(
    account: ResolvedFeishuAccount,
    *,
    timeout_s: float = FEISHU_PROBE_TIMEOUT_S,
    use_cache: bool = True,
) -> FeishuProbeResult:
    """
    Probe a Feishu account by calling GET /open-apis/bot/v3/info.

    Returns a FeishuProbeResult with ok=True and bot identity on success,
    or ok=False with an error message on failure.

    Results are cached with separate TTLs:
      - Success: 10 minutes
      - Error: 1 minute

    Mirrors TS probeFeishu().
    """
    from .monitor_state import get_probe_cache, set_probe_cache

    account_id = account.account_id
    cache_key = account_id

    if use_cache:
        cached = get_probe_cache(cache_key)
        if cached:
            return FeishuProbeResult(
                ok=not cached.get("error"),
                account_id=account_id,
                app_id=account.app_id,
                bot_name=cached.get("bot_name"),
                bot_open_id=cached.get("open_id"),
                error=cached.get("error"),
            )

    start_ms = time.monotonic() * 1000

    try:
        result = await asyncio.wait_for(
            _do_probe(account),
            timeout=timeout_s,
        )
        latency_ms = time.monotonic() * 1000 - start_ms

        if result.get("error"):
            set_probe_cache(cache_key, result, is_error=True)
        else:
            set_probe_cache(cache_key, result, is_error=False)
            # Keep bot_open_ids in sync
            open_id = result.get("open_id", "")
            if open_id:
                from .monitor_state import set_bot_open_id
                set_bot_open_id(account_id, open_id)

        return FeishuProbeResult(
            ok=not result.get("error"),
            account_id=account_id,
            app_id=account.app_id,
            bot_name=result.get("bot_name"),
            bot_open_id=result.get("open_id"),
            error=result.get("error"),
            latency_ms=latency_ms,
        )

    except asyncio.TimeoutError:
        err = f"probe timed out after {timeout_s * 1000:.0f}ms"
        logger.warning("[feishu] Probe timeout for account=%s", account_id)
        set_probe_cache(cache_key, {"error": err}, is_error=True)
        return FeishuProbeResult(
            ok=False, account_id=account_id, app_id=account.app_id, error=err
        )
    except Exception as exc:
        err = str(exc)
        logger.warning("[feishu] Probe error for account=%s: %s", account_id, err)
        set_probe_cache(cache_key, {"error": err}, is_error=True)
        return FeishuProbeResult(
            ok=False, account_id=account_id, app_id=account.app_id, error=err
        )


async def _do_probe(account: ResolvedFeishuAccount) -> dict[str, Any]:
    """Internal: fetch bot info and return a flat result dict."""
    try:
        import requests as _requests
        import lark_oapi as lark
        from lark_oapi.core.token.manager import TokenManager

        tmp_client = (
            lark.Client.builder()
            .app_id(account.app_id)
            .app_secret(account.app_secret)
            .domain(account.domain_url)
            .app_type(lark.AppType.SELF)
            .build()
        )
        conf = tmp_client._config

        loop = asyncio.get_running_loop()
        token = await loop.run_in_executor(
            None,
            lambda: TokenManager.get_self_tenant_token(conf),
        )
        response = await loop.run_in_executor(
            None,
            lambda: _requests.get(
                f"{account.domain_url}/open-apis/bot/v3/info",
                headers={"Authorization": f"Bearer {token}"},
                timeout=FEISHU_PROBE_TIMEOUT_S,
            ),
        )
        data = response.json()
        bot = data.get("bot") or data.get("data", {}).get("bot") or {}
        open_id: str = bot.get("open_id") or ""
        bot_name: str = bot.get("app_name") or bot.get("bot_name") or ""

        if not open_id:
            return {"error": f"bot open_id missing in response (code={data.get('code')})"}

        return {"open_id": open_id, "bot_name": bot_name}

    except Exception as exc:
        return {"error": str(exc)}
