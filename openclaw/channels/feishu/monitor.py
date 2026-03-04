"""Top-level Feishu monitor: multi-account fan-out.

Starts all configured accounts concurrently and manages their lifecycle.

Mirrors TypeScript: extensions/feishu/src/monitor.ts
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Callable, Awaitable

from ..base import InboundMessage
from .accounts import resolve_feishu_accounts
from .monitor_account import start_account_monitor

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


async def start_feishu_monitor(
    cfg: dict[str, Any],
    message_handler: Callable[[InboundMessage], Awaitable[None]],
    channel_id: str,
    stop_event: asyncio.Event,
) -> None:
    """
    Start monitors for all configured Feishu accounts concurrently.

    Mirrors TS startFeishuMonitor() which calls Promise.all over all accounts.

    Each account gets its own asyncio Task. If an account fails, it logs the
    error but does not affect other accounts.
    """
    accounts = resolve_feishu_accounts(cfg)

    if not accounts:
        logger.warning("[feishu] No valid accounts configured — monitor not started")
        await stop_event.wait()
        return

    logger.info("[feishu] Starting %d account monitor(s)", len(accounts))

    async def run_account(account: Any) -> None:
        try:
            await start_account_monitor(account, message_handler, channel_id, stop_event)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(
                "[feishu] Account monitor for %s failed: %s",
                account.account_id, e,
                exc_info=True,
            )

    # Run all account monitors concurrently; each runs until stop_event fires
    tasks = [
        asyncio.create_task(run_account(account), name=f"feishu-{account.account_id}")
        for account in accounts
    ]

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
    finally:
        logger.info("[feishu] All account monitors stopped")
