"""Device authentication store - Manages device auth tokens

Ports TypeScript src/infra/device-auth-store.ts functionality.
Manages ~/.openclaw/identity/device-auth.json containing:
- Device ID
- Role-based tokens (operator, user, etc.)
- Scopes and permissions
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from openclaw.config.paths import resolve_state_dir

logger = logging.getLogger(__name__)

DEVICE_AUTH_FILENAME = "device-auth.json"


class DeviceAuthToken:
    """Single auth token for a device"""

    def __init__(
        self,
        token: str,
        role: str,
        scopes: list[str],
        updated_at_ms: int | None = None,
    ):
        self.token = token
        self.role = role
        self.scopes = scopes
        self.updated_at_ms = updated_at_ms or int(datetime.now(UTC).timestamp() * 1000)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict"""
        return {
            "token": self.token,
            "role": self.role,
            "scopes": self.scopes,
            "updatedAtMs": self.updated_at_ms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeviceAuthToken:
        """Deserialize from dict"""
        return cls(
            token=data["token"],
            role=data["role"],
            scopes=data["scopes"],
            updated_at_ms=data.get("updatedAtMs"),
        )


class DeviceAuthStore:
    """Device authentication store"""

    def __init__(self, device_id: str, tokens: dict[str, DeviceAuthToken]):
        self.version = 1
        self.device_id = device_id
        self.tokens = tokens

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON storage"""
        return {
            "version": self.version,
            "deviceId": self.device_id,
            "tokens": {role: token.to_dict() for role, token in self.tokens.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeviceAuthStore:
        """Deserialize from JSON dict"""
        tokens = {
            role: DeviceAuthToken.from_dict(token_data)
            for role, token_data in data.get("tokens", {}).items()
        }
        return cls(device_id=data["deviceId"], tokens=tokens)

    def get_token(self, role: str) -> DeviceAuthToken | None:
        """Get token for a role"""
        return self.tokens.get(role)

    def set_token(self, role: str, token: DeviceAuthToken) -> None:
        """Set token for a role"""
        self.tokens[role] = token

    def remove_token(self, role: str) -> bool:
        """Remove token for a role. Returns True if token existed."""
        if role in self.tokens:
            del self.tokens[role]
            return True
        return False

    def has_scope(self, role: str, scope: str) -> bool:
        """Check if role has a specific scope"""
        token = self.get_token(role)
        if token is None:
            return False
        return scope in token.scopes


def _resolve_identity_dir() -> Path:
    """Resolve ~/.openclaw/identity directory"""
    state_dir = Path(resolve_state_dir())
    identity_dir = state_dir / "identity"
    return identity_dir


def _resolve_device_auth_path() -> Path:
    """Resolve ~/.openclaw/identity/device-auth.json path"""
    identity_dir = _resolve_identity_dir()
    return identity_dir / DEVICE_AUTH_FILENAME


def _read_device_auth_file(path: Path) -> dict[str, Any] | None:
    """Read device auth JSON file"""
    try:
        if not path.exists():
            return None
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        return data
    except Exception as e:
        logger.warning(f"Failed to read device auth from {path}: {e}")
        return None


def _write_device_auth_file(path: Path, data: dict[str, Any]) -> None:
    """Write device auth JSON file atomically"""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

    # Atomic write: temp file + rename
    temp_path = path.with_suffix(".tmp")
    try:
        temp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        temp_path.replace(path)
        # Set restrictive permissions on auth file
        path.chmod(0o600)
        logger.debug(f"Device auth saved to {path}")
    except Exception as e:
        logger.error(f"Failed to write device auth to {path}: {e}")
        if temp_path.exists():
            temp_path.unlink()
        raise


def load_device_auth_store(device_id: str) -> DeviceAuthStore:
    """Load device auth store or create empty one
    
    Args:
        device_id: Device ID for this store
        
    Returns:
        DeviceAuthStore instance
    """
    path = _resolve_device_auth_path()

    # Try to load existing store
    data = _read_device_auth_file(path)
    if data is not None:
        try:
            store = DeviceAuthStore.from_dict(data)
            # Verify device ID matches
            if store.device_id != device_id:
                logger.warning(
                    f"Device ID mismatch in auth store: expected {device_id}, got {store.device_id}"
                )
                # Create new store with correct device ID
                store = DeviceAuthStore(device_id=device_id, tokens={})
            else:
                logger.debug(f"Loaded device auth store for {device_id}")
                return store
        except Exception as e:
            logger.warning(f"Failed to parse device auth store, creating new: {e}")

    # Create new store
    logger.info(f"Creating new device auth store for {device_id}")
    store = DeviceAuthStore(device_id=device_id, tokens={})
    
    # Save to file
    _write_device_auth_file(path, store.to_dict())
    
    return store


def save_device_auth_store(store: DeviceAuthStore) -> None:
    """Save device auth store to file
    
    Args:
        store: DeviceAuthStore to save
    """
    path = _resolve_device_auth_path()
    _write_device_auth_file(path, store.to_dict())


def get_device_auth_token(device_id: str, role: str) -> DeviceAuthToken | None:
    """Get auth token for a device and role
    
    Args:
        device_id: Device ID
        role: Role name (e.g., "operator")
        
    Returns:
        DeviceAuthToken or None if not found
    """
    store = load_device_auth_store(device_id)
    return store.get_token(role)


def set_device_auth_token(
    device_id: str, role: str, token: str, scopes: list[str]
) -> None:
    """Set auth token for a device and role
    
    Args:
        device_id: Device ID
        role: Role name
        token: Token string
        scopes: List of scopes/permissions
    """
    store = load_device_auth_store(device_id)
    auth_token = DeviceAuthToken(
        token=token,
        role=role,
        scopes=scopes,
        updated_at_ms=int(datetime.now(UTC).timestamp() * 1000),
    )
    store.set_token(role, auth_token)
    save_device_auth_store(store)
    logger.info(f"Set auth token for device {device_id}, role {role}")


def remove_device_auth_token(device_id: str, role: str) -> bool:
    """Remove auth token for a device and role
    
    Args:
        device_id: Device ID
        role: Role name
        
    Returns:
        True if token was removed
    """
    store = load_device_auth_store(device_id)
    removed = store.remove_token(role)
    if removed:
        save_device_auth_store(store)
        logger.info(f"Removed auth token for device {device_id}, role {role}")
    return removed


def verify_device_auth_token(device_id: str, role: str, token: str) -> bool:
    """Verify if a token is valid for a device and role
    
    Args:
        device_id: Device ID
        role: Role name
        token: Token to verify
        
    Returns:
        True if token is valid
    """
    auth_token = get_device_auth_token(device_id, role)
    if auth_token is None:
        return False
    return auth_token.token == token
