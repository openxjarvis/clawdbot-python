"""Pairing token generation and verification.

Mirrors TypeScript openclaw/src/infra/pairing-token.ts.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import base64

PAIRING_TOKEN_BYTES: int = 32


def generate_pairing_token() -> str:
    """Generate a cryptographically-random pairing token (URL-safe base64).

    Mirrors TS generatePairingToken() which calls
    ``randomBytes(32).toString('base64url')``.
    """
    raw = os.urandom(PAIRING_TOKEN_BYTES)
    # base64url — matches Node's Buffer.toString('base64url')
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def verify_pairing_token(provided: str, expected: str) -> bool:
    """Constant-time comparison of two pairing tokens.

    Mirrors TS verifyPairingToken() / safeEqualSecret().
    Returns False when either argument is empty.
    """
    if not provided or not expected:
        return False
    return hmac.compare_digest(
        provided.encode("utf-8"),
        expected.encode("utf-8"),
    )


__all__ = [
    "PAIRING_TOKEN_BYTES",
    "generate_pairing_token",
    "verify_pairing_token",
]
