"""Device identity management - Ed25519 key pairs and device IDs

Ports TypeScript src/infra/device-identity.ts functionality.
Manages ~/.openclaw/identity/device.json containing:
- Device ID (SHA-256 of public key)
- Ed25519 key pair (PEM format)
- Creation timestamp
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from openclaw.config.paths import resolve_state_dir

logger = logging.getLogger(__name__)

DEVICE_IDENTITY_FILENAME = "device.json"


class DeviceIdentity:
    """Device identity with Ed25519 key pair"""

    def __init__(
        self,
        device_id: str,
        public_key_pem: str,
        private_key_pem: str,
        created_at_ms: int,
    ):
        self.device_id = device_id
        self.public_key_pem = public_key_pem
        self.private_key_pem = private_key_pem
        self.created_at_ms = created_at_ms

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON storage"""
        return {
            "version": 1,
            "deviceId": self.device_id,
            "publicKeyPem": self.public_key_pem,
            "privateKeyPem": self.private_key_pem,
            "createdAtMs": self.created_at_ms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeviceIdentity:
        """Deserialize from JSON dict"""
        return cls(
            device_id=data["deviceId"],
            public_key_pem=data["publicKeyPem"],
            private_key_pem=data["privateKeyPem"],
            created_at_ms=data["createdAtMs"],
        )

    def get_public_key(self) -> Ed25519PublicKey:
        """Load public key from PEM"""
        return serialization.load_pem_public_key(self.public_key_pem.encode())

    def get_private_key(self) -> Ed25519PrivateKey:
        """Load private key from PEM"""
        return serialization.load_pem_private_key(
            self.private_key_pem.encode(), password=None
        )

    def sign(self, message: bytes) -> bytes:
        """Sign message with private key"""
        private_key = self.get_private_key()
        return private_key.sign(message)

    def verify(self, signature: bytes, message: bytes) -> bool:
        """Verify signature with public key"""
        try:
            public_key = self.get_public_key()
            public_key.verify(signature, message)
            return True
        except Exception:
            return False


def _generate_key_pair() -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    """Generate new Ed25519 key pair"""
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    return private_key, public_key


def _serialize_private_key(private_key: Ed25519PrivateKey) -> str:
    """Serialize private key to PEM format"""
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return pem.decode()


def _serialize_public_key(public_key: Ed25519PublicKey) -> str:
    """Serialize public key to PEM format"""
    pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return pem.decode()


def _derive_device_id(public_key: Ed25519PublicKey) -> str:
    """Derive device ID from public key (SHA-256 hash)"""
    public_bytes = public_key.public_bytes_raw()
    hash_bytes = hashlib.sha256(public_bytes).digest()
    return hash_bytes.hex()


def _resolve_identity_dir() -> Path:
    """Resolve ~/.openclaw/identity directory"""
    state_dir = Path(resolve_state_dir())
    identity_dir = state_dir / "identity"
    return identity_dir


def _resolve_device_identity_path() -> Path:
    """Resolve ~/.openclaw/identity/device.json path"""
    identity_dir = _resolve_identity_dir()
    return identity_dir / DEVICE_IDENTITY_FILENAME


def _read_device_identity_file(path: Path) -> dict[str, Any] | None:
    """Read device identity JSON file"""
    try:
        if not path.exists():
            return None
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        return data
    except Exception as e:
        logger.warning(f"Failed to read device identity from {path}: {e}")
        return None


def _write_device_identity_file(path: Path, data: dict[str, Any]) -> None:
    """Write device identity JSON file atomically"""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

    # Atomic write: temp file + rename
    temp_path = path.with_suffix(".tmp")
    try:
        temp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        temp_path.replace(path)
        # Set restrictive permissions on identity file
        path.chmod(0o600)
        logger.info(f"Device identity saved to {path}")
    except Exception as e:
        logger.error(f"Failed to write device identity to {path}: {e}")
        if temp_path.exists():
            temp_path.unlink()
        raise


def load_or_create_device_identity() -> DeviceIdentity:
    """Load existing device identity or create new one
    
    Returns:
        DeviceIdentity instance
    """
    path = _resolve_device_identity_path()

    # Try to load existing identity
    data = _read_device_identity_file(path)
    if data is not None:
        try:
            identity = DeviceIdentity.from_dict(data)
            logger.debug(f"Loaded device identity: {identity.device_id}")
            return identity
        except Exception as e:
            logger.warning(f"Failed to parse device identity, regenerating: {e}")

    # Generate new identity
    logger.info("Generating new device identity...")
    private_key, public_key = _generate_key_pair()

    private_pem = _serialize_private_key(private_key)
    public_pem = _serialize_public_key(public_key)
    device_id = _derive_device_id(public_key)
    created_at_ms = int(datetime.now(UTC).timestamp() * 1000)

    identity = DeviceIdentity(
        device_id=device_id,
        public_key_pem=public_pem,
        private_key_pem=private_pem,
        created_at_ms=created_at_ms,
    )

    # Save to file
    _write_device_identity_file(path, identity.to_dict())

    logger.info(f"Created new device identity: {device_id}")
    return identity


def get_device_identity() -> DeviceIdentity | None:
    """Get existing device identity without creating new one
    
    Returns:
        DeviceIdentity or None if not found
    """
    path = _resolve_device_identity_path()
    data = _read_device_identity_file(path)
    if data is None:
        return None
    try:
        return DeviceIdentity.from_dict(data)
    except Exception as e:
        logger.warning(f"Failed to parse device identity: {e}")
        return None


def verify_device_signature(device_id: str, signature: bytes, message: bytes) -> bool:
    """Verify signature from a device
    
    Args:
        device_id: Device ID (for logging)
        signature: Signature bytes
        message: Original message bytes
        
    Returns:
        True if signature is valid
    """
    identity = get_device_identity()
    if identity is None:
        logger.warning(f"No device identity found for verification")
        return False

    if identity.device_id != device_id:
        logger.warning(
            f"Device ID mismatch: expected {identity.device_id}, got {device_id}"
        )
        return False

    return identity.verify(signature, message)
