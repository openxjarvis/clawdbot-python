"""SSRF protection utilities.

Python port of TypeScript src/infra/net/ssrf.ts.
Provides IP address classification to block Server-Side Request Forgery attacks.
"""

from __future__ import annotations

import socket
from typing import Sequence


class SsrfBlockedError(Exception):
    """Raised when a request is blocked due to SSRF policy."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_BLOCKED_HOSTNAMES: frozenset[str] = frozenset(["localhost", "metadata.google.internal"])


def _parse_ipv4(address: str) -> list[int] | None:
    """Parse dotted-decimal IPv4 into a list of 4 ints, or None on failure."""
    parts = address.split(".")
    if len(parts) != 4:
        return None
    numbers: list[int] = []
    for part in parts:
        try:
            value = int(part, 10)
        except ValueError:
            return None
        if value < 0 or value > 255:
            return None
        numbers.append(value)
    return numbers


def _strip_ipv6_zone_id(address: str) -> str:
    idx = address.find("%")
    return address[:idx] if idx >= 0 else address


def _parse_ipv6_hextets(address: str) -> list[int] | None:
    """
    Parse an IPv6 address string into 8 hextets (integers 0-0xffff).

    Handles:
    - Standard and compressed (::) notation
    - IPv4-embedded forms like ::ffff:127.0.0.1
    - Bracket-wrapped addresses are NOT handled here (strip brackets first)

    Returns None for malformed input (fail-closed for security).
    """
    inp = _strip_ipv6_zone_id(address.strip().lower())
    if not inp:
        return None

    # Handle IPv4-embedded IPv6 (e.g. ::ffff:127.0.0.1)
    if "." in inp:
        last_colon = inp.rfind(":")
        if last_colon < 0:
            return None
        ipv4 = _parse_ipv4(inp[last_colon + 1 :])
        if ipv4 is None:
            return None
        high = (ipv4[0] << 8) + ipv4[1]
        low = (ipv4[2] << 8) + ipv4[3]
        inp = f"{inp[:last_colon]}:{high:x}:{low:x}"

    double_colon_parts = inp.split("::")
    if len(double_colon_parts) > 2:
        return None

    head_parts = [p for p in double_colon_parts[0].split(":") if p] if double_colon_parts[0] else []
    if len(double_colon_parts) == 2:
        tail_parts = [p for p in double_colon_parts[1].split(":") if p] if double_colon_parts[1] else []
    else:
        tail_parts = []

    missing = 8 - len(head_parts) - len(tail_parts)
    if missing < 0:
        return None

    if len(double_colon_parts) == 1:
        full_parts = inp.split(":")
    else:
        full_parts = head_parts + ["0"] * missing + tail_parts

    if len(full_parts) != 8:
        return None

    hextets: list[int] = []
    for part in full_parts:
        if not part:
            return None
        try:
            value = int(part, 16)
        except ValueError:
            return None
        if value < 0 or value > 0xFFFF:
            return None
        hextets.append(value)
    return hextets


def _decode_ipv4_from_hextets(high: int, low: int) -> list[int]:
    return [(high >> 8) & 0xFF, high & 0xFF, (low >> 8) & 0xFF, low & 0xFF]


def _extract_ipv4_from_embedded_ipv6(hextets: list[int]) -> list[int] | None:
    """
    Extract the embedded IPv4 address from an IPv6 address using known tunnelling prefixes.

    Mirrors TS extractIpv4FromEmbeddedIpv6().
    """
    h = hextets

    # IPv4-mapped (::ffff:a.b.c.d) and IPv4-compatible (::a.b.c.d)
    if h[0] == 0 and h[1] == 0 and h[2] == 0 and h[3] == 0 and h[4] == 0 and h[5] in (0xFFFF, 0):
        return _decode_ipv4_from_hextets(h[6], h[7])

    # NAT64 well-known prefix: 64:ff9b::/96
    if h[0] == 0x0064 and h[1] == 0xFF9B and h[2] == 0 and h[3] == 0 and h[4] == 0 and h[5] == 0:
        return _decode_ipv4_from_hextets(h[6], h[7])

    # NAT64 local-use prefix: 64:ff9b:1::/48
    if h[0] == 0x0064 and h[1] == 0xFF9B and h[2] == 0x0001 and h[3] == 0 and h[4] == 0 and h[5] == 0:
        return _decode_ipv4_from_hextets(h[6], h[7])

    # 6to4 prefix: 2002::/16
    if h[0] == 0x2002:
        return _decode_ipv4_from_hextets(h[1], h[2])

    # Teredo prefix: 2001:0000::/32 (client IPv4 XOR'd with 0xffff)
    if h[0] == 0x2001 and h[1] == 0x0000:
        return _decode_ipv4_from_hextets(h[6] ^ 0xFFFF, h[7] ^ 0xFFFF)

    return None


def _is_private_ipv4(parts: list[int]) -> bool:
    """
    Return True if the IPv4 address belongs to a private/reserved range.

    Mirrors TS isPrivateIpv4().
    """
    o1, o2 = parts[0], parts[1]
    if o1 == 0:           return True   # 0.0.0.0/8 - unspecified
    if o1 == 10:          return True   # 10.0.0.0/8 - private
    if o1 == 127:         return True   # 127.0.0.0/8 - loopback
    if o1 == 169 and o2 == 254:         return True   # 169.254.0.0/16 - link-local
    if o1 == 172 and 16 <= o2 <= 31:    return True   # 172.16.0.0/12 - private
    if o1 == 192 and o2 == 168:         return True   # 192.168.0.0/16 - private
    if o1 == 100 and 64 <= o2 <= 127:   return True   # 100.64.0.0/10 - shared address space
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_private_ip_address(address: str) -> bool:
    """
    Return True if *address* is a private/internal IP that should be blocked in SSRF checks.

    Handles:
    - IPv4 dotted-decimal
    - IPv6 (including compressed, link-local, loopback)
    - IPv4-embedded IPv6 (::ffff:, NAT64, 6to4, Teredo)
    - Bracket-wrapped IPv6 (e.g. ``[::1]``)
    - Zone-ID suffixed IPv6 (e.g. ``fe80::1%lo0``)

    Security note: Malformed IPv6 inputs return True (fail-closed).

    Mirrors TS isPrivateIpAddress() from src/infra/net/ssrf.ts.
    """
    normalized = address.strip().lower()
    if normalized.startswith("[") and normalized.endswith("]"):
        normalized = normalized[1:-1]
    if not normalized:
        return False

    if ":" in normalized:
        hextets = _parse_ipv6_hextets(normalized)
        if hextets is None:
            # Fail closed on parse error
            return True

        # Unspecified ::
        if all(h == 0 for h in hextets):
            return True

        # Loopback ::1
        if hextets[:7] == [0, 0, 0, 0, 0, 0, 0] and hextets[7] == 1:
            return True

        embedded = _extract_ipv4_from_embedded_ipv6(hextets)
        if embedded is not None:
            return _is_private_ipv4(embedded)

        first = hextets[0]
        if (first & 0xFFC0) == 0xFE80:  return True   # fe80::/10 link-local
        if (first & 0xFFC0) == 0xFEC0:  return True   # fec0::/10 site-local (deprecated)
        if (first & 0xFE00) == 0xFC00:  return True   # fc00::/7  unique local
        return False

    ipv4 = _parse_ipv4(normalized)
    if ipv4 is None:
        return False
    return _is_private_ipv4(ipv4)


def is_blocked_hostname(hostname: str) -> bool:
    """
    Return True if *hostname* is a well-known blocked hostname (localhost, .local, .internal, etc.).

    Mirrors TS isBlockedHostname().
    """
    normalized = hostname.strip().lower()
    if not normalized:
        return False
    if normalized in _BLOCKED_HOSTNAMES:
        return True
    return (
        normalized.endswith(".localhost")
        or normalized.endswith(".local")
        or normalized.endswith(".internal")
    )


__all__ = [
    "SsrfBlockedError",
    "is_private_ip_address",
    "is_blocked_hostname",
]
