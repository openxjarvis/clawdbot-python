"""Telegram channel implementation"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timezone
from typing import Any, Optional

from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    MessageReactionHandler,
    filters,
)

from ..base import ChannelCapabilities, ChannelPlugin, InboundMessage
from ..chat_commands import ChatCommandExecutor, ChatCommandParser
from .commands_extended import (
    register_extended_commands,  # noqa: F401 – kept for backward compat, not used directly
)
from .i18n_support import register_lang_handlers
from .sent_message_cache import record_sent_message, was_sent_by_bot
from .sticker_cache import (
    CachedSticker,
    cache_sticker,
    describe_sticker_image,
    get_cached_sticker,
)
from .update_dedupe import TelegramUpdateDedupe, callback_key, message_key, update_key
from .update_offset_store import (
    read_telegram_update_offset,
    write_telegram_update_offset,
)

logger = logging.getLogger(__name__)

# Reconnect policy — mirrors TS TELEGRAM_POLL_RESTART_POLICY
_POLL_BACKOFF_INITIAL = 2.0       # seconds (TS initialMs: 2000)
_POLL_BACKOFF_MAX = 30.0          # seconds (TS maxMs: 30000)
_POLL_BACKOFF_FACTOR = 1.8        # TS factor: 1.8
_POLL_JITTER = 0.25               # TS jitter: 0.25
_MAX_RETRY_TIME_S = 60 * 60       # 1 hour (TS maxRetryTime: 60 min)
_POLL_TIMEOUT_S = 30              # matches TS grammY fetch.timeout: 30
_HEALTH_CHECK_INTERVAL_S = 60     # health check interval
_HEALTH_CHECK_TIMEOUT_S = 15      # get_me() timeout
_HEALTH_MAX_FAILURES = 3          # consecutive failures before forced restart

# Backwards-compat aliases used in existing code
_CONFLICT_BACKOFF_INITIAL = _POLL_BACKOFF_INITIAL
_CONFLICT_BACKOFF_MAX = _POLL_BACKOFF_MAX
_CONFLICT_BACKOFF_FACTOR = _POLL_BACKOFF_FACTOR
_CONFLICT_MAX_RETRY_TIME = 5 * 60


# ---------------------------------------------------------------------------
# Network error classification — mirrors TS isRecoverableTelegramNetworkError
# ---------------------------------------------------------------------------

_RECOVERABLE_ERROR_CODES = frozenset({
    "ECONNRESET", "ECONNREFUSED", "EPIPE", "ETIMEDOUT",
    "ESOCKETTIMEDOUT", "ENETUNREACH", "EHOSTUNREACH",
    "ENOTFOUND", "ECONNABORTED",
})

_RECOVERABLE_ERROR_NAMES = frozenset({
    "AbortError", "TimeoutError", "ConnectTimeoutError",
    "RequestError", "FetchError",
})

_RECOVERABLE_MSG_FRAGMENTS = (
    "network error", "socket hang up", "timeout", "econnreset",
    "undici", "fetch failed", "ETIMEDOUT", "ECONNREFUSED",
    "ENOTFOUND", "read ECONNRESET", "write EPIPE",
)


def _is_recoverable_network_error(exc: BaseException) -> bool:
    """Return True when *exc* looks like a transient network error.

    Mirrors TS ``isRecoverableTelegramNetworkError``.
    """
    import telegram.error as tg_err

    if isinstance(exc, (tg_err.NetworkError, tg_err.TimedOut)):
        return True

    msg = str(exc).lower()
    name = type(exc).__name__

    if name in _RECOVERABLE_ERROR_NAMES:
        return True
    if any(frag.lower() in msg for frag in _RECOVERABLE_MSG_FRAGMENTS):
        return True

    # Recurse into cause chain (mirrors TS recursive inspection)
    cause = getattr(exc, "__cause__", None) or getattr(exc, "__context__", None)
    if cause is not None and cause is not exc:
        return _is_recoverable_network_error(cause)

    return False


class TelegramChannel(ChannelPlugin):
    """Telegram bot channel"""

    def __init__(self, bot_token: str | None = None):
        super().__init__()
        self.id = "telegram"
        self.label = "Telegram"
        self.capabilities = ChannelCapabilities(
            chat_types=["direct", "group", "channel"],
            supports_media=True,
            supports_reactions=True,
            supports_threads=False,
            supports_polls=True,
            block_streaming=True,
            native_commands=True,
            supports_edit=True,
            supports_unsend=True,
            supports_reply=True,
        )
        self._app: Application | None = None
        self._bot_token: str | None = None
        self._command_parser: ChatCommandParser | None = None
        self._command_executor: ChatCommandExecutor | None = None
        self._owner_id: str | None = None
        self._config: dict | None = None
        self._cfg: dict[str, Any] = {}
        self._account_id: str | None = None
        self._agent_runtime: Any = None
        self._session_manager: Any = None
        self._dedupe = TelegramUpdateDedupe()
        self._conflict_backoff = _CONFLICT_BACKOFF_INITIAL
        self._conflict_retry_task: asyncio.Task | None = None
        self._conflict_recovery_in_progress: bool = False

        # Media group buffering (albums)
        self._media_group_buffer: dict[str, dict] = {}
        self._media_group_processing: asyncio.Task | None = None

        # Text fragment buffering (long messages split by Telegram)
        self._text_fragment_buffer: dict[str, dict] = {}
        self._text_fragment_processing: asyncio.Task | None = None

        if bot_token is not None:
            if not bot_token:
                raise ValueError("bot_token cannot be an empty string")
            self._bot_token = bot_token

    @property
    def bot_token(self) -> str | None:
        """Return the configured bot token."""
        return self._bot_token

    async def _make_api_call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Make a raw Telegram Bot API call.

        Args:
            method: Telegram Bot API method (e.g. "sendMessage")
            params: Method parameters

        Returns:
            Parsed API response dict
        """
        import aiohttp
        if not self._bot_token:
            raise ValueError("Bot token not configured")
        url = f"https://api.telegram.org/bot{self._bot_token}/{method}"
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=params or {}) as resp:
                data = await resp.json()
                if not data.get("ok"):
                    raise Exception(f"Telegram API error: {data.get('description', 'Unknown error')}")
                return data.get("result", {})

    async def send_message(self, chat_id: str, text: str, **kwargs) -> dict[str, Any]:
        """
        Send a text message to a chat.

        Args:
            chat_id: Telegram chat ID
            text: Message text

        Returns:
            Sent message dict with at least ``message_id``
        """
        return await self._make_api_call("sendMessage", {"chat_id": chat_id, "text": text, **kwargs})

    async def send_photo(self, chat_id: str, photo: str, **kwargs) -> dict[str, Any]:
        """
        Send a photo to a chat.

        Args:
            chat_id: Telegram chat ID
            photo: Photo URL or file_id

        Returns:
            Sent message dict
        """
        return await self._make_api_call("sendPhoto", {"chat_id": chat_id, "photo": photo, **kwargs})

    def parse_message(self, telegram_message: dict[str, Any]) -> dict[str, Any]:
        """
        Parse a raw Telegram message dict into a normalised format.

        Args:
            telegram_message: Raw Telegram message object

        Returns:
            Normalised message dict with ``text``, ``user_id``, ``chat_id``,
            ``message_id``, ``is_command`` fields.
        """
        from_user = telegram_message.get("from", {})
        chat = telegram_message.get("chat", {})
        text = telegram_message.get("text", "")
        entities = telegram_message.get("entities", [])

        is_command = any(e.get("type") == "bot_command" for e in entities)

        return {
            "message_id": str(telegram_message.get("message_id", "")),
            "user_id": str(from_user.get("id", "")),
            "chat_id": str(chat.get("id", "")),
            "text": text,
            "is_command": is_command,
            "date": telegram_message.get("date"),
            "from": from_user,
        }

    async def start(self, config: dict[str, Any]) -> None:
        """Start Telegram bot"""
        self._bot_token = config.get("botToken") or config.get("bot_token")

        if not self._bot_token:
            raise ValueError("Telegram bot token not provided")

        # Get owner ID for command permissions
        self._owner_id = config.get("ownerId") or config.get("owner_id")
        self._config = config
        self._cfg = config  # Alias for compatibility

        logger.info("Starting Telegram channel...")

        # Initialize chat command system
        self._command_parser = ChatCommandParser()
        # Note: command_executor will be initialized once we have session_manager
        # This would typically be set via set_message_handler or similar

        # Create application
        self._app = Application.builder().token(self._bot_token).build()

        # Register i18n language switching handlers
        register_lang_handlers(self._app)

        # NOTE: register_extended_commands() is intentionally NOT called here.
        # All slash-command handlers are registered later in _register_dynamic_command_handlers()
        # via the proper command pipeline (command_pipeline.py).  The old extended-command
        # handlers required bot_data["agent_runtime"] which is never populated, producing the
        # "Command cannot be executed" error.

        # Add callback query handler for inline keyboards
        self._app.add_handler(CallbackQueryHandler(self._handle_callback_query))

        # Add message handlers for all types (text and media)
        # Handle text messages
        self._app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_telegram_message)
        )
        # Handle photo messages
        self._app.add_handler(
            MessageHandler(filters.PHOTO, self._handle_telegram_media)
        )
        # Handle video messages
        self._app.add_handler(
            MessageHandler(filters.VIDEO, self._handle_telegram_media)
        )
        # Handle audio messages
        self._app.add_handler(
            MessageHandler(filters.AUDIO | filters.VOICE, self._handle_telegram_media)
        )
        # Handle document messages
        self._app.add_handler(
            MessageHandler(filters.Document.ALL, self._handle_telegram_media)
        )

        # Handle message reactions
        self._app.add_handler(
            MessageReactionHandler(self._handle_reaction_update)
        )

        # Start bot
        await self._app.initialize()
        await self._app.start()

        # Get bot info after initialization
        bot_info = await self._app.bot.get_me()
        # Resolve account_id: use configured accountId if present, else "default" (matches TS resolveAccountId())
        cfg_account_id = (
            (config or {}).get("accountId")
            or (config or {}).get("account_id")
            or ""
        )
        account_id = str(cfg_account_id).strip() if cfg_account_id else ""
        logger.info(f"Bot initialized: @{bot_info.username} (account_id: {account_id})")

        # Create a minimal config dict for command handler
        cmd_config = {
            "channels": {
                "telegram": {
                    "accounts": {
                        account_id: {
                            "allowFrom": []  # Allow all for now
                        }
                    }
                }
            },
            "agents": {
                "defaults": {
                    "model": config.get("model", "google/gemini-3-pro-preview")
                }
            }
        }

        self._account_id = account_id

        # Register conflict/error handler for update-processing errors
        # (Updater polling errors are handled via error_callback in start_polling below)
        self._app.add_error_handler(self._handle_polling_error)

        # Delete any existing webhook and clear pending updates to avoid conflicts
        # This ensures clean state when switching from webhook to polling mode
        await self._app.bot.delete_webhook(drop_pending_updates=True)
        logger.info("Cleared webhook and pending updates")

        # Register dynamic command handlers (all native commands from registry)
        # Must be after bot initialization so we have account_id and cfg
        await self._register_dynamic_command_handlers()

        # Register bot commands with Telegram
        await self._register_bot_commands()

        # Set bot menu button (optional)
        await self._setup_menu_button()

        # Restore persisted update offset so we don't reprocess old updates
        saved_offset = read_telegram_update_offset(account_id)
        if saved_offset is not None:
            logger.info("Resuming from persisted update offset %d", saved_offset)

        await self._app.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=False,  # We already dropped via delete_webhook
        )

        self._running = True
        self._conflict_backoff = _POLL_BACKOFF_INITIAL
        # Launch background health monitor
        self._health_monitor_task: asyncio.Task | None = asyncio.create_task(
            self._run_health_monitor()
        )
        logger.info("Telegram channel started")

    async def stop(self) -> None:
        """Stop Telegram bot"""
        self._running = False
        self._conflict_recovery_in_progress = False
        if self._conflict_retry_task and not self._conflict_retry_task.done():
            self._conflict_retry_task.cancel()
        health_task = getattr(self, "_health_monitor_task", None)
        if health_task and not health_task.done():
            health_task.cancel()
        if self._app:
            logger.info("Stopping Telegram channel...")
            try:
                await self._app.updater.stop()
            except Exception:
                pass
            await self._app.stop()
            await self._app.shutdown()
            self._running = False
            logger.info("Telegram channel stopped")

    async def _handle_polling_error(
        self, update: object, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """PTB global error handler — mirrors TS monitor.ts error handling.

        Handles Conflict (409), recoverable network errors, and unknown errors
        with appropriate restart / retry strategies.
        """
        import telegram.error as tg_err

        exc = context.error
        if exc is None:
            return

        if isinstance(exc, tg_err.Conflict):
            if self._conflict_recovery_in_progress:
                logger.debug("Telegram Conflict — recovery already in progress, skipping duplicate")
                return
            logger.warning(
                "Telegram Conflict (another bot instance is polling): %s — "
                "restarting with backoff",
                exc,
            )
            self._schedule_polling_restart(reason="conflict")

        elif _is_recoverable_network_error(exc):
            # Network errors are transient — force a polling restart
            # (mirrors TS unhandled-rejection handler for network errors)
            logger.warning("Telegram recoverable network error — scheduling restart: %s", exc)
            self._schedule_polling_restart(reason="network")

        elif isinstance(exc, tg_err.TimedOut):
            logger.debug("Telegram request timed out (auto-retry by PTB): %s", exc)

        elif isinstance(exc, tg_err.InvalidToken):
            logger.critical("Telegram InvalidToken — will not retry: %s", exc)

        else:
            logger.error("Unhandled Telegram error: %s", exc, exc_info=True)

    def _schedule_polling_restart(self, reason: str = "unknown") -> None:
        """Schedule a polling restart, cancelling any in-progress restart."""
        if self._conflict_recovery_in_progress:
            return
        if self._conflict_retry_task and not self._conflict_retry_task.done():
            self._conflict_retry_task.cancel()
        self._conflict_retry_task = asyncio.create_task(
            self._restart_polling_after_conflict(reason=reason)
        )

    async def _restart_polling_after_conflict(self, reason: str = "unknown") -> None:
        """Stop polling, wait with exponential backoff, then resume.

        Mirrors TS ``runPollingCycle`` restart logic with
        ``TELEGRAM_POLL_RESTART_POLICY``.
        """
        if self._conflict_recovery_in_progress:
            return
        self._conflict_recovery_in_progress = True
        try:
            import random
            wait = self._conflict_backoff
            jitter = wait * _POLL_JITTER * (2 * random.random() - 1)
            wait_with_jitter = max(0.5, wait + jitter)

            # Increase backoff for the next failure (capped)
            self._conflict_backoff = min(
                self._conflict_backoff * _POLL_BACKOFF_FACTOR,
                _POLL_BACKOFF_MAX,
            )
            logger.info(
                "Polling restart (%s): pausing %.1fs before retry",
                reason,
                wait_with_jitter,
            )
            await asyncio.sleep(wait_with_jitter)

            if not self._running or self._app is None:
                return

            # Persist current update offset before stopping
            if self._account_id and self._app.updater:
                try:
                    current_offset = getattr(self._app.updater, "_last_update_id", None)
                    if current_offset is not None and current_offset > 0:
                        write_telegram_update_offset(self._account_id, current_offset)
                except Exception:
                    pass

            try:
                await self._app.updater.stop()
            except Exception as stop_exc:
                logger.debug("Updater stop during restart (%s): %s", reason, stop_exc)

            try:
                await self._app.updater.start_polling(
                    allowed_updates=Update.ALL_TYPES,
                    drop_pending_updates=False,
                )
                # Reset backoff on successful restart
                self._conflict_backoff = _POLL_BACKOFF_INITIAL
                logger.info("Polling restarted after %s (backoff reset)", reason)
            except Exception as start_exc:
                logger.error("Failed to restart polling (%s): %s", reason, start_exc)
                self._conflict_recovery_in_progress = False
                self._schedule_polling_restart(reason=reason)
        finally:
            self._conflict_recovery_in_progress = False

    async def _run_health_monitor(self) -> None:
        """Periodically check that the bot is reachable.

        Mirrors TS EnhancedTelegramChannel health check: calls ``get_me()``
        every ``_HEALTH_CHECK_INTERVAL_S`` seconds.  After
        ``_HEALTH_MAX_FAILURES`` consecutive failures, forces a polling
        restart.
        """
        failures = 0
        while self._running and self._app is not None:
            try:
                await asyncio.sleep(_HEALTH_CHECK_INTERVAL_S)
                if not self._running or self._app is None:
                    break
                await asyncio.wait_for(
                    self._app.bot.get_me(),
                    timeout=_HEALTH_CHECK_TIMEOUT_S,
                )
                failures = 0  # reset on success
            except asyncio.CancelledError:
                break
            except Exception as exc:
                failures += 1
                logger.warning(
                    "Telegram health check failed (%d/%d): %s",
                    failures,
                    _HEALTH_MAX_FAILURES,
                    exc,
                )
                if failures >= _HEALTH_MAX_FAILURES:
                    logger.error(
                        "Telegram health check failed %d times — forcing polling restart",
                        failures,
                    )
                    failures = 0
                    self._schedule_polling_restart(reason="health-check-failure")

    async def send_typing(self, target: str) -> None:
        """Send a 'typing…' chat action to show the bot is processing."""
        if not self._app:
            return
        try:
            chat_id = int(target) if str(target).lstrip("-").isdigit() else target
            await self._app.bot.send_chat_action(chat_id=chat_id, action="typing")
        except Exception as exc:
            logger.debug("send_typing failed for %s: %s", target, exc)

    def _fire_message_sent_hook(
        self,
        to: str,
        content: str,
        success: bool,
        message_id: str | None = None,
        error: str | None = None,
        session_key: str | None = None,
    ) -> None:
        """Fire internal hook for message:sent (fire-and-forget)."""
        import asyncio

        if not session_key:
            return

        try:
            from openclaw.hooks.internal_hooks import (
                create_internal_hook_event,
                trigger_internal_hook,
            )

            context = {
                "to": to,
                "content": content,
                "success": success,
                "channelId": "telegram",
                "channel_id": "telegram",
                "accountId": None,
                "account_id": None,
                "conversationId": to,
                "conversation_id": to,
            }

            if message_id:
                context["messageId"] = message_id
                context["message_id"] = message_id

            if error:
                context["error"] = error

            hook_event = create_internal_hook_event(
                "message",
                "sent",
                session_key,
                context
            )

            async def _trigger():
                await trigger_internal_hook(hook_event)

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(_trigger())
                else:
                    loop.run_until_complete(_trigger())
            except Exception:
                pass
        except Exception:
            pass

    async def send_text(self, target: str, text: str, reply_to: str | None = None, session_key: str | None = None) -> str:
        """Send text message with Markdown support"""
        if not self._app:
            raise RuntimeError("Telegram channel not started")

        success = False
        error_msg = None
        message_id = None

        try:
            # Parse target (chat_id)
            chat_id = int(target) if target.lstrip("-").isdigit() else target

            # Send message with Markdown parsing
            # Try Markdown first, fallback to plain text if parsing fails
            try:
                message = await self._app.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_to_message_id=int(reply_to) if reply_to else None,
                    parse_mode="Markdown"
                )
            except Exception as markdown_error:
                logger.debug(f"Markdown parsing failed, sending as plain text: {markdown_error}")
                # Fallback to plain text
                message = await self._app.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_to_message_id=int(reply_to) if reply_to else None
                )

            # Record sent message for reaction tracking
            record_sent_message(chat_id, message.message_id)

            message_id = str(message.message_id)
            success = True

            # Trigger message:sent hook
            self._fire_message_sent_hook(
                to=target,
                content=text,
                success=True,
                message_id=message_id,
                session_key=session_key,
            )

            return message_id

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to send Telegram message: {e}", exc_info=True)

            # Trigger message:sent hook for failure
            self._fire_message_sent_hook(
                to=target,
                content=text,
                success=False,
                error=error_msg,
                session_key=session_key,
            )

            raise

    async def send_photo(
        self,
        target: str | None = None,
        photo: Any = None,
        caption: str | None = None,
        reply_to: str | None = None,
        keyboard: Any = None,
        chat_id: str | None = None,
        **kwargs,
    ) -> Any:
        """Send photo message.

        Supports two calling styles:
        - Legacy: send_photo(target, photo, caption, ...)
        - API-style: send_photo(chat_id="...", photo="...", ...)
        """
        # New-style call: chat_id keyword provided (uses _make_api_call)
        if chat_id is not None:
            return await self._make_api_call(
                "sendPhoto", {"chat_id": chat_id, "photo": photo, **kwargs}
            )

        # Legacy style: requires a running bot application
        if not self._app:
            raise RuntimeError("Telegram channel not started")

        resolved_chat_id = int(target) if target and target.lstrip("-").isdigit() else target

        try:
            message = await self._app.bot.send_photo(
                chat_id=resolved_chat_id,
                photo=photo,
                caption=caption,
                parse_mode="Markdown" if caption else None,
                reply_to_message_id=int(reply_to) if reply_to else None,
                reply_markup=keyboard,
            )

            # Record sent message for reaction tracking
            record_sent_message(resolved_chat_id, message.message_id)

            return str(message.message_id)
        except Exception as e:
            logger.error(f"Failed to send photo: {e}")
            raise

    async def send_video(
        self, target: str, video, caption: str | None = None,
        reply_to: str | None = None, keyboard=None
    ) -> str:
        """Send video message"""
        if not self._app:
            raise RuntimeError("Telegram channel not started")

        chat_id = int(target) if target.lstrip("-").isdigit() else target

        try:
            message = await self._app.bot.send_video(
                chat_id=chat_id,
                video=video,
                caption=caption,
                parse_mode="Markdown" if caption else None,
                reply_to_message_id=int(reply_to) if reply_to else None,
                reply_markup=keyboard
            )

            # Record sent message for reaction tracking
            record_sent_message(chat_id, message.message_id)

            return str(message.message_id)
        except Exception as e:
            logger.error(f"Failed to send video: {e}")
            raise

    async def send_document(
        self, target: str, document, caption: str | None = None,
        reply_to: str | None = None, keyboard=None
    ) -> str:
        """Send document/file message"""
        if not self._app:
            raise RuntimeError("Telegram channel not started")

        chat_id = int(target) if target.lstrip("-").isdigit() else target

        try:
            message = await self._app.bot.send_document(
                chat_id=chat_id,
                document=document,
                caption=caption,
                parse_mode="Markdown" if caption else None,
                reply_to_message_id=int(reply_to) if reply_to else None,
                reply_markup=keyboard
            )

            # Record sent message for reaction tracking
            record_sent_message(chat_id, message.message_id)

            return str(message.message_id)
        except Exception as e:
            logger.error(f"Failed to send document: {e}")
            raise

    async def send_audio(
        self, target: str, audio, caption: str | None = None,
        reply_to: str | None = None
    ) -> str:
        """Send audio message"""
        if not self._app:
            raise RuntimeError("Telegram channel not started")

        chat_id = int(target) if target.lstrip("-").isdigit() else target

        try:
            message = await self._app.bot.send_audio(
                chat_id=chat_id,
                audio=audio,
                caption=caption,
                parse_mode="Markdown" if caption else None,
                reply_to_message_id=int(reply_to) if reply_to else None
            )

            # Record sent message for reaction tracking
            record_sent_message(chat_id, message.message_id)

            return str(message.message_id)
        except Exception as e:
            logger.error(f"Failed to send audio: {e}")
            raise

    async def send_location(
        self, target: str, latitude: float, longitude: float,
        reply_to: str | None = None
    ) -> str:
        """Send location message"""
        if not self._app:
            raise RuntimeError("Telegram channel not started")

        chat_id = int(target) if target.lstrip("-").isdigit() else target

        try:
            message = await self._app.bot.send_location(
                chat_id=chat_id,
                latitude=latitude,
                longitude=longitude,
                reply_to_message_id=int(reply_to) if reply_to else None
            )

            # Record sent message for reaction tracking
            record_sent_message(chat_id, message.message_id)

            return str(message.message_id)
        except Exception as e:
            logger.error(f"Failed to send location: {e}")
            raise

    async def send_poll(
        self, target: str, question: str, options: list[str],
        is_anonymous: bool = True, reply_to: str | None = None
    ) -> str:
        """Send poll message"""
        if not self._app:
            raise RuntimeError("Telegram channel not started")

        chat_id = int(target) if target.lstrip("-").isdigit() else target

        try:
            message = await self._app.bot.send_poll(
                chat_id=chat_id,
                question=question,
                options=options,
                is_anonymous=is_anonymous,
                reply_to_message_id=int(reply_to) if reply_to else None
            )

            # Record sent message for reaction tracking
            record_sent_message(chat_id, message.message_id)

            return str(message.message_id)
        except Exception as e:
            logger.error(f"Failed to send poll: {e}")
            raise

    async def send_dice(
        self, target: str, emoji: str = "🎲",
        reply_to: str | None = None
    ) -> str:
        """Send dice/animation message (🎲🎯🏀⚽🎳🎰)"""
        if not self._app:
            raise RuntimeError("Telegram channel not started")

        chat_id = int(target) if target.lstrip("-").isdigit() else target

        try:
            message = await self._app.bot.send_dice(
                chat_id=chat_id,
                emoji=emoji,
                reply_to_message_id=int(reply_to) if reply_to else None
            )

            # Record sent message for reaction tracking
            record_sent_message(chat_id, message.message_id)

            return str(message.message_id)
        except Exception as e:
            logger.error(f"Failed to send dice: {e}")
            raise

    async def send_media(
        self,
        target: str,
        media_url: str,
        media_type: str,
        caption: str | None = None,
        reply_to: str | None = None,
    ) -> str:
        """Send media message — mirrors TS delivery.ts deliverReplies().

        Supports: photo, video, animation (GIF), audio, voice, document.
        Caption longer than 1024 chars is split into a follow-up text message.
        Accepts both local file paths and HTTP URLs.
        """
        if not self._app:
            raise RuntimeError("Telegram channel not started")

        from pathlib import Path

        chat_id = int(target) if target.lstrip("-").isdigit() else target
        reply_id = int(reply_to) if reply_to else None

        # Caption splitting — Telegram limit is 1024 chars for media captions
        _CAPTION_LIMIT = 1024
        overflow_text: str | None = None
        if caption and len(caption) > _CAPTION_LIMIT:
            overflow_text = caption[_CAPTION_LIMIT:]
            caption = caption[:_CAPTION_LIMIT]

        # Telegram Bot API hard limit for uploads via the public API
        _TELEGRAM_MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB
        # Write timeout scales with file size: at least 60s, +1s per MB
        _BASE_WRITE_TIMEOUT = 60.0

        media_source = media_url
        is_local_file = False
        write_timeout = _BASE_WRITE_TIMEOUT

        # Detect local file (no URL scheme)
        if not media_url.startswith(("http://", "https://", "file://")):
            file_path = Path(media_url).expanduser()
            if file_path.exists() and file_path.is_file():
                file_size = file_path.stat().st_size
                if file_size > _TELEGRAM_MAX_UPLOAD_BYTES:
                    size_mb = file_size / (1024 * 1024)
                    raise ValueError(
                        f"File too large for Telegram Bot API ({size_mb:.1f} MB, limit 50 MB): {file_path.name}. "
                        "Consider compressing the file or sharing it via a URL."
                    )
                # Scale write timeout by file size (1 second per MB, min 60s)
                write_timeout = max(_BASE_WRITE_TIMEOUT, file_size / (1024 * 1024))
                media_source = open(file_path, "rb")  # noqa: WPS515 — closed in finally
                is_local_file = True
                logger.info("Sending local file: %s (%.1f MB)", file_path, file_size / (1024 * 1024))
            else:
                raise FileNotFoundError(
                    f"Media file not found: {media_url!r}. "
                    "Ensure the agent outputs an absolute path or that the file "
                    "is resolved against the session workspace before calling send_media."
                )

        try:
            if media_type == "photo":
                msg = await self._app.bot.send_photo(
                    chat_id=chat_id,
                    photo=media_source,
                    caption=caption,
                    parse_mode="Markdown" if caption else None,
                    reply_to_message_id=reply_id,
                    write_timeout=write_timeout,
                )
            elif media_type == "video":
                msg = await self._app.bot.send_video(
                    chat_id=chat_id,
                    video=media_source,
                    caption=caption,
                    parse_mode="Markdown" if caption else None,
                    reply_to_message_id=reply_id,
                    write_timeout=write_timeout,
                )
            elif media_type == "animation":
                msg = await self._app.bot.send_animation(
                    chat_id=chat_id,
                    animation=media_source,
                    caption=caption,
                    parse_mode="Markdown" if caption else None,
                    reply_to_message_id=reply_id,
                    write_timeout=write_timeout,
                )
            elif media_type == "voice":
                try:
                    msg = await self._app.bot.send_voice(
                        chat_id=chat_id,
                        voice=media_source,
                        caption=caption,
                        parse_mode="Markdown" if caption else None,
                        reply_to_message_id=reply_id,
                        write_timeout=write_timeout,
                    )
                except Exception as voice_err:
                    logger.warning("send_voice failed (%s), falling back to document", voice_err)
                    # Re-open if file was closed by failed send
                    if is_local_file:
                        file_path = Path(media_url).expanduser()
                        media_source = open(file_path, "rb")  # noqa: WPS515
                    msg = await self._app.bot.send_document(
                        chat_id=chat_id,
                        document=media_source,
                        caption=caption,
                        parse_mode="Markdown" if caption else None,
                        reply_to_message_id=reply_id,
                        write_timeout=write_timeout,
                    )
            elif media_type in ("audio",):
                msg = await self._app.bot.send_audio(
                    chat_id=chat_id,
                    audio=media_source,
                    caption=caption,
                    parse_mode="Markdown" if caption else None,
                    reply_to_message_id=reply_id,
                    write_timeout=write_timeout,
                )
            else:
                # Default: send as document (covers pptx, pdf, zip, etc.)
                msg = await self._app.bot.send_document(
                    chat_id=chat_id,
                    document=media_source,
                    caption=caption,
                    parse_mode="Markdown" if caption else None,
                    reply_to_message_id=reply_id,
                    write_timeout=write_timeout,
                )

            # Record sent message for reaction tracking
            record_sent_message(chat_id, msg.message_id)

            # Send overflow caption as a follow-up text message
            if overflow_text:
                overflow_msg = await self._app.bot.send_message(
                    chat_id=chat_id,
                    text=overflow_text,
                    parse_mode="Markdown",
                )
                # Record overflow message too
                record_sent_message(chat_id, overflow_msg.message_id)

            return str(msg.message_id)
        finally:
            if is_local_file and hasattr(media_source, "close"):
                media_source.close()

    def set_command_executor(self, session_manager, agent_runtime) -> None:
        """Set up command executor with session manager and agent runtime"""
        self._command_executor = ChatCommandExecutor(session_manager, agent_runtime)

    async def _handle_telegram_media(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle incoming media messages — mirrors TS bot-handlers.ts resolveMedia().

        Downloads the file from Telegram, encodes it as a base64 data URL, and
        passes it to the agent as a structured attachment (same shape as ChatAttachment
        in the TypeScript version) so the LLM can actually process the content.
        """
        if not update.message:
            return

        message = update.message

        # Deduplication — mirrors TS bot-updates.ts createTelegramUpdateDedupe
        dedup_key = message_key(message.chat_id, message.message_id)
        if self._dedupe.should_skip(dedup_key):
            logger.debug("Skipping duplicate media message %s", message.message_id)
            return

        # Media group handling (albums) - buffer multi-image messages
        media_group_id = getattr(message, "media_group_id", None)
        if media_group_id:
            await self._buffer_media_group(message, media_group_id, update, context)
            return

        chat = message.chat
        sender = message.from_user

        # Determine media type and collect file info
        media_type: str | None = None
        file_id: str | None = None
        file_name: str | None = None
        mime_type: str | None = None
        caption = message.caption or ""

        if message.photo:
            media_type = "photo"
            file_id = message.photo[-1].file_id
            file_name = f"photo_{message.message_id}.jpg"
            mime_type = "image/jpeg"
        elif message.video:
            media_type = "video"
            file_id = message.video.file_id
            file_name = message.video.file_name or f"video_{message.message_id}.mp4"
            mime_type = message.video.mime_type or "video/mp4"
        elif message.audio:
            media_type = "audio"
            file_id = message.audio.file_id
            file_name = message.audio.file_name or f"audio_{message.message_id}.mp3"
            mime_type = message.audio.mime_type or "audio/mpeg"
        elif message.voice:
            media_type = "voice"
            file_id = message.voice.file_id
            file_name = f"voice_{message.message_id}.ogg"
            mime_type = message.voice.mime_type or "audio/ogg"
        elif message.document:
            media_type = "document"
            file_id = message.document.file_id
            file_name = message.document.file_name or f"document_{message.message_id}"
            mime_type = message.document.mime_type or "application/octet-stream"
        elif message.sticker:
            # Skip animated/video stickers; accept static WebP only
            if not (message.sticker.is_animated or message.sticker.is_video):
                media_type = "photo"
                file_id = message.sticker.file_id
                file_name = f"sticker_{message.message_id}.webp"
                mime_type = "image/webp"

                # Store sticker metadata for potential caching
                sticker_metadata = {
                    "file_id": message.sticker.file_id,
                    "file_unique_id": message.sticker.file_unique_id,
                    "emoji": message.sticker.emoji,
                    "set_name": message.sticker.set_name,
                }

        if not file_id:
            logger.warning("No file_id found for media message %s", message.message_id)
            return

        # Persist update offset
        if update.update_id and self._account_id:
            write_telegram_update_offset(self._account_id, update.update_id)

        try:
            # Download file from Telegram and encode as base64 data URL
            # Mirrors TS delivery.ts resolveMedia() download logic
            tg_file = await context.bot.get_file(file_id)
            file_bytes = await tg_file.download_as_bytearray()
            file_size = len(file_bytes)

            import base64
            b64_content = base64.b64encode(bytes(file_bytes)).decode()

            # Determine attachment type bucket
            is_image = (mime_type or "").startswith("image/")
            is_audio = media_type in ("voice", "audio") or (mime_type or "").startswith("audio/")
            if is_image:
                attach_type = "image"
            elif is_audio:
                attach_type = media_type or "audio"  # "voice" or "audio"
            else:
                attach_type = "file"

            attachment: dict = {
                "type": attach_type,
                "mimeType": mime_type or "application/octet-stream",
                "content": b64_content,
                "filename": file_name,
                "size": file_size,
            }

            logger.info(
                "Received %s: %s (%d bytes) from user %s",
                media_type, file_name, file_size, sender.id,
            )

            # Cache sticker if this is a static sticker
            if message.sticker and "sticker_metadata" in locals():
                await self._cache_sticker_if_needed(
                    sticker_metadata=sticker_metadata,
                    file_bytes=bytes(file_bytes),
                    sender_username=sender.username,
                )

            # Determine chat type
            chat_type = "direct"
            if chat.type in ("group", "supergroup"):
                chat_type = "group"
            elif chat.type == "channel":
                chat_type = "channel"

            # Human-readable text description (fallback for models that don't handle attachments)
            text = caption if caption else f"[User sent a {media_type}: {file_name}]"

            inbound = InboundMessage(
                channel_id=self.id,
                message_id=str(message.message_id),
                sender_id=str(sender.id),
                sender_name=sender.full_name or sender.username or str(sender.id),
                chat_id=str(chat.id),
                chat_type=chat_type,
                text=text,
                timestamp=message.date.isoformat() if message.date else datetime.now(UTC).isoformat(),
                reply_to=str(message.reply_to_message.message_id) if message.reply_to_message else None,
                metadata={
                    "username": sender.username,
                    "chat_title": chat.title,
                    "chat_username": chat.username,
                    "media_type": media_type,
                    "file_id": file_id,
                    "file_name": file_name,
                    "mime_type": mime_type,
                    "caption": caption,
                },
                attachments=[attachment],
            )

            await self._handle_message(inbound)

        except Exception as e:
            logger.error("Error handling media message: %s", e, exc_info=True)
            try:
                await context.bot.send_message(
                    chat_id=chat.id,
                    text=f"Sorry, I had trouble processing that {media_type}.",
                    reply_to_message_id=message.message_id,
                )
            except Exception:
                pass

    async def _handle_telegram_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle incoming Telegram text message"""
        if not update.message or not update.message.text:
            return

        message = update.message

        # Deduplication — mirrors TS bot-updates.ts
        dedup_key = message_key(message.chat_id, message.message_id)
        if self._dedupe.should_skip(dedup_key):
            logger.debug("Skipping duplicate text message %s", message.message_id)
            return

        # Text fragment handling - buffer long messages split by Telegram
        text_fragment_id = self._detect_text_fragment(message)
        if text_fragment_id:
            await self._buffer_text_fragment(message, text_fragment_id, update, context)
            return

        # Persist update offset
        if update.update_id and self._account_id:
            write_telegram_update_offset(self._account_id, update.update_id)

        chat = message.chat
        sender = message.from_user

        # Determine chat type first
        is_group = chat.type in ["group", "supergroup"]
        is_dm = not is_group

        # DM Access Control - Check dm_policy for direct messages
        if is_dm and self._config:
            dm_policy = self._config.get("dmPolicy") or self._config.get("dm_policy") or "pairing"

            # Handle disabled DM
            if dm_policy == "disabled":
                logger.info(f"DM from {sender.id} blocked by dm_policy=disabled")
                return

            # Handle pairing and allowlist modes
            if dm_policy in ["pairing", "allowlist"]:
                # Check if sender is allowed
                is_allowed = await self._check_sender_allowed(
                    sender_id=str(sender.id),
                    username=sender.username,
                    dm_policy=dm_policy
                )

                if not is_allowed:
                    # For pairing mode, create pairing request
                    if dm_policy == "pairing":
                        await self._handle_pairing_request(sender, chat, context)
                    else:
                        # For allowlist mode, just ignore
                        logger.info(f"DM from {sender.id} blocked by dm_policy={dm_policy}")
                    return

        # Process as normal message
        await self._process_normal_text_message(message, update, context)

    async def _register_dynamic_command_handlers(self) -> None:
        """Register all native command handlers dynamically (mirrors TS bot-native-commands.ts:438-647)."""
        try:
            from openclaw.auto_reply.commands_registry_data import (
                list_native_command_specs_for_config,
            )
            from openclaw.auto_reply.skill_commands import list_skill_commands_for_agents
            from openclaw.channels.telegram.command_pipeline import handle_native_command
            from openclaw.channels.telegram.commands import (
                TELEGRAM_COMMAND_NAME_PATTERN,
                normalize_telegram_command_name,
            )

            # Get skill commands if enabled
            skill_commands = []
            try:
                skill_commands = list_skill_commands_for_agents(self._cfg)
                logger.info(f"Loaded {len(skill_commands)} skill commands for registration")
            except Exception as exc:
                logger.warning(f"Failed to load skill commands: {exc}")

            # Get all native commands from registry
            native_specs = list_native_command_specs_for_config(
                self._cfg,
                skill_commands,
                provider="telegram"
            )

            logger.info(f"Registering {len(native_specs)} native command handlers dynamically")

            # Register handler for each command
            registered_count = 0
            for spec in native_specs:
                name = spec.name or spec.native_name
                if not name:
                    continue

                normalized = normalize_telegram_command_name(name)
                if not TELEGRAM_COMMAND_NAME_PATTERN.match(normalized):
                    logger.warning(f"Skipping invalid command name: {normalized}")
                    continue

                # Create handler closure that captures the spec
                async def create_command_handler(command_spec):
                    async def command_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
                        await handle_native_command(
                            update=update,
                            context=ctx,
                            command_spec=command_spec,
                            bot=self._app.bot,
                            cfg=self._cfg,
                            account_id=self._account_id,
                            message_handler=self._message_handler,
                            channel_id=self.id,
                        )
                    return command_handler

                handler = await create_command_handler(spec)
                self._app.add_handler(CommandHandler(normalized, handler))
                registered_count += 1
                logger.debug(f"Registered command handler: /{normalized}")

            logger.info(f"Successfully registered {registered_count} command handlers")

        except Exception as exc:
            logger.error(f"Failed to register dynamic command handlers: {exc}")
            # Fallback to minimal hardcoded handlers
            logger.info("Falling back to hardcoded command handlers")
            self._app.add_handler(CommandHandler("start", self._handle_start_command))
            self._app.add_handler(CommandHandler("help", self._handle_help_command))
            self._app.add_handler(CommandHandler("model", self._handle_model_command))
            self._app.add_handler(CommandHandler("status", self._handle_status_command))

    async def _register_bot_commands(self):
        """Register bot commands with Telegram API using dynamic registration."""
        try:
            from openclaw.channels.telegram.command_handler import register_telegram_native_commands

            # Load the FULL openclaw config so skill commands (from agents.list)
            # and custom commands are included. self._config is only the telegram
            # channel sub-config (botToken, dmPolicy…), not the root config.
            try:
                from openclaw.config.loader import load_config
                full_cfg_obj = load_config()
                if full_cfg_obj and hasattr(full_cfg_obj, "model_dump"):
                    full_cfg: dict = full_cfg_obj.model_dump(by_alias=True, exclude_none=True)
                elif isinstance(full_cfg_obj, dict):
                    full_cfg = full_cfg_obj
                else:
                    full_cfg = self._config or {}
            except Exception:
                full_cfg = self._config or {}

            # Use dynamic registration from command registry
            await register_telegram_native_commands(
                bot=self._app.bot,
                cfg=full_cfg,
                account_id=self._account_id or "",
                native_enabled=True,
                native_skills_enabled=True,
            )
        except Exception as e:
            logger.error(f"Failed to register commands with Telegram API: {e}")

            # Fallback to minimal hardcoded commands
            try:
                from telegram import BotCommand

                minimal_commands = [
                    BotCommand("start", "Start using the bot"),
                    BotCommand("help", "View help information"),
                    BotCommand("status", "View status"),
                ]

                await self._app.bot.set_my_commands(minimal_commands)
                logger.info("Registered minimal fallback commands")
            except Exception as fallback_err:
                logger.error(f"Failed to register fallback commands: {fallback_err}")

    async def _setup_menu_button(self):
        """Setup bot menu button"""
        try:
            # Set menu button (shows in bottom left of chat)
            logger.info("Menu button setup completed")
        except Exception as e:
            logger.debug(f"Menu button setup failed: {e}")

    def _get_quick_reply_keyboard(self):
        """Get quick reply keyboard with common commands"""
        keyboard = [
            [KeyboardButton("💬 New Chat"), KeyboardButton("📊 Status")],
            [KeyboardButton("❓ Help"), KeyboardButton("🤖 Switch Model")],
        ]
        return ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=False
        )

    async def _handle_start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        welcome_message = (
            "👋 *Welcome to OpenClaw AI Assistant!*\n\n"
            "I am a powerful AI assistant that can help you:\n"
            "• 💬 Intelligent conversation\n"
            "• 📝 Process documents and files\n"
            "• 🔍 Search and query information\n"
            "• 🛠️ Execute various tasks\n\n"
            "Send any message to start a conversation, or use /help to see more commands."
        )

        # Send welcome message with quick reply keyboard
        await update.message.reply_text(
            welcome_message,
            parse_mode="Markdown",
            reply_markup=self._get_quick_reply_keyboard()
        )

    async def _handle_help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_message = (
            "📋 *Available Commands*\n\n"
            "/start - Show welcome message\n"
            "/help - Show this help information\n"
            "/new - Start new conversation (clear history)\n"
            "/status - View bot status\n"
            "/model - Switch AI model\n\n"
            "*💡 Tips*\n"
            "• Send messages directly to start conversation\n"
            "• Supports images, files, etc.\n"
            "• Multi-turn conversation supported\n\n"
            "_Need help? Visit documentation or contact support team._"
        )

        await update.message.reply_text(
            help_message,
            parse_mode="Markdown"
        )

    async def _handle_new_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /new command - start new conversation"""
        user_id = update.effective_user.id

        # Create inline keyboard for confirmation
        keyboard = [
            [
                InlineKeyboardButton("✅ Confirm", callback_data="new_confirm"),
                InlineKeyboardButton("❌ Cancel", callback_data="new_cancel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "🆕 *Start New Conversation*\n\n"
            "This will clear the current conversation history.\n"
            "Are you sure you want to continue?",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

    async def _handle_reset_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /reset command - reset session (clear transcript)"""
        try:
            # Build session key from chat info
            chat_id = update.effective_chat.id
            chat_type = update.effective_chat.type

            # Construct session key matching gateway format
            # Format: {channel}:{account_id}:{scope}:{id}
            if chat_type == "private":
                session_key = f"telegram:{self.id}:dm:main:{chat_id}"
            else:
                session_key = f"telegram:{self.id}:group:{chat_id}"

            logger.info(f"[{self.id}] Reset requested for session: {session_key}")

            # Call gateway sessions.reset method
            try:
                from openclaw.gateway.api.sessions_methods import SessionsResetMethod

                reset_method = SessionsResetMethod()
                result = await reset_method.execute(
                    connection=None,
                    params={
                        "key": session_key,
                        "archiveTranscript": True  # Archive old transcript
                    }
                )

                if result.get("ok"):
                    new_session_id = result.get("sessionId", "unknown")
                    message = (
                        "✅ **Conversation Reset**\n\n"
                        "Your conversation history has been cleared!\n"
                        f"🆔 New session: `{new_session_id[:8]}...`\n\n"
                        "We can start fresh now! 🎉"
                    )
                    logger.info(f"[{self.id}] Session reset successful: {new_session_id}")
                else:
                    message = "⚠️ **Reset Partial**\n\nSession was reset, but something went wrong."
                    logger.warning(f"[{self.id}] Session reset returned non-ok result")

            except Exception as reset_err:
                logger.error(f"[{self.id}] Failed to reset session via API: {reset_err}")
                message = (
                    "⚠️ **Reset Failed**\n\n"
                    "Unable to reset session. Please try again or contact support.\n"
                    f"Error: `{str(reset_err)[:100]}`"
                )

            await update.message.reply_text(message, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"[{self.id}] Error handling reset command: {e}")
            await update.message.reply_text(
                "❌ **Error**\n\nFailed to process reset command.",
                parse_mode="Markdown"
            )

    async def _handle_status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        # Get current model from config
        current_model = self._config.get("model", "google/gemini-3-pro-preview") if self._config else "unknown"

        status_message = (
            "📊 *Bot Status*\n\n"
            f"🤖 Current Model: `{current_model}`\n"
            f"✅ Status: Running\n"
            f"💬 Session: Active\n"
            f"📡 Connection: Normal\n\n"
            "_System running normally_"
        )

        await update.message.reply_text(
            status_message,
            parse_mode="Markdown"
        )

    async def _handle_model_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /model command - show model selection"""
        current_model = self._config.get("model", "google/gemini-3-pro-preview") if self._config else "unknown"

        keyboard = [
            [InlineKeyboardButton("🌟 Gemini Pro (Current)", callback_data="model_gemini")],
            [InlineKeyboardButton("🧠 Claude Sonnet", callback_data="model_claude")],
            [InlineKeyboardButton("⚡ GPT-4", callback_data="model_gpt4")],
            [InlineKeyboardButton("🔥 GPT-4 Turbo", callback_data="model_gpt4turbo")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"🤖 *Select AI Model*\n\n"
            f"Current Model: `{current_model}`\n\n"
            f"Choose the model to use:",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

    async def _handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries from inline keyboards"""
        from telegram.error import BadRequest

        query = update.callback_query
        await query.answer()

        data = query.data
        logger.info(f"Callback query: {data}")

        if data == "new_confirm":
            # Clear conversation history (implement this in session manager)
            try:
                await query.edit_message_text(
                    "✅ *New Conversation Started*\n\n"
                    "Conversation history cleared. Send a message to start a new conversation!",
                    parse_mode="Markdown"
                )
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    # Message content is identical, silently ignore
                    logger.debug(f"Message already shows correct state for {data}")
                else:
                    raise

        elif data == "new_cancel":
            try:
                await query.edit_message_text(
                    "❌ *Cancelled*\n\nContinuing current conversation.",
                    parse_mode="Markdown"
                )
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    logger.debug(f"Message already shows correct state for {data}")
                else:
                    raise

        elif data.startswith("model_"):
            model_name = data.replace("model_", "")
            model_map = {
                "gemini": ("google/gemini-3-pro-preview", "Gemini Pro"),
                "claude": ("claude-3-5-sonnet-20241022", "Claude 3.5 Sonnet"),
                "gpt4": ("gpt-4", "GPT-4"),
                "gpt4turbo": ("gpt-4-turbo", "GPT-4 Turbo"),
            }

            if model_name in model_map:
                model_id, display_name = model_map[model_name]
                # Update config (this would need to be persisted)
                if self._config:
                    self._config["model"] = model_id

                try:
                    await query.edit_message_text(
                        f"✅ *Model Switched*\n\n"
                        f"Now using: {display_name}\n"
                        f"Model ID: `{model_id}`\n\n"
                        f"_New messages will use this model_",
                        parse_mode="Markdown"
                    )
                except BadRequest as e:
                    if "Message is not modified" in str(e):
                        logger.debug(f"Message already shows correct state for model {model_name}")
                    else:
                        raise

    async def _check_sender_allowed(
        self,
        sender_id: str,
        username: str | None,
        dm_policy: str
    ) -> bool:
        """Check if sender is allowed based on dm_policy and allowFrom.
        
        Args:
            sender_id: Telegram user ID
            username: Telegram username (without @)
            dm_policy: DM policy (pairing, allowlist, open)
            
        Returns:
            True if sender is allowed
        """
        # For open policy with wildcard, allow all
        if dm_policy == "open":
            allow_from = self._config.get("allowFrom") or self._config.get("allow_from") or []
            if "*" in allow_from:
                return True

        # Get allowFrom from config
        allow_from_config = self._config.get("allowFrom") or self._config.get("allow_from") or []

        # Get allowFrom from pairing store
        try:
            from ...pairing.pairing_store import read_channel_allow_from_store
            # Pass account_id to read both account-scoped and legacy allowFrom lists
            allow_from_store = read_channel_allow_from_store("telegram", self._account_id)
        except Exception as e:
            logger.warning(f"Failed to read pairing store: {e}")
            allow_from_store = []

        # Merge both lists
        effective_allow_from = list(set(allow_from_config + allow_from_store))

        # Check wildcard
        if "*" in effective_allow_from:
            return True

        # Check if empty and not in pairing mode
        if not effective_allow_from and dm_policy == "allowlist":
            return False

        # Check sender ID match
        if sender_id in effective_allow_from:
            return True

        # Check username match (case-insensitive)
        if username:
            username_lower = username.lower()
            username_with_at = f"@{username_lower}"

            for allowed in effective_allow_from:
                allowed_lower = allowed.lower()
                if allowed_lower == username_lower or allowed_lower == username_with_at:
                    return True

        return False

    async def _handle_pairing_request(
        self,
        sender: Any,
        chat: Any,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle pairing request for unauthorized DM.
        
        Args:
            sender: Telegram User object
            chat: Telegram Chat object
            context: Telegram context
        """
        try:
            from ...pairing.messages import format_pairing_request_message
            from ...pairing.pairing_store import upsert_channel_pairing_request

            # Create or update pairing request (with account_id for multi-account support)
            result = upsert_channel_pairing_request(
                channel="telegram",
                sender_id=str(sender.id),
                account_id=self._account_id,
                meta={
                    "username": sender.username or "",
                    "first_name": sender.first_name or "",
                    "last_name": sender.last_name or "",
                    "full_name": sender.full_name or "",
                }
            )

            pairing_code = result["code"]
            is_new_request = result["created"]

            # Only send message for new requests
            if is_new_request:
                logger.info(f"Created pairing request for telegram:{sender.id}, code={pairing_code}")

                # Format pairing message
                message_text = format_pairing_request_message(
                    code=pairing_code,
                    channel="telegram",
                    id_label=f"Telegram ID ({sender.id})"
                )

                # Add user info
                user_info = "\n📱 **Your Info**\n"
                user_info += f"- Telegram ID: `{sender.id}`\n"
                if sender.username:
                    user_info += f"- Username: @{sender.username}\n"
                user_info += f"- Name: {sender.full_name}\n"

                message_text = message_text.replace(
                    "This code expires in 1 hour.",
                    user_info + "\nThis code expires in 1 hour."
                )

                # Send to user
                await context.bot.send_message(
                    chat_id=chat.id,
                    text=message_text,
                    parse_mode="Markdown"
                )
            else:
                logger.debug(f"Pairing request already exists for telegram:{sender.id}")

        except Exception as e:
            logger.error(f"Failed to handle pairing request: {e}", exc_info=True)
            await context.bot.send_message(
                chat_id=chat.id,
                text="⚠️ Access not configured. Please contact the bot owner.",
            )

    async def _cache_sticker_if_needed(
        self,
        sticker_metadata: dict[str, Any],
        file_bytes: bytes,
        sender_username: str | None,
    ) -> None:
        """
        Cache a sticker with vision-based description.
        
        Args:
            sticker_metadata: Sticker metadata from Telegram
            file_bytes: Downloaded sticker file bytes
            sender_username: Username of sender (for receivedFrom)
        """
        file_unique_id = sticker_metadata.get("file_unique_id")
        if not file_unique_id:
            return

        # Check if already cached
        existing = get_cached_sticker(file_unique_id)
        if existing:
            logger.debug("Sticker %s already cached", file_unique_id)
            return

        try:
            import tempfile

            # Save to temp file for vision analysis
            with tempfile.NamedTemporaryFile(suffix=".webp", delete=False) as tmp:
                tmp.write(file_bytes)
                temp_path = tmp.name

            # Describe sticker using vision API
            description = await describe_sticker_image(
                image_path=temp_path,
                config=self._config,
                agent_id=None,
            )

            # Clean up temp file
            import os
            try:
                os.unlink(temp_path)
            except Exception:
                pass

            if not description:
                description = "Sticker"

            # Cache the sticker
            cached = CachedSticker(
                file_id=sticker_metadata.get("file_id", ""),
                file_unique_id=file_unique_id,
                emoji=sticker_metadata.get("emoji"),
                set_name=sticker_metadata.get("set_name"),
                description=description,
                cached_at=datetime.now(UTC).isoformat(),
                received_from=sender_username,
            )

            cache_sticker(cached)
            logger.info("Cached sticker %s: %s", file_unique_id, description)

        except Exception as exc:
            logger.warning("Failed to cache sticker: %s", exc)

    async def _handle_reaction_update(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle incoming message reaction updates"""
        if not update.message_reaction:
            return

        reaction = update.message_reaction
        chat = reaction.chat
        message_id = reaction.message_id
        user = reaction.user

        # Resolve reaction notification mode (default: "own")
        reaction_mode = (
            self._config.get("reactionNotifications")
            or self._config.get("reaction_notifications")
            or "own"
        )

        if reaction_mode == "off":
            return

        if user and user.is_bot:
            return

        # Filter based on mode
        if reaction_mode == "own" and not was_sent_by_bot(chat.id, message_id):
            return

        # Detect added reactions (compare old vs new)
        old_emojis = set()
        if reaction.old_reaction:
            for r in reaction.old_reaction:
                if hasattr(r, "type") and r.type == "emoji" and hasattr(r, "emoji"):
                    old_emojis.add(r.emoji)

        added_reactions = []
        if reaction.new_reaction:
            for r in reaction.new_reaction:
                if hasattr(r, "type") and r.type == "emoji" and hasattr(r, "emoji"):
                    if r.emoji not in old_emojis:
                        added_reactions.append(r.emoji)

        if not added_reactions:
            return

        # Build sender label
        sender_label = "unknown"
        if user:
            name_parts = [user.first_name or "", user.last_name or ""]
            sender_name = " ".join(p for p in name_parts if p).strip()
            sender_username = f"@{user.username}" if user.username else None

            if sender_name and sender_username:
                sender_label = f"{sender_name} ({sender_username})"
            elif sender_name:
                sender_label = sender_name
            elif sender_username:
                sender_label = sender_username
            elif user.id:
                sender_label = f"id:{user.id}"

        # Determine session routing
        is_group = chat.type in ["group", "supergroup"]
        is_forum = getattr(chat, "is_forum", False)

        # Build session key for reaction (chat-level, no thread ID available)
        if is_group:
            # For groups, route to chat-level session
            session_key = f"agent:main:telegram:group:{chat.id}"
        else:
            # For DMs
            session_key = f"agent:main:telegram:{chat.id}"

        # Enqueue system event for each added reaction
        for emoji in added_reactions:
            text = f"Telegram reaction added: {emoji} by {sender_label} on msg {message_id}"

            # Create system event
            try:
                if self._message_handler:
                    inbound = InboundMessage(
                        channel_id=self.id,
                        message_id=str(message_id),
                        sender_id=str(user.id) if user else "unknown",
                        sender_name=sender_label,
                        chat_id=str(chat.id),
                        chat_type="group" if is_group else "direct",
                        text=text,
                        timestamp=datetime.now(UTC).isoformat(),
                        metadata={
                            "event_type": "reaction",
                            "emoji": emoji,
                            "username": user.username if user else None,
                            "chat_title": chat.title if hasattr(chat, "title") else None,
                            "session_key": session_key,
                        },
                    )

                    await self._message_handler(inbound)
                    logger.debug("Reaction event enqueued: %s", text)

            except Exception as exc:
                logger.error("Failed to handle reaction event: %s", exc, exc_info=True)

    async def _buffer_media_group(
        self,
        message: Any,
        media_group_id: str,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """
        Buffer messages from a media group (album).
        
        Combines multiple media messages with same media_group_id into a single
        InboundMessage with multiple attachments.
        
        Args:
            message: Telegram Message object
            media_group_id: Media group ID
            update: Telegram Update object
            context: Telegram context
        """
        MEDIA_GROUP_TIMEOUT_MS = 500

        # Get or create buffer entry
        if media_group_id in self._media_group_buffer:
            entry = self._media_group_buffer[media_group_id]

            # Cancel existing timer
            if "timer" in entry:
                entry["timer"].cancel()

            # Add message to buffer
            entry["messages"].append({
                "message": message,
                "update": update,
                "context": context,
            })
        else:
            entry = {
                "messages": [{
                    "message": message,
                    "update": update,
                    "context": context,
                }],
            }
            self._media_group_buffer[media_group_id] = entry

        # Schedule flush
        async def flush_group():
            await asyncio.sleep(MEDIA_GROUP_TIMEOUT_MS / 1000)
            if media_group_id in self._media_group_buffer:
                buffered = self._media_group_buffer.pop(media_group_id)
                await self._process_media_group(buffered)

        entry["timer"] = asyncio.create_task(flush_group())

    async def _process_media_group(self, entry: dict) -> None:
        """
        Process a buffered media group.
        
        Downloads all media, combines captions, and sends as single InboundMessage
        with multiple attachments.
        
        Args:
            entry: Media group buffer entry
        """
        try:
            messages = entry["messages"]
            if not messages:
                return

            # Sort by message_id
            messages.sort(key=lambda m: m["message"].message_id)

            # Find message with caption (prefer first one with caption)
            caption_msg = next(
                (m for m in messages if m["message"].caption or m["message"].text),
                messages[0]
            )

            primary_message = caption_msg["message"]
            primary_context = caption_msg["context"]

            chat = primary_message.chat
            sender = primary_message.from_user

            # Download all media
            attachments = []
            for msg_entry in messages:
                msg = msg_entry["message"]
                ctx = msg_entry["context"]

                # Determine media type and file info
                file_id = None
                file_name = None
                mime_type = None

                if msg.photo:
                    file_id = msg.photo[-1].file_id
                    file_name = f"photo_{msg.message_id}.jpg"
                    mime_type = "image/jpeg"
                elif msg.video:
                    file_id = msg.video.file_id
                    file_name = msg.video.file_name or f"video_{msg.message_id}.mp4"
                    mime_type = msg.video.mime_type or "video/mp4"
                elif msg.document:
                    file_id = msg.document.file_id
                    file_name = msg.document.file_name or f"document_{msg.message_id}"
                    mime_type = msg.document.mime_type or "application/octet-stream"

                if not file_id:
                    continue

                try:
                    # Download file
                    tg_file = await ctx.bot.get_file(file_id)
                    file_bytes = await tg_file.download_as_bytearray()
                    file_size = len(file_bytes)

                    import base64
                    b64_content = base64.b64encode(bytes(file_bytes)).decode()

                    # Determine attachment type
                    is_image = (mime_type or "").startswith("image/")
                    attach_type = "image" if is_image else "file"

                    attachment = {
                        "type": attach_type,
                        "mimeType": mime_type or "application/octet-stream",
                        "content": b64_content,
                        "filename": file_name,
                        "size": file_size,
                    }

                    attachments.append(attachment)

                except Exception as exc:
                    logger.warning("Failed to download media from group: %s", exc)

            if not attachments:
                logger.warning("No attachments in media group")
                return

            # Combine captions from all messages
            captions = [
                m["message"].caption or m["message"].text
                for m in messages
                if m["message"].caption or m["message"].text
            ]
            combined_caption = "\n".join(c for c in captions if c)

            # Determine chat type
            chat_type = "direct"
            if chat.type in ("group", "supergroup"):
                chat_type = "group"
            elif chat.type == "channel":
                chat_type = "channel"

            # Human-readable text description
            text = combined_caption if combined_caption else f"[User sent {len(attachments)} media items]"

            # Build InboundMessage
            inbound = InboundMessage(
                channel_id=self.id,
                message_id=str(primary_message.message_id),
                sender_id=str(sender.id),
                sender_name=sender.full_name or sender.username or str(sender.id),
                chat_id=str(chat.id),
                chat_type=chat_type,
                text=text,
                timestamp=primary_message.date.isoformat() if primary_message.date else datetime.now(UTC).isoformat(),
                reply_to=str(primary_message.reply_to_message.message_id) if primary_message.reply_to_message else None,
                metadata={
                    "username": sender.username,
                    "chat_title": chat.title,
                    "chat_username": chat.username,
                    "media_type": "album",
                    "caption": combined_caption,
                    "media_count": len(attachments),
                },
                attachments=attachments,
            )

            await self._handle_message(inbound)

        except Exception as exc:
            logger.error("Error processing media group: %s", exc, exc_info=True)

    def _detect_text_fragment(self, message: Any) -> str | None:
        """
        Detect if message is part of a split text fragment.
        
        Telegram splits messages >4096 chars. We detect fragments by checking:
        - Message length is near 4096 char limit
        - Sender/chat match previous fragment
        - Time delta is < 2s from last fragment
        
        Returns:
            Fragment ID (sender_chat composite) or None
        """
        TEXT_FRAGMENT_MIN_LENGTH = 3900

        if not message.text:
            return None

        # Only buffer messages close to the limit
        if len(message.text) < TEXT_FRAGMENT_MIN_LENGTH:
            return None

        # Generate fragment key (sender + chat)
        sender_id = message.from_user.id if message.from_user else None
        if not sender_id:
            return None

        return f"{message.chat_id}:{sender_id}"

    async def _buffer_text_fragment(
        self,
        message: Any,
        fragment_id: str,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """
        Buffer text fragments from split messages.
        
        Combines consecutive messages from same sender that are split by Telegram.
        
        Args:
            message: Telegram Message object
            fragment_id: Fragment buffer key
            update: Telegram Update object
            context: Telegram context
        """
        TEXT_FRAGMENT_TIMEOUT_MS = 2000

        # Get or create buffer entry
        if fragment_id in self._text_fragment_buffer:
            entry = self._text_fragment_buffer[fragment_id]

            # Cancel existing timer
            if "timer" in entry:
                entry["timer"].cancel()

            # Add message to buffer
            entry["messages"].append({
                "message": message,
                "update": update,
                "context": context,
            })
        else:
            entry = {
                "messages": [{
                    "message": message,
                    "update": update,
                    "context": context,
                }],
            }
            self._text_fragment_buffer[fragment_id] = entry

        # Schedule flush
        async def flush_fragments():
            await asyncio.sleep(TEXT_FRAGMENT_TIMEOUT_MS / 1000)
            if fragment_id in self._text_fragment_buffer:
                buffered = self._text_fragment_buffer.pop(fragment_id)
                await self._process_text_fragments(buffered)

        entry["timer"] = asyncio.create_task(flush_fragments())

    async def _process_text_fragments(self, entry: dict) -> None:
        """
        Process buffered text fragments.
        
        Combines consecutive split messages into a single InboundMessage.
        
        Args:
            entry: Text fragment buffer entry
        """
        try:
            messages = entry["messages"]
            if not messages:
                return

            # Sort by message_id
            messages.sort(key=lambda m: m["message"].message_id)

            # Combine all text
            combined_text = "".join(m["message"].text or "" for m in messages)

            # Use first message as primary
            primary_message = messages[0]["message"]
            primary_update = messages[0]["update"]
            primary_context = messages[0]["context"]

            # Create new Update with combined text for normal processing
            # We'll modify the message text temporarily
            original_text = primary_message.text
            primary_message.text = combined_text

            try:
                # Now process as normal text message (skip fragment detection)
                await self._process_normal_text_message(
                    primary_message,
                    primary_update,
                    primary_context,
                )
            finally:
                primary_message.text = original_text

        except Exception as exc:
            logger.error("Error processing text fragments: %s", exc, exc_info=True)

    async def _process_normal_text_message(
        self,
        message: Any,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """
        Process a normal text message (non-fragment).
        
        This is the core text message handling logic extracted from _handle_telegram_message.
        """
        # Persist update offset
        if update.update_id and self._account_id:
            write_telegram_update_offset(self._account_id, update.update_id)

        chat = message.chat
        sender = message.from_user

        # Determine chat type first
        is_group = chat.type in ["group", "supergroup"]
        is_dm = not is_group

        # DM Access Control - Check dm_policy for direct messages
        if is_dm and self._config:
            dm_policy = self._config.get("dmPolicy") or self._config.get("dm_policy") or "pairing"

            # Handle disabled DM
            if dm_policy == "disabled":
                logger.info(f"DM from {sender.id} blocked by dm_policy=disabled")
                return

            # Handle pairing and allowlist modes
            if dm_policy in ["pairing", "allowlist"]:
                # Check if sender is allowed
                is_allowed = await self._check_sender_allowed(
                    sender_id=str(sender.id),
                    username=sender.username,
                    dm_policy=dm_policy
                )

                if not is_allowed:
                    # For pairing mode, create pairing request
                    if dm_policy == "pairing":
                        await self._handle_pairing_request(sender, chat, context)
                    else:
                        # For allowlist mode, just ignore
                        logger.info(f"DM from {sender.id} blocked by dm_policy={dm_policy}")
                    return

        # Check for chat commands
        if self._command_parser:
            command = self._command_parser.parse(message.text)
            if command and self._command_executor:
                session_id = f"telegram:{chat.id}"
                user_id = str(sender.id)
                is_owner = self._owner_id and user_id == self._owner_id
                try:
                    await self._command_executor.execute(
                        command=command,
                        session_id=session_id,
                        is_owner=is_owner,
                        channel=self,
                        context={"chat_id": chat.id}
                    )
                except Exception as cmd_exc:
                    logger.error(
                        "Failed to execute command %s: %s",
                        command.command,
                        cmd_exc,
                        exc_info=True
                    )
                return

        # Normal message processing
        chat_type = "direct"
        if chat.type in ("group", "supergroup"):
            chat_type = "group"
        elif chat.type == "channel":
            chat_type = "channel"

        inbound = InboundMessage(
            channel_id=self.id,
            message_id=str(message.message_id),
            sender_id=str(sender.id),
            sender_name=sender.full_name or sender.username or str(sender.id),
            chat_id=str(chat.id),
            chat_type=chat_type,
            text=message.text,
            timestamp=message.date.isoformat() if message.date else datetime.now(UTC).isoformat(),
            reply_to=str(message.reply_to_message.message_id) if message.reply_to_message else None,
            metadata={
                "username": sender.username,
                "chat_title": chat.title,
                "chat_username": chat.username,
            },
        )

        await self._handle_message(inbound)
