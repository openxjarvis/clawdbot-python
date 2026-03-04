"""
Discord access policy — DM/group/allowlist gating.
Mirrors:
  src/discord/monitor/allow-list.ts
  src/discord/monitor/dm-command-auth.ts
  src/discord/monitor/dm-command-decision.ts
"""
from __future__ import annotations

import hashlib
import json
import logging
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import (
    DiscordGuildChannelConfig,
    DiscordGuildEntry,
    DmPolicy,
    GroupPolicy,
    ResolvedDiscordAccount,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Allowlist matching — mirrors allow-list.ts
# ---------------------------------------------------------------------------

_ID_PREFIXES = ("discord:", "user:", "pk:", "role:", "channel:")


def _strip_prefix(value: str) -> str:
    for pfx in _ID_PREFIXES:
        if value.startswith(pfx):
            return value[len(pfx):]
    return value


def _matches_entry(entry: str, discord_id: str, name: str | None, allow_name: bool) -> bool:
    """Check if a single allowlist entry matches the given discord_id or name."""
    if entry == "*":
        return True
    bare = _strip_prefix(entry)
    if bare == discord_id:
        return True
    if allow_name and name and bare.lower() == name.lower():
        return True
    return False


def allowlist_includes(
    entries: list[str],
    discord_id: str,
    name: str | None = None,
    allow_name: bool = False,
) -> bool:
    """Return True if any entry in `entries` matches."""
    if not entries:
        return False
    return any(_matches_entry(e, discord_id, name, allow_name) for e in entries)


def allowlist_includes_wildcard(entries: list[str]) -> bool:
    return "*" in entries


# ---------------------------------------------------------------------------
# Guild/channel allowlist resolution
# ---------------------------------------------------------------------------

def resolve_guild_config(
    account: ResolvedDiscordAccount,
    guild_id: str,
    guild_name: str | None = None,
) -> DiscordGuildEntry | None:
    """
    Resolve the guild config for a given guild ID.
    Lookup order: by ID → by slug → by wildcard "*"
    """
    guilds = account.guilds
    allow_name = account.dangerously_allow_name_matching

    # By ID
    if guild_id in guilds:
        return guilds[guild_id]

    # By slug or name
    if allow_name and guild_name:
        for entry in guilds.values():
            if entry.slug and entry.slug.lower() == guild_name.lower():
                return entry

    # Wildcard
    if "*" in guilds:
        return guilds["*"]

    return None


def resolve_channel_config(
    guild_entry: DiscordGuildEntry,
    channel_id: str,
    channel_name: str | None = None,
    parent_id: str | None = None,
    parent_name: str | None = None,
    allow_name: bool = False,
) -> DiscordGuildChannelConfig | None:
    """
    Resolve the channel config within a guild.
    Lookup order: by ID → by slug/name → by parent ID/name → by wildcard "*"
    Mirrors resolve-channels.ts thread parent fallback.
    """
    channels = guild_entry.channels

    if channel_id in channels:
        return channels[channel_id]

    if allow_name and channel_name:
        for ch_id, ch_cfg in channels.items():
            if ch_id.lower() == channel_name.lower():
                return ch_cfg

    # Thread inherits parent channel config
    if parent_id and parent_id in channels:
        return channels[parent_id]

    if allow_name and parent_name:
        for ch_id, ch_cfg in channels.items():
            if ch_id.lower() == parent_name.lower():
                return ch_cfg

    if "*" in channels:
        return channels["*"]

    return None


def is_guild_allowed(
    account: ResolvedDiscordAccount,
    guild_id: str,
    guild_name: str | None = None,
) -> bool:
    """Check whether a guild is allowed to interact, based on groupPolicy."""
    policy: GroupPolicy = account.group_policy

    if policy == "disabled":
        return False
    if policy == "open":
        if account.guilds:
            logger.debug(
                "[discord][policy] groupPolicy=open with guilds config set — "
                "all guilds are still allowed (open overrides allowlist)"
            )
        return True
    # "allowlist"
    guild_cfg = resolve_guild_config(account, guild_id, guild_name)
    return guild_cfg is not None


def is_channel_allowed(
    account: ResolvedDiscordAccount,
    guild_entry: DiscordGuildEntry,
    channel_id: str,
    channel_name: str | None = None,
    parent_id: str | None = None,
    parent_name: str | None = None,
) -> bool:
    """Return True if a specific channel (within an already-allowed guild) is accessible."""
    if not guild_entry.channels:
        return True  # No channel-level restrictions → all channels allowed

    ch_cfg = resolve_channel_config(
        guild_entry,
        channel_id,
        channel_name,
        parent_id,
        parent_name,
        account.dangerously_allow_name_matching,
    )
    if ch_cfg is None:
        return False
    # Explicit allow=False blocks the channel
    if ch_cfg.allow is False:
        return False
    return ch_cfg.enabled


def is_member_allowed(
    account: ResolvedDiscordAccount,
    guild_entry: DiscordGuildEntry | None,
    channel_cfg: DiscordGuildChannelConfig | None,
    user_id: str,
    user_name: str | None,
    user_roles: list[str],
) -> bool:
    """
    Check per-channel then per-guild user/role allowlists.
    An empty list means "no restriction at this level".
    """
    allow_name = account.dangerously_allow_name_matching

    # Channel-level users
    if channel_cfg and channel_cfg.users:
        if not allowlist_includes(channel_cfg.users, user_id, user_name, allow_name):
            return False

    # Channel-level roles
    if channel_cfg and channel_cfg.roles:
        if not any(allowlist_includes(channel_cfg.roles, rid, None, False) for rid in user_roles):
            return False

    # Guild-level users
    if guild_entry and guild_entry.users:
        if not allowlist_includes(guild_entry.users, user_id, user_name, allow_name):
            return False

    # Guild-level roles
    if guild_entry and guild_entry.roles:
        if not any(allowlist_includes(guild_entry.roles, rid, None, False) for rid in user_roles):
            return False

    return True


# ---------------------------------------------------------------------------
# DM pairing store
# ---------------------------------------------------------------------------

@dataclass
class _PairingEntry:
    code: str
    user_id: str
    username: str
    created_at: float = field(default_factory=time.time)


class PairingStore:
    """
    Persistent store for DM pairing codes.
    Mirrors TS pairing store in dm-command-auth.ts / dm-command-decision.ts.
    """

    _PAIRING_TTL = 600.0  # 10 minutes

    def __init__(self, persist_dir: Path | None = None, account_id: str = "default") -> None:
        self._pending: dict[str, _PairingEntry] = {}  # user_id -> entry
        self._approved: dict[str, str] = {}  # user_id -> approved_at ISO string

        self._path: Path | None = None
        if persist_dir:
            self._path = persist_dir / f"discord_pairing_{account_id}.json"
            self._load()

    def _load(self) -> None:
        if self._path and self._path.exists():
            try:
                data = json.loads(self._path.read_text())
                self._approved = data.get("approved", {})
            except Exception:
                pass

    def _save(self) -> None:
        if self._path:
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                self._path.write_text(json.dumps({"approved": self._approved}))
            except Exception:
                pass

    def create_pairing_code(self, user_id: str, username: str) -> str:
        code = secrets.token_hex(4).upper()
        self._pending[user_id] = _PairingEntry(code=code, user_id=user_id, username=username)
        return code

    def approve(self, user_id: str) -> bool:
        entry = self._pending.pop(user_id, None)
        if entry is None:
            return False
        import datetime
        self._approved[user_id] = datetime.datetime.utcnow().isoformat()
        self._save()
        return True

    def is_approved(self, user_id: str) -> bool:
        return user_id in self._approved

    def evict_expired_pending(self) -> None:
        now = time.time()
        expired = [uid for uid, e in self._pending.items() if now - e.created_at > self._PAIRING_TTL]
        for uid in expired:
            del self._pending[uid]

    def get_pending_code(self, user_id: str) -> str | None:
        self.evict_expired_pending()
        entry = self._pending.get(user_id)
        return entry.code if entry else None


# ---------------------------------------------------------------------------
# DM policy resolution
# ---------------------------------------------------------------------------

@dataclass
class DmPolicyResult:
    allowed: bool
    reason: str
    pairing_code: str | None = None  # set when a new pairing code was just issued


def check_dm_policy(
    account: ResolvedDiscordAccount,
    user_id: str,
    username: str | None,
    pairing_store: PairingStore | None,
) -> DmPolicyResult:
    """
    Evaluate DM access for a given user.
    Mirrors dm-command-auth.ts / dm-command-decision.ts.
    """
    dm = account.dm
    policy: DmPolicy = dm.policy
    allow_name = account.dangerously_allow_name_matching

    if not dm.enabled:
        return DmPolicyResult(allowed=False, reason="DMs disabled for this account")

    if policy == "disabled":
        return DmPolicyResult(allowed=False, reason="DM policy is disabled")

    if policy == "open":
        return DmPolicyResult(allowed=True, reason="DM policy is open")

    if policy == "allowlist":
        if allowlist_includes(dm.allow_from, user_id, username, allow_name):
            return DmPolicyResult(allowed=True, reason="User on allowlist")
        return DmPolicyResult(allowed=False, reason="User not on DM allowlist")

    # "pairing"
    if pairing_store is None:
        # No pairing store available — fall back to open (shouldn't happen)
        return DmPolicyResult(allowed=True, reason="Pairing fallback (no store)")

    # Always allow pre-approved users
    if allowlist_includes(dm.allow_from, user_id, username, allow_name):
        return DmPolicyResult(allowed=True, reason="User on allowlist (pairing mode)")

    if pairing_store.is_approved(user_id):
        return DmPolicyResult(allowed=True, reason="User approved via pairing")

    # Issue or re-use existing pairing code
    existing = pairing_store.get_pending_code(user_id)
    if existing:
        return DmPolicyResult(
            allowed=False,
            reason="Pairing required",
            pairing_code=existing,
        )

    code = pairing_store.create_pairing_code(user_id, username or user_id)
    return DmPolicyResult(
        allowed=False,
        reason="Pairing required — new code issued",
        pairing_code=code,
    )
