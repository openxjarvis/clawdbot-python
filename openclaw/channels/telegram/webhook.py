"""Telegram webhook mode support

Alternative to long polling for receiving Telegram updates.
Starts an HTTP server to receive webhook callbacks from Telegram.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from typing import Any

from telegram import Update
from telegram.ext import Application

logger = logging.getLogger(__name__)

TELEGRAM_WEBHOOK_MAX_BODY_BYTES = 1024 * 1024
TELEGRAM_WEBHOOK_BODY_TIMEOUT_MS = 30_000
DEFAULT_WEBHOOK_PATH = "/telegram-webhook"
DEFAULT_WEBHOOK_HOST = "127.0.0.1"
DEFAULT_WEBHOOK_PORT = 8787


class TelegramWebhookServer:
    """HTTP server for Telegram webhook callbacks"""
    
    def __init__(
        self,
        app: Application,
        webhook_url: str,
        webhook_secret: str,
        webhook_path: str = DEFAULT_WEBHOOK_PATH,
        webhook_host: str = DEFAULT_WEBHOOK_HOST,
        webhook_port: int = DEFAULT_WEBHOOK_PORT,
    ):
        """
        Initialize webhook server
        
        Args:
            app: Telegram Application instance
            webhook_url: Public webhook URL
            webhook_secret: Secret token for HMAC validation
            webhook_path: Webhook path (default: /telegram-webhook)
            webhook_host: Listen host (default: 127.0.0.1)
            webhook_port: Listen port (default: 8787)
        """
        self._app = app
        self._webhook_url = webhook_url
        self._webhook_secret = webhook_secret
        self._webhook_path = webhook_path
        self._webhook_host = webhook_host
        self._webhook_port = webhook_port
        self._server = None
        self._server_task = None
    
    def _validate_secret(self, header_value: str | None, body: bytes) -> bool:
        """
        Validate webhook secret using HMAC
        
        Args:
            header_value: X-Telegram-Bot-Api-Secret-Token header value
            body: Request body bytes
        
        Returns:
            True if secret is valid
        """
        if not header_value:
            return False
        
        # Telegram sends the secret token in plain text, we just compare
        return header_value == self._webhook_secret
    
    async def _handle_webhook_request(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Handle incoming webhook request"""
        try:
            # Read request line
            request_line = await reader.readline()
            request_str = request_line.decode('utf-8').strip()
            
            if not request_str:
                writer.write(b"HTTP/1.1 400 Bad Request\r\n\r\n")
                await writer.drain()
                writer.close()
                return
            
            parts = request_str.split()
            if len(parts) < 2:
                writer.write(b"HTTP/1.1 400 Bad Request\r\n\r\n")
                await writer.drain()
                writer.close()
                return
            
            method = parts[0]
            path = parts[1]
            
            # Read headers
            headers = {}
            while True:
                line = await reader.readline()
                if line == b'\r\n' or line == b'\n':
                    break
                
                header_str = line.decode('utf-8').strip()
                if ':' in header_str:
                    key, value = header_str.split(':', 1)
                    headers[key.strip().lower()] = value.strip()
            
            # Health check
            if path == "/healthz":
                writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")
                await writer.drain()
                writer.close()
                return
            
            # Only accept POST to webhook path
            if method != "POST" or path != self._webhook_path:
                writer.write(b"HTTP/1.1 404 Not Found\r\n\r\n")
                await writer.drain()
                writer.close()
                return
            
            # Read body
            content_length = int(headers.get('content-length', 0))
            if content_length > TELEGRAM_WEBHOOK_MAX_BODY_BYTES:
                writer.write(b"HTTP/1.1 413 Payload Too Large\r\n\r\n")
                await writer.drain()
                writer.close()
                return
            
            body = await reader.read(content_length)
            
            # Validate secret
            secret_header = headers.get('x-telegram-bot-api-secret-token')
            if not self._validate_secret(secret_header, body):
                logger.warning("Webhook request with invalid secret")
                writer.write(b"HTTP/1.1 401 Unauthorized\r\n\r\n")
                await writer.drain()
                writer.close()
                return
            
            # Parse update
            try:
                update_data = json.loads(body.decode('utf-8'))
                update = Update.de_json(update_data, self._app.bot)
                
                # Process update
                await self._app.process_update(update)
                
                writer.write(b"HTTP/1.1 200 OK\r\n\r\n")
                await writer.drain()
            
            except Exception as exc:
                logger.error("Failed to process webhook update: %s", exc, exc_info=True)
                writer.write(b"HTTP/1.1 500 Internal Server Error\r\n\r\n")
                await writer.drain()
        
        except Exception as exc:
            logger.error("Webhook request handling error: %s", exc, exc_info=True)
        
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
    
    async def start(self) -> None:
        """Start webhook server"""
        # Set webhook URL
        allowed_updates = [
            "message",
            "edited_message",
            "channel_post",
            "edited_channel_post",
            "callback_query",
            "message_reaction",
        ]
        
        await self._app.bot.set_webhook(
            url=self._webhook_url,
            secret_token=self._webhook_secret,
            allowed_updates=allowed_updates,
        )
        
        logger.info("Webhook set to %s", self._webhook_url)
        
        # Start HTTP server
        self._server = await asyncio.start_server(
            self._handle_webhook_request,
            self._webhook_host,
            self._webhook_port,
        )
        
        logger.info(
            "Webhook server listening on %s:%d%s",
            self._webhook_host,
            self._webhook_port,
            self._webhook_path,
        )
    
    async def stop(self) -> None:
        """Stop webhook server"""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info("Webhook server stopped")
    
    def get_local_url(self) -> str:
        """Get local webhook URL"""
        host = "localhost" if self._webhook_host == "0.0.0.0" else self._webhook_host
        return f"http://{host}:{self._webhook_port}{self._webhook_path}"


async def start_telegram_webhook(
    app: Application,
    webhook_url: str,
    webhook_secret: str,
    webhook_path: str = DEFAULT_WEBHOOK_PATH,
    webhook_host: str = DEFAULT_WEBHOOK_HOST,
    webhook_port: int = DEFAULT_WEBHOOK_PORT,
) -> TelegramWebhookServer:
    """
    Start Telegram webhook server
    
    Args:
        app: Telegram Application instance
        webhook_url: Public webhook URL (must be HTTPS for Telegram)
        webhook_secret: Secret token for validation
        webhook_path: Webhook endpoint path
        webhook_host: Host to bind to
        webhook_port: Port to bind to
    
    Returns:
        TelegramWebhookServer instance
    """
    if not webhook_secret or not webhook_secret.strip():
        raise ValueError(
            "Telegram webhook mode requires a non-empty secret token. "
            "Set channels.telegram.webhookSecret in your config."
        )
    
    server = TelegramWebhookServer(
        app=app,
        webhook_url=webhook_url,
        webhook_secret=webhook_secret,
        webhook_path=webhook_path,
        webhook_host=webhook_host,
        webhook_port=webhook_port,
    )
    
    await server.start()
    
    return server
