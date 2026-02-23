"""
Gateway authentication middleware

Integrates new authentication system into Gateway server.
"""
from __future__ import annotations

import logging
from typing import Any

from openclaw.auth.device_pairing import DevicePairingManager
from openclaw.gateway.auth import (
    AuthMode,
    AuthResult,
    authorize_gateway_connect,
    is_loopback_address,
    validate_auth_config,
)
from openclaw.gateway.error_codes import (
    ErrorCode,
    GatewayError,
    InvalidRequestError,
    NotLinkedError,
)

logger = logging.getLogger(__name__)


class GatewayAuthMiddleware:
    """
    Gateway authentication middleware.
    
    Handles multiple authentication methods:
    - Token authentication
    - Password authentication
    - Device pairing authentication
    - Local direct (loopback bypass)
    """
    
    def __init__(
        self,
        auth_mode: AuthMode = AuthMode.TOKEN,
        token: str | None = None,
        password: str | None = None,
        allow_local_direct: bool = True,
        device_pairing_enabled: bool = True,
    ):
        """
        Initialize auth middleware.
        
        Args:
            auth_mode: Authentication mode (token or password)
            token: Expected gateway token
            password: Expected gateway password
            allow_local_direct: Allow loopback connections without auth
            device_pairing_enabled: Enable device pairing authentication
        """
        self.auth_mode = auth_mode
        self.token = token
        self.password = password
        self.allow_local_direct = allow_local_direct
        self.device_pairing_enabled = device_pairing_enabled
        
        # Validate configuration
        validate_auth_config(auth_mode, token, password)
        
        # Device pairing manager (if enabled)
        self.device_manager = DevicePairingManager() if device_pairing_enabled else None
        
        logger.info(f"Gateway auth initialized: mode={auth_mode.value}, local_direct={allow_local_direct}")
    
    def authenticate_connection(
        self,
        request_token: str | None = None,
        request_password: str | None = None,
        device_id: str | None = None,
        device_token: str | None = None,
        client_ip: str | None = None,
    ) -> tuple[bool, str | None, dict[str, Any]]:
        """
        Authenticate a connection.
        
        Args:
            request_token: Token from request
            request_password: Password from request
            device_id: Device ID for device pairing
            device_token: Device token for device pairing
            client_ip: Client IP address
        
        Returns:
            (is_authenticated, error_reason, metadata)
        """
        metadata = {}
        
        # 1. Try device authentication first (if enabled and provided)
        if self.device_pairing_enabled and device_id and device_token:
            is_valid, reason = self.device_manager.validate_token(
                device_id=device_id,
                token=device_token,
            )
            if is_valid:
                logger.info(f"Device auth success: {device_id}")
                metadata["auth_method"] = "device"
                metadata["device_id"] = device_id
                return True, None, metadata
            else:
                logger.warning(f"Device auth failed: {device_id}, reason={reason}")
                # Continue to other auth methods
        
        # 2. Try gateway authentication
        result = authorize_gateway_connect(
            auth_mode=self.auth_mode,
            config_token=self.token,
            config_password=self.password,
            request_token=request_token,
            request_password=request_password,
            client_ip=client_ip if self.allow_local_direct else None,
        )
        
        if result.ok:
            logger.info(f"Gateway auth success: method={result.method}")
            metadata["auth_method"] = result.method.value if result.method else "unknown"
            if result.user:
                metadata["user"] = result.user
            return True, None, metadata
        
        # Authentication failed
        logger.warning(f"Gateway auth failed: reason={result.reason}")
        return False, result.reason, metadata
    
    def create_device_pairing_request(
        self,
        device_id: str,
        public_key: str,
        display_name: str | None = None,
        platform: str | None = None,
        remote_ip: str | None = None,
    ) -> str:
        """
        Create a device pairing request.
        
        Args:
            device_id: Device identifier
            public_key: Device public key
            display_name: Human-readable device name
            platform: Platform (ios/android/web/etc.)
            remote_ip: Client IP
        
        Returns:
            Request ID
        
        Raises:
            RuntimeError: If device pairing is disabled
        """
        if not self.device_pairing_enabled or not self.device_manager:
            raise RuntimeError("Device pairing is not enabled")
        
        request_id = self.device_manager.create_pairing_request(
            device_id=device_id,
            public_key=public_key,
            display_name=display_name,
            platform=platform,
            remote_ip=remote_ip,
        )
        
        logger.info(f"Device pairing request created: {request_id} for {device_id}")
        return request_id
    
    def list_pending_pairing_requests(self) -> list[dict[str, Any]]:
        """List pending device pairing requests."""
        if not self.device_pairing_enabled or not self.device_manager:
            return []
        
        requests = self.device_manager.list_pending()
        return [r.to_dict() for r in requests]
    
    def approve_pairing_request(self, request_id: str) -> dict[str, Any] | None:
        """
        Approve a device pairing request.
        
        Args:
            request_id: Request ID
        
        Returns:
            Device info with token, or None if not found
        """
        if not self.device_pairing_enabled or not self.device_manager:
            return None
        
        device = self.device_manager.approve_request(request_id)
        if device:
            logger.info(f"Device pairing approved: {device.device_id}")
            # Return device info with token
            token = next(iter(device.tokens.values())) if device.tokens else None
            return {
                "device_id": device.device_id,
                "display_name": device.display_name,
                "platform": device.platform,
                "token": token.token if token else None,
                "scopes": token.scopes if token else [],
            }
        
        return None
    
    def reject_pairing_request(self, request_id: str) -> bool:
        """Reject a device pairing request."""
        if not self.device_pairing_enabled or not self.device_manager:
            return False
        
        return self.device_manager.reject_request(request_id)
