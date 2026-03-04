"""Per-account monitor startup and event handler registration.

Mirrors TypeScript: extensions/feishu/src/monitor.account.ts

Each account gets:
  - An EventDispatcherHandler with all relevant events registered
  - Either WebSocket or Webhook transport
  - Bot open_id prefetch at startup
  - Per-chat serial queue (prevents concurrent LLM calls for the same chat)
  - Inbound debouncer (merges rapid-fire messages from the same sender)

IMPORTANT: All event callbacks from lark_oapi fire in the WS daemon thread
(not the main asyncio event loop). Coroutines must be dispatched back to the
main loop using asyncio.run_coroutine_threadsafe(coro, main_loop), NOT
asyncio.ensure_future (which would schedule on the WS thread's local loop).
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any, Callable, Awaitable

from ..base import InboundMessage
from .bot import handle_feishu_card_action, handle_feishu_message, handle_feishu_reaction
from .client import create_event_dispatcher, create_feishu_client
from .monitor_state import get_bot_open_id, set_bot_open_id
from .monitor_transport import start_websocket_transport, start_webhook_transport

if TYPE_CHECKING:
    from .config import ResolvedFeishuAccount

logger = logging.getLogger(__name__)

# Default debounce window: 0ms = disabled.  Set via account config ``inbound_debounce_ms``.
_DEFAULT_DEBOUNCE_MS: float = 0.0


# ---------------------------------------------------------------------------
# Bot open_id prefetch
# ---------------------------------------------------------------------------

async def prefetch_bot_open_id(
    account: ResolvedFeishuAccount,
) -> str | None:
    """
    GET /open-apis/bot/v3/info to learn the bot's own open_id.

    lark_oapi 1.5.3 does not include a code-generated lark_oapi.api.bot module,
    so we call the REST endpoint directly with a tenant access token obtained
    from lark_oapi.core.token.manager.TokenManager.

    Mirrors TS prefetchBotOpenId() / probe.ts.
    """
    from .monitor_state import get_probe_cache, set_probe_cache

    cached = get_probe_cache(account.account_id)
    if cached:
        return cached.get("open_id")

    try:
        import requests as _requests
        import lark_oapi as lark
        from lark_oapi.core.token.manager import TokenManager

        # Build a temporary Client to obtain its internal Config object, which
        # is required by TokenManager to fetch/cache the tenant access token.
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
                timeout=10,
            ),
        )
        data = response.json()
        open_id = (data.get("bot") or {}).get("open_id") or ""
        bot_name = (data.get("bot") or {}).get("app_name") or ""
        if open_id:
            set_bot_open_id(account.account_id, open_id)
            set_probe_cache(account.account_id, {"open_id": open_id, "bot_name": bot_name})
            logger.info(
                "[feishu] Bot open_id for account=%s: %s",
                account.account_id, open_id,
            )
            return open_id
        else:
            logger.warning(
                "[feishu] Bot open_id not found in response for account=%s: %s",
                account.account_id, data,
            )
    except Exception as exc:
        logger.warning(
            "[feishu] Failed to prefetch bot open_id for account=%s: %s",
            account.account_id, exc,
        )
    return None


# ---------------------------------------------------------------------------
# Per-chat serial queue
# ---------------------------------------------------------------------------

class _ChatQueue:
    """
    Serializes message processing per chat_id.

    Ensures messages within the same chat are handled one at a time, while
    different chats can run concurrently. Mirrors TS createChatQueue().
    """

    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue[Callable[[], Awaitable[None]] | None]] = {}
        self._consumers: dict[str, asyncio.Task] = {}

    def get_or_create(self, chat_id: str) -> asyncio.Queue:
        if chat_id not in self._queues:
            q: asyncio.Queue = asyncio.Queue()
            self._queues[chat_id] = q
            self._consumers[chat_id] = asyncio.create_task(
                self._consume(chat_id, q), name=f"feishu-chat-{chat_id}"
            )
        return self._queues[chat_id]

    async def enqueue(self, chat_id: str, task: Callable[[], Awaitable[None]]) -> None:
        q = self.get_or_create(chat_id)
        await q.put(task)

    async def _consume(self, chat_id: str, q: asyncio.Queue) -> None:
        while True:
            task = await q.get()
            if task is None:
                break
            try:
                await task()
            except Exception as exc:
                logger.error(
                    "[feishu] Chat queue error for chat=%s: %s", chat_id, exc, exc_info=True
                )

    def shutdown(self) -> None:
        for q in self._queues.values():
            q.put_nowait(None)
        for task in self._consumers.values():
            task.cancel()
        self._queues.clear()
        self._consumers.clear()


# ---------------------------------------------------------------------------
# Inbound debouncer
# ---------------------------------------------------------------------------

class _InboundDebouncer:
    """
    Per-(account, chat, sender, thread) message debouncer.

    Collects rapid-fire text messages from the same sender within a configurable
    time window, then merges their text content into one combined InboundMessage
    and dispatches it once. Prevents N simultaneous LLM calls on message bursts.

    Key: ``feishu:{account_id}:{chat_id}:{thread_key}:{sender_id}``

    Mirrors TS createInboundDebouncer() from plugin-sdk.
    """

    def __init__(
        self,
        debounce_ms: float,
        account_id: str,
        dispatch: Callable[[InboundMessage], Awaitable[None]],
    ) -> None:
        self._debounce_s = max(debounce_ms, 0.0) / 1000.0
        self._account_id = account_id
        self._dispatch = dispatch
        # key → accumulated messages
        self._pending: dict[str, list[InboundMessage]] = {}
        # key → scheduled flush handle
        self._handles: dict[str, asyncio.TimerHandle] = {}

    def _make_key(self, msg: InboundMessage) -> str:
        chat_id = msg.chat_id
        sender_id = msg.sender_id
        thread_id = (msg.metadata or {}).get("feishu_root_id") or ""
        thread_key = f"thread:{thread_id}" if thread_id else "chat"
        return f"feishu:{self._account_id}:{chat_id}:{thread_key}:{sender_id}"

    def _should_debounce(self, msg: InboundMessage) -> bool:
        """Only debounce non-empty text messages. Skip media, reactions, card actions."""
        if not msg.text:
            return False
        if (msg.metadata or {}).get("feishu_is_reaction"):
            return False
        if (msg.metadata or {}).get("feishu_is_card_action"):
            return False
        return True

    async def enqueue(self, msg: InboundMessage) -> None:
        if self._debounce_s <= 0 or not self._should_debounce(msg):
            await self._dispatch(msg)
            return

        key = self._make_key(msg)

        # Cancel pending flush timer
        handle = self._handles.pop(key, None)
        if handle:
            handle.cancel()

        self._pending.setdefault(key, []).append(msg)

        # Schedule new flush after debounce window
        loop = asyncio.get_running_loop()
        self._handles[key] = loop.call_later(
            self._debounce_s,
            lambda k=key: asyncio.ensure_future(self._flush(k)),
        )

    async def _flush(self, key: str) -> None:
        msgs = self._pending.pop(key, [])
        self._handles.pop(key, None)
        if not msgs:
            return

        if len(msgs) == 1:
            await self._dispatch(msgs[0])
            return

        # Merge: combine all text into one message using the last message's metadata
        texts = [m.text for m in msgs if m.text]
        combined_text = "\n".join(texts)
        last = msgs[-1]

        # Build merged InboundMessage preserving all metadata from the last message
        merged = InboundMessage(
            channel_id=last.channel_id,
            message_id=last.message_id,
            sender_id=last.sender_id,
            sender_name=last.sender_name,
            chat_id=last.chat_id,
            chat_type=last.chat_type,
            text=combined_text,
            timestamp=last.timestamp,
            reply_to=last.reply_to,
            attachments=last.attachments,
            metadata={
                **(last.metadata or {}),
                "feishu_debounce_count": len(msgs),
                "feishu_debounce_merged_ids": [
                    m.message_id for m in msgs if m.message_id
                ],
            },
        )
        logger.debug(
            "[feishu] Debounced %d messages from sender=%s chat=%s into one",
            len(msgs), last.sender_id, last.chat_id,
        )
        await self._dispatch(merged)


# ---------------------------------------------------------------------------
# Per-account monitor
# ---------------------------------------------------------------------------

async def start_account_monitor(
    account: ResolvedFeishuAccount,
    message_handler: Callable[[InboundMessage], Awaitable[None]],
    channel_id: str,
    stop_event: asyncio.Event,
) -> None:
    """
    Start the full monitor for a single Feishu account.

    Steps:
      1. Capture main event loop (for cross-thread dispatch)
      2. Create API client
      3. Prefetch bot open_id
      4. Build EventDispatcherHandler with all event registrations
         - Per-chat serial queue ensures in-order processing
         - Inbound debouncer merges rapid-fire messages from same sender
      5. Start transport (WebSocket or Webhook)

    Mirrors TS startAccountMonitor() with createChatQueue + createInboundDebouncer.
    """
    # Capture the main event loop NOW, before any background threads start.
    main_loop = asyncio.get_running_loop()

    client = create_feishu_client(account)

    # Prefetch bot open_id (sequential to avoid bursting the API)
    await prefetch_bot_open_id(account)
    bot_open_id = get_bot_open_id(account.account_id)

    # Per-chat serial queue — one consumer task per chat_id
    chat_queue = _ChatQueue()

    # Inbound debouncer — configurable window (default 0 = disabled)
    debounce_ms: float = getattr(account, "inbound_debounce_ms", _DEFAULT_DEBOUNCE_MS) or 0.0

    async def _dispatch_message(msg: InboundMessage) -> None:
        """Enqueue to the correct per-chat queue for serial processing."""
        raw_chat_id = (msg.metadata or {}).get("feishu_chat_id") or msg.chat_id
        await chat_queue.enqueue(raw_chat_id, lambda m=msg: message_handler(m))

    debouncer = _InboundDebouncer(
        debounce_ms=debounce_ms,
        account_id=account.account_id,
        dispatch=_dispatch_message,
    )

    # Build event dispatcher
    dispatcher_builder = create_event_dispatcher(account)

    # ----- im.message.receive_v1 -----
    def on_message(event: Any) -> None:
        async def _process() -> None:
            await handle_feishu_message(
                event,
                client,
                account,
                bot_open_id,
                debouncer.enqueue,   # route through debouncer → chat queue → handler
                channel_id,
            )
        asyncio.run_coroutine_threadsafe(_process(), main_loop)

    dispatcher_builder = dispatcher_builder.register_p2_im_message_receive_v1(on_message)

    # ----- im.chat.member.bot.added_v1 -----
    def on_bot_added(event: Any) -> None:
        logger.info("[feishu] Bot added to chat for account=%s", account.account_id)

    dispatcher_builder = dispatcher_builder.register_p2_im_chat_member_bot_added_v1(on_bot_added)

    # ----- im.chat.member.bot.deleted_v1 -----
    def on_bot_removed(event: Any) -> None:
        logger.info("[feishu] Bot removed from chat for account=%s", account.account_id)

    dispatcher_builder = dispatcher_builder.register_p2_im_chat_member_bot_deleted_v1(on_bot_removed)

    # ----- im.message.reaction.created_v1 -----
    async def _handle_reaction_verified(event: Any) -> None:
        """Verify bot authorship and filter app-initiated reactions before dispatching.

        Mirrors TS resolveReactionSyntheticEvent() — filters operator_type=app,
        verifies message ownership via API for "own" mode.
        """
        if account.reaction_notifications == "off":
            return

        msg_event = getattr(event, "event", event)

        # Filter operator_type=app reactions (bot's own ack reactions)
        operator = getattr(msg_event, "operator", None)
        if operator:
            operator_type = (
                getattr(operator, "operator_type", None)
                or getattr(operator, "type", None)
            )
            if operator_type == "app":
                logger.debug("[feishu] Skipping app-initiated reaction event")
                return

        # Verify message ownership via API
        is_own = False
        reaction_notifications = account.reaction_notifications
        message_id = getattr(msg_event, "message_id", None)

        if message_id and reaction_notifications in ("own", "all"):
            try:
                from lark_oapi.api.im.v1 import GetMessageRequest

                loop = asyncio.get_running_loop()
                request = GetMessageRequest.builder().message_id(message_id).build()
                response = await loop.run_in_executor(
                    None,
                    lambda: client.im.v1.message.get(request),
                )
                if response.success() and response.data:
                    items = getattr(response.data, "items", None) or []
                    for item in items:
                        sender = getattr(item, "sender", None)
                        if sender:
                            sid = getattr(sender, "id", None) or getattr(sender, "sender_id", None)
                            stype = getattr(sender, "sender_type", None)
                            if (
                                (sid and bot_open_id and sid == bot_open_id)
                                or (stype == "app" and sid and bot_open_id and sid == bot_open_id)
                            ):
                                is_own = True
                                break
            except Exception as verify_err:
                logger.debug(
                    "[feishu] Failed to verify reaction message ownership: %s", verify_err
                )

        if reaction_notifications == "own" and not is_own:
            logger.debug("[feishu] Skipping reaction on non-bot-authored message (mode=own)")
            return

        await handle_feishu_reaction(
            event,
            client,
            account,
            bot_open_id,
            message_handler,   # reactions bypass the debouncer (they're already synthetic)
            channel_id,
            is_own_message=is_own,
        )

    def on_reaction_created(event: Any) -> None:
        asyncio.run_coroutine_threadsafe(
            _handle_reaction_verified(event),
            main_loop,
        )

    dispatcher_builder = dispatcher_builder.register_p2_im_message_reaction_created_v1(on_reaction_created)

    # ----- card.action.trigger -----
    def on_card_action(event: Any) -> Any:
        asyncio.run_coroutine_threadsafe(
            handle_feishu_card_action(
                event,
                client,
                account,
                bot_open_id,
                message_handler,   # card actions also bypass debouncer
                channel_id,
            ),
            main_loop,
        )
        try:
            from lark_oapi.event.callback.model.p2_card_action_trigger import P2CardActionTriggerResponse
            return P2CardActionTriggerResponse({})
        except Exception:
            return None

    dispatcher_builder = dispatcher_builder.register_p2_card_action_trigger(on_card_action)

    # Build final handler
    event_handler = dispatcher_builder.build()

    # Start transport
    mode = account.connection_mode
    logger.info(
        "[feishu] Starting account=%s transport=%s debounce_ms=%s",
        account.account_id, mode, debounce_ms if debounce_ms > 0 else "disabled",
    )

    try:
        if mode == "webhook":
            await start_webhook_transport(account, event_handler, stop_event)
        else:
            await start_websocket_transport(account, event_handler, stop_event)
    finally:
        chat_queue.shutdown()
