"""Feishu target ID normalization and resolution utilities.

Handles routing prefix strings used by the system internally:
  chat:oc_xxx   → chat_id
  group:oc_xxx  → chat_id
  user:ou_xxx   → open_id
  dm:ou_xxx     → open_id / user_id
  open_id:ou_xx → open_id

Also handles raw IDs:
  oc_xxx        → chat_id
  ou_xxx        → open_id
  on_xxx        → union_id
  <other>       → user_id

Mirrors TypeScript: extensions/feishu/src/targets.ts
"""
from __future__ import annotations

import re

_CHAT_ID_PREFIX = "oc_"
_OPEN_ID_PREFIX = "ou_"
_UNION_ID_PREFIX = "on_"
_USER_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
_PROVIDER_RE = re.compile(r"^(feishu|lark):", re.IGNORECASE)
_ROUTING_PREFIX_RE = re.compile(
    r"^(chat|group|channel|user|dm|open_id):", re.IGNORECASE
)

FeishuIdType = str  # "chat_id" | "open_id" | "union_id" | "user_id"


def _strip_provider_prefix(raw: str) -> str:
    """Remove leading ``feishu:`` / ``lark:`` provider prefix."""
    return _PROVIDER_RE.sub("", raw).strip()


def detect_id_type(id_: str) -> FeishuIdType | None:
    """Detect the Feishu ID type from a raw (no-prefix) ID string.

    Returns "chat_id", "open_id", "union_id", "user_id", or None.
    Mirrors TS detectIdType().
    """
    trimmed = id_.strip()
    if trimmed.startswith(_CHAT_ID_PREFIX):
        return "chat_id"
    if trimmed.startswith(_OPEN_ID_PREFIX):
        return "open_id"
    if trimmed.startswith(_UNION_ID_PREFIX):
        return "union_id"
    if _USER_ID_RE.match(trimmed):
        return "user_id"
    return None


def normalize_feishu_target(raw: str) -> str | None:
    """Strip provider and routing prefixes, returning the bare Feishu ID.

    Examples:
      "chat:oc_abc"    → "oc_abc"
      "user:ou_abc"    → "ou_abc"
      "feishu:ou_abc"  → "ou_abc"
      "dm:ou_abc"      → "ou_abc"
      "ou_abc"         → "ou_abc"
      ""               → None

    Mirrors TS normalizeFeishuTarget().
    """
    trimmed = raw.strip()
    if not trimmed:
        return None

    without_provider = _strip_provider_prefix(trimmed)
    lower = without_provider.lower()

    for prefix in ("chat:", "group:", "channel:", "user:", "dm:", "open_id:"):
        if lower.startswith(prefix):
            rest = without_provider[len(prefix):].strip()
            return rest or None

    return without_provider or None


def format_feishu_target(id_: str, id_type: FeishuIdType | None = None) -> str:
    """Format a Feishu ID with the canonical routing prefix.

    Examples:
      ("oc_abc", "chat_id") → "chat:oc_abc"
      ("ou_abc", "open_id") → "user:ou_abc"
      ("oc_abc", None)      → "chat:oc_abc"

    Mirrors TS formatFeishuTarget().
    """
    trimmed = id_.strip()
    if id_type == "chat_id" or trimmed.startswith(_CHAT_ID_PREFIX):
        return f"chat:{trimmed}"
    if id_type == "open_id" or trimmed.startswith(_OPEN_ID_PREFIX):
        return f"user:{trimmed}"
    return trimmed


def resolve_receive_id_type(target: str) -> tuple[str, str]:
    """Resolve (receive_id, receive_id_type) from a target string.

    Handles both routing prefixes (chat:, user:, dm:, ...) and raw IDs (oc_, ou_, on_).

    Returns (receive_id, receive_id_type) where receive_id_type is one of:
      "chat_id", "open_id", "union_id", "user_id"

    Mirrors TS resolveReceiveIdType() — extended with union_id support.
    """
    trimmed = target.strip()
    lower = trimmed.lower()

    # Routing prefix — resolve type from prefix then detect raw ID type
    if lower.startswith("chat:") or lower.startswith("group:") or lower.startswith("channel:"):
        for prefix in ("chat:", "group:", "channel:"):
            if lower.startswith(prefix):
                rid = trimmed[len(prefix):].strip()
                return rid, "chat_id"

    if lower.startswith("open_id:"):
        rid = trimmed[len("open_id:"):].strip()
        return rid, "open_id"

    if lower.startswith("user:") or lower.startswith("dm:"):
        for prefix in ("user:", "dm:"):
            if lower.startswith(prefix):
                rid = trimmed[len(prefix):].strip()
                if rid.startswith(_OPEN_ID_PREFIX):
                    return rid, "open_id"
                return rid, "user_id"

    # Strip provider prefix and try raw ID detection
    without_provider = _strip_provider_prefix(trimmed)
    if without_provider.startswith(_CHAT_ID_PREFIX):
        return without_provider, "chat_id"
    if without_provider.startswith(_OPEN_ID_PREFIX):
        return without_provider, "open_id"
    if without_provider.startswith(_UNION_ID_PREFIX):
        return without_provider, "union_id"

    return without_provider, "user_id"


def looks_like_feishu_id(raw: str) -> bool:
    """Return True if the string looks like a Feishu ID or target.

    Mirrors TS looksLikeFeishuId().
    """
    trimmed = _strip_provider_prefix(raw.strip())
    if not trimmed:
        return False
    if _ROUTING_PREFIX_RE.match(trimmed):
        return True
    if trimmed.startswith(_CHAT_ID_PREFIX):
        return True
    if trimmed.startswith(_OPEN_ID_PREFIX):
        return True
    return False
