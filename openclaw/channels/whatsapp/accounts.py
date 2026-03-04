"""WhatsApp multi-account resolution and ID normalization.

Mirrors TypeScript: src/web/accounts.ts and src/whatsapp/normalize.ts
"""
from __future__ import annotations

import re
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .config import ResolvedWhatsAppAccount

DEFAULT_ACCOUNT_ID = "default"


def normalize_wa_id(phone: str) -> str:
    """
    Normalize a phone number to E.164 format, stripping JID suffixes.

    Handles:
    - JIDs like "1234567890@s.whatsapp.net" → "+1234567890"
    - "1234567890:12@s.whatsapp.net" → "+1234567890"
    - "+1 (234) 567-890" → "+1234567890"
    - "1234567890" → "+1234567890"
    """
    stripped = phone.strip()

    # Strip JID suffix (@...)
    if "@" in stripped:
        stripped = stripped.split("@")[0]
    # Strip device suffix (:...)
    if ":" in stripped:
        stripped = stripped.split(":")[0]

    # Keep only digits and leading +
    digits = re.sub(r"[^\d+]", "", stripped)
    if not digits:
        return phone

    # Ensure leading +
    if not digits.startswith("+"):
        digits = f"+{digits}"

    return digits


def jid_to_e164(jid: str) -> str | None:
    """Convert a WhatsApp JID to E.164, or None if not a phone JID."""
    try:
        bare = jid.split(":")[0].split("@")[0]
        if not re.match(r"^\d+$", bare):
            return None
        return f"+{bare}"
    except Exception:
        return None


def e164_to_jid(e164: str) -> str:
    """Convert E.164 or bare number to WhatsApp individual JID."""
    digits = re.sub(r"[^\d]", "", e164)
    return f"{digits}@s.whatsapp.net"


def is_group_jid(jid: str) -> bool:
    return jid.endswith("@g.us")


def get_default_account(
    accounts: list[ResolvedWhatsAppAccount],
    default_id: str | None = None,
) -> ResolvedWhatsAppAccount | None:
    """Return the preferred default account."""
    if not accounts:
        return None
    if default_id:
        for acct in accounts:
            if acct.account_id == default_id:
                return acct
    # Fall back to account named "default" or first
    for acct in accounts:
        if acct.account_id == DEFAULT_ACCOUNT_ID:
            return acct
    return accounts[0]


def resolve_account_by_id(
    accounts: list[ResolvedWhatsAppAccount],
    account_id: str | None,
) -> ResolvedWhatsAppAccount | None:
    """Find account by ID."""
    if not account_id:
        return None
    for acct in accounts:
        if acct.account_id == account_id:
            return acct
    return None


def normalize_account_id(raw: Any) -> str:
    """Return a normalized (lowercase stripped) account ID."""
    if not raw:
        return DEFAULT_ACCOUNT_ID
    return str(raw).strip().lower()
