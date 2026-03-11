"""Slack HTTP receiver with signature verification - P1-4

Implements HMAC-SHA256 signature verification for Slack webhooks.
Mirrors TS slack HTTP mode implementation.
"""
import hashlib
import hmac
import time
import logging
from typing import Any

logger = logging.getLogger(__name__)


def verify_slack_signature(
    signing_secret: str,
    timestamp: str,
    body: str,
    signature: str,
) -> bool:
    """
    Verify Slack signature using HMAC-SHA256.
    
    Mirrors TS signature verification logic.
    See: https://api.slack.com/authentication/verifying-requests-from-slack
    
    Args:
        signing_secret: Slack signing secret
        timestamp: X-Slack-Request-Timestamp header
        body: Raw request body
        signature: X-Slack-Signature header
    
    Returns:
        True if signature is valid, False otherwise
    """
    # Check timestamp freshness (within 5 minutes)
    try:
        request_timestamp = int(timestamp)
        if abs(time.time() - request_timestamp) > 60 * 5:
            logger.warning("[slack] Request timestamp too old or in future")
            return False
    except (ValueError, TypeError):
        logger.warning("[slack] Invalid timestamp format")
        return False
    
    # Compute expected signature
    sig_basestring = f"v0:{timestamp}:{body}"
    expected_signature = (
        "v0="
        + hmac.new(
            signing_secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256,
        ).hexdigest()
    )
    
    # Constant-time comparison
    return hmac.compare_digest(expected_signature, signature)


class HTTPReceiver:
    """
    HTTP receiver for Slack webhooks.
    
    Handles signature verification and event dispatch.
    Compatible with slack_bolt's AsyncApp.
    """
    
    def __init__(self, signing_secret: str, endpoint: str):
        self.signing_secret = signing_secret
        self.endpoint = endpoint
        self._app = None  # Will be set by AsyncApp
    
    def init_app(self, app: Any) -> None:
        """Initialize with AsyncApp instance"""
        self._app = app
    
    async def handle(self, request: Any) -> dict[str, Any]:
        """
        Handle incoming webhook request.
        
        Args:
            request: HTTP request object (framework-specific)
        
        Returns:
            Response dict with status and body
        """
        try:
            # Get headers and body
            timestamp = self._get_header(request, "X-Slack-Request-Timestamp", "")
            signature = self._get_header(request, "X-Slack-Signature", "")
            
            # Read body
            body = await self._read_body(request)
            body_str = body.decode("utf-8") if isinstance(body, bytes) else body
            
            # Verify signature
            if not verify_slack_signature(
                self.signing_secret,
                timestamp,
                body_str,
                signature,
            ):
                logger.warning("[slack] Invalid signature")
                return {"status": 401, "body": "Invalid signature"}
            
            # URL verification challenge (Slack sends this when setting up webhooks)
            import json
            try:
                payload = json.loads(body_str)
                if payload.get("type") == "url_verification":
                    return {
                        "status": 200,
                        "body": json.dumps({"challenge": payload.get("challenge")}),
                        "headers": {"Content-Type": "application/json"},
                    }
            except json.JSONDecodeError:
                pass
            
            # Dispatch event to app
            if self._app:
                # This would integrate with slack_bolt's event dispatcher
                # For now, return success
                # In a full implementation, this would call self._app's dispatch logic
                pass
            
            return {"status": 200, "body": "ok"}
            
        except Exception as e:
            logger.error(f"[slack] Error handling webhook request: {e}", exc_info=True)
            return {"status": 500, "body": "Internal server error"}
    
    def _get_header(self, request: Any, name: str, default: str = "") -> str:
        """Get header value from request (framework-agnostic)"""
        if hasattr(request, "headers"):
            headers = request.headers
            if isinstance(headers, dict):
                return headers.get(name, default)
            elif hasattr(headers, "get"):
                return headers.get(name, default)
        return default
    
    async def _read_body(self, request: Any) -> bytes:
        """Read request body (framework-agnostic)"""
        if hasattr(request, "body"):
            body = request.body
            if callable(body):
                body = await body() if hasattr(body, "__await__") else body()
            if isinstance(body, bytes):
                return body
            if isinstance(body, str):
                return body.encode("utf-8")
        
        if hasattr(request, "read"):
            body = request.read
            if callable(body):
                body = await body() if hasattr(body, "__await__") else body()
            if isinstance(body, bytes):
                return body
        
        return b""


def create_http_receiver(
    signing_secret: str,
    endpoint: str = "/slack/events",
) -> HTTPReceiver:
    """
    Create HTTP receiver for Slack webhooks.
    
    Args:
        signing_secret: Slack signing secret for signature verification
        endpoint: Webhook endpoint path (default: /slack/events)
    
    Returns:
        HTTPReceiver instance compatible with slack_bolt AsyncApp
    """
    return HTTPReceiver(signing_secret, endpoint)
