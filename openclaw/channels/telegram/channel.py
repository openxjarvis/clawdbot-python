"""Telegram channel implementation"""
from __future__ import annotations


import asyncio
import logging
from datetime import UTC, datetime, timezone
from typing import Any, Optional

from telegram import Update, BotCommand, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, ContextTypes, MessageHandler, CommandHandler, CallbackQueryHandler, filters

from ..chat_commands import ChatCommandExecutor, ChatCommandParser
from ..base import ChannelCapabilities, ChannelPlugin, InboundMessage
from .command_handler import TelegramCommandHandler
from .commands import list_native_commands, register_commands_with_telegram
from .i18n_support import register_lang_handlers
from .commands_extended import register_extended_commands
from .update_offset_store import (
    read_telegram_update_offset,
    write_telegram_update_offset,
)
from .update_dedupe import TelegramUpdateDedupe, update_key, message_key, callback_key

logger = logging.getLogger(__name__)

# Exponential backoff config for Conflict errors — mirrors TS monitor.ts
_CONFLICT_BACKOFF_INITIAL = 2.0   # seconds
_CONFLICT_BACKOFF_MAX = 30.0      # seconds
_CONFLICT_BACKOFF_FACTOR = 1.8
_CONFLICT_MAX_RETRY_TIME = 5 * 60 # 5 minutes total


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
        )
        self._app: Application | None = None
        self._bot_token: str | None = None
        self._command_parser: Optional[ChatCommandParser] = None
        self._command_executor: Optional[ChatCommandExecutor] = None
        self._owner_id: Optional[str] = None
        self._command_handler: Optional[TelegramCommandHandler] = None
        self._config: Optional[dict] = None
        self._account_id: Optional[str] = None
        self._dedupe = TelegramUpdateDedupe()
        self._conflict_backoff = _CONFLICT_BACKOFF_INITIAL
        self._conflict_retry_task: Optional[asyncio.Task] = None

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

        logger.info("Starting Telegram channel...")

        # Initialize chat command system
        self._command_parser = ChatCommandParser()
        # Note: command_executor will be initialized once we have session_manager
        # This would typically be set via set_message_handler or similar

        # Create application
        self._app = Application.builder().token(self._bot_token).build()

        # Add command handlers
        self._app.add_handler(CommandHandler("start", self._handle_start_command))
        self._app.add_handler(CommandHandler("help", self._handle_help_command))
        self._app.add_handler(CommandHandler("new", self._handle_new_command))
        self._app.add_handler(CommandHandler("reset", self._handle_reset_command))
        self._app.add_handler(CommandHandler("status", self._handle_status_command))
        self._app.add_handler(CommandHandler("model", self._handle_model_command))
        
        # Register i18n language switching handlers
        register_lang_handlers(self._app)
        
        # Register extended commands
        register_extended_commands(self._app)
        
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

        # Start bot
        await self._app.initialize()
        await self._app.start()
        
        # Get bot info after initialization
        bot_info = await self._app.bot.get_me()
        account_id = str(bot_info.id)
        logger.info(f"Bot initialized: @{bot_info.username} (ID: {account_id})")
        
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
        self._command_handler = TelegramCommandHandler(cmd_config, account_id, None)

        # Register conflict/error handler for update-processing errors
        # (Updater polling errors are handled via error_callback in start_polling below)
        self._app.add_error_handler(self._handle_polling_error)

        # Delete any existing webhook and clear pending updates to avoid conflicts
        # This ensures clean state when switching from webhook to polling mode
        await self._app.bot.delete_webhook(drop_pending_updates=True)
        logger.info("Cleared webhook and pending updates")

        # Register bot commands with Telegram
        await self._register_bot_commands()

        # Set bot menu button (optional)
        await self._setup_menu_button()

        # Restore persisted update offset so we don't reprocess old updates
        saved_offset = read_telegram_update_offset(account_id)
        if saved_offset is not None:
            logger.info("Resuming from persisted update offset %d", saved_offset)

        def _polling_error_cb(exc: Exception) -> None:
            """Sync callback for Updater network_retry_loop errors — mirrors TS monitor.ts.

            Called by PTB's internal polling loop on every TelegramError.
            For Conflict (409) errors we schedule an async restart with backoff.
            """
            import telegram.error as tg_err
            if isinstance(exc, tg_err.Conflict):
                logger.warning(
                    "Telegram Conflict (another bot instance is polling) — "
                    "scheduling restart in %.1fs",
                    self._conflict_backoff,
                )
                asyncio.get_event_loop().create_task(
                    self._restart_polling_after_conflict()
                )
            elif isinstance(exc, tg_err.NetworkError):
                logger.warning("Telegram network error (will auto-retry): %s", exc)
            elif isinstance(exc, tg_err.TimedOut):
                logger.debug("Telegram getUpdates timed out (will retry): %s", exc)
            else:
                logger.error("Telegram polling error: %s", exc)

        await self._app.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=False,  # We already dropped via delete_webhook
            error_callback=_polling_error_cb,
        )

        self._running = True
        self._conflict_backoff = _CONFLICT_BACKOFF_INITIAL
        logger.info("Telegram channel started")

    async def stop(self) -> None:
        """Stop Telegram bot"""
        if self._conflict_retry_task and not self._conflict_retry_task.done():
            self._conflict_retry_task.cancel()
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
        """PTB global error handler — mirrors TS monitor.ts conflict detection.

        On a 409 Conflict (another getUpdates call is active), we stop polling
        and schedule a restart with exponential backoff so we don't hammer the
        API or block indefinitely.
        """
        import telegram.error as tg_err

        exc = context.error
        if exc is None:
            return

        if isinstance(exc, tg_err.Conflict):
            logger.warning(
                "Telegram Conflict (another bot instance is polling): %s — "
                "retrying in %.1fs (backoff)",
                exc,
                self._conflict_backoff,
            )
            # Schedule the restart; don't await here to avoid blocking PTB internals
            self._conflict_retry_task = asyncio.create_task(
                self._restart_polling_after_conflict()
            )
        elif isinstance(exc, tg_err.NetworkError):
            logger.warning("Telegram network error (will auto-retry): %s", exc)
        elif isinstance(exc, tg_err.TimedOut):
            logger.debug("Telegram request timed out (will auto-retry): %s", exc)
        else:
            logger.error("Unhandled Telegram error: %s", exc, exc_info=exc)

    async def _restart_polling_after_conflict(self) -> None:
        """Stop polling, wait with exponential backoff, then resume."""
        wait = self._conflict_backoff
        # Increase backoff for the next conflict (capped)
        self._conflict_backoff = min(
            self._conflict_backoff * _CONFLICT_BACKOFF_FACTOR,
            _CONFLICT_BACKOFF_MAX,
        )
        logger.info("Pausing polling for %.1fs before restart", wait)
        await asyncio.sleep(wait)

        if not self._running or self._app is None:
            return

        try:
            await self._app.updater.stop()
        except Exception as exc:
            logger.debug("Updater stop during conflict recovery: %s", exc)

        try:
            await self._app.updater.start_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=False,
            )
            # Reset backoff on successful restart
            self._conflict_backoff = _CONFLICT_BACKOFF_INITIAL
            logger.info("Polling restarted after conflict backoff")
        except Exception as exc:
            logger.error("Failed to restart polling: %s", exc)
            # Schedule another retry
            self._conflict_retry_task = asyncio.create_task(
                self._restart_polling_after_conflict()
            )

    async def send_typing(self, target: str) -> None:
        """Send a 'typing…' chat action to show the bot is processing."""
        if not self._app:
            return
        try:
            chat_id = int(target) if str(target).lstrip("-").isdigit() else target
            await self._app.bot.send_chat_action(chat_id=chat_id, action="typing")
        except Exception as exc:
            logger.debug("send_typing failed for %s: %s", target, exc)

    async def send_text(self, target: str, text: str, reply_to: str | None = None) -> str:
        """Send text message with Markdown support"""
        if not self._app:
            raise RuntimeError("Telegram channel not started")

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

            return str(message.message_id)

        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}", exc_info=True)
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

        media_source = media_url
        is_local_file = False

        # Detect local file (no URL scheme)
        if not media_url.startswith(("http://", "https://", "file://")):
            file_path = Path(media_url).expanduser()
            if file_path.exists() and file_path.is_file():
                media_source = open(file_path, "rb")  # noqa: WPS515 — closed in finally
                is_local_file = True
                logger.info("Sending local file: %s", file_path)

        try:
            if media_type == "photo":
                msg = await self._app.bot.send_photo(
                    chat_id=chat_id,
                    photo=media_source,
                    caption=caption,
                    parse_mode="Markdown" if caption else None,
                    reply_to_message_id=reply_id,
                )
            elif media_type == "video":
                msg = await self._app.bot.send_video(
                    chat_id=chat_id,
                    video=media_source,
                    caption=caption,
                    parse_mode="Markdown" if caption else None,
                    reply_to_message_id=reply_id,
                )
            elif media_type == "animation":
                msg = await self._app.bot.send_animation(
                    chat_id=chat_id,
                    animation=media_source,
                    caption=caption,
                    parse_mode="Markdown" if caption else None,
                    reply_to_message_id=reply_id,
                )
            elif media_type == "voice":
                try:
                    msg = await self._app.bot.send_voice(
                        chat_id=chat_id,
                        voice=media_source,
                        caption=caption,
                        parse_mode="Markdown" if caption else None,
                        reply_to_message_id=reply_id,
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
                    )
            elif media_type in ("audio",):
                msg = await self._app.bot.send_audio(
                    chat_id=chat_id,
                    audio=media_source,
                    caption=caption,
                    parse_mode="Markdown" if caption else None,
                    reply_to_message_id=reply_id,
                )
            else:
                # Default: send as document (covers pptx, pdf, zip, etc.)
                msg = await self._app.bot.send_document(
                    chat_id=chat_id,
                    document=media_source,
                    caption=caption,
                    parse_mode="Markdown" if caption else None,
                    reply_to_message_id=reply_id,
                )

            # Send overflow caption as a follow-up text message
            if overflow_text:
                await self._app.bot.send_message(
                    chat_id=chat_id,
                    text=overflow_text,
                    parse_mode="Markdown",
                )

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

            # Determine attachment type bucket (image vs file)
            is_image = (mime_type or "").startswith("image/")
            attach_type = "image" if is_image else "file"

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
                    response = await self._command_executor.execute(
                        command, session_id, user_id, is_owner
                    )
                    await self._app.bot.send_message(
                        chat_id=chat.id,
                        text=response,
                        reply_to_message_id=message.message_id
                    )
                    return
                except Exception as e:
                    logger.error(f"Error executing command: {e}", exc_info=True)
                    await self._app.bot.send_message(
                        chat_id=chat.id,
                        text=f"❌ Error: {str(e)}",
                        reply_to_message_id=message.message_id
                    )
                    return

        # Determine chat type
        chat_type = "direct"
        if chat.type == "group" or chat.type == "supergroup":
            chat_type = "group"
        elif chat.type == "channel":
            chat_type = "channel"

        # Create normalized message
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

        # Pass to handler
        await self._handle_message(inbound)

    async def _register_bot_commands(self):
        """Register bot commands with Telegram API (makes them visible in client)"""
        commands = [
            # Basic commands
            BotCommand("start", "🚀 Start using the bot"),
            BotCommand("help", "📋 View help information"),
            BotCommand("new", "🆕 Start new conversation"),
            BotCommand("status", "📊 View status"),
            BotCommand("model", "🤖 Switch AI model"),
            
            # Extended commands (already have handlers registered)
            BotCommand("commands", "📋 List all available commands"),
            BotCommand("context", "📖 Explain context management"),
            BotCommand("compact", "🗜️ Compact session context"),
            BotCommand("stop", "⏹️ Stop current run"),
            BotCommand("verbose", "🔍 Toggle verbose mode"),
            BotCommand("reasoning", "🧠 Toggle reasoning visibility"),
            BotCommand("usage", "📊 Show usage statistics"),
            
            # Session management
            BotCommand("reset", "🔄 Reset conversation (clear transcript)"),
        ]
        
        try:
            await self._app.bot.set_my_commands(commands)
            logger.info(f"✅ Registered {len(commands)} commands with Telegram API")
        except Exception as e:
            logger.error(f"Failed to register commands with Telegram API: {e}")

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
            allow_from_store = read_channel_allow_from_store("telegram")
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
            from ...pairing.pairing_store import upsert_channel_pairing_request
            from ...pairing.messages import format_pairing_request_message
            
            # Create or update pairing request
            result = upsert_channel_pairing_request(
                channel="telegram",
                sender_id=str(sender.id),
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
                user_info = f"\n📱 **Your Info**\n"
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
