"""Feishu directory listing — peers (users) and groups (chats).

Used by ``openclaw message list-targets --channel feishu`` to enumerate
known Feishu targets from config and optionally from the live Feishu API.

Mirrors TypeScript: extensions/feishu/src/directory.ts
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .config import ResolvedFeishuAccount

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class FeishuDirectoryPeer:
    """A user (peer) known to the Feishu channel. Mirrors TS FeishuDirectoryPeer."""
    kind: str = "user"
    id: str = ""
    name: str | None = None


@dataclass
class FeishuDirectoryGroup:
    """A group chat known to the Feishu channel. Mirrors TS FeishuDirectoryGroup."""
    kind: str = "group"
    id: str = ""
    name: str | None = None


# ---------------------------------------------------------------------------
# Config-based listings (no API calls)
# ---------------------------------------------------------------------------

def list_feishu_directory_peers(
    account: ResolvedFeishuAccount,
    *,
    query: str | None = None,
    limit: int | None = None,
) -> list[FeishuDirectoryPeer]:
    """
    Return peers from config (allowFrom + dms keys).

    Mirrors TS listFeishuDirectoryPeers().
    """
    from .targets import normalize_feishu_target

    cfg = account  # account has allow_from, dms attrs
    q = (query or "").strip().lower()
    ids: set[str] = set()

    allow_from = getattr(cfg, "allow_from", None) or []
    for entry in allow_from:
        trimmed = str(entry).strip()
        if trimmed and trimmed != "*":
            ids.add(trimmed)

    dms = getattr(cfg, "dms", None) or {}
    for user_id in (dms.keys() if isinstance(dms, dict) else []):
        trimmed = user_id.strip()
        if trimmed:
            ids.add(trimmed)

    results: list[FeishuDirectoryPeer] = []
    for raw in sorted(ids):
        norm = normalize_feishu_target(raw) or raw
        if q and q not in norm.lower():
            continue
        results.append(FeishuDirectoryPeer(kind="user", id=norm))
        if limit and limit > 0 and len(results) >= limit:
            break

    return results


def list_feishu_directory_groups(
    account: ResolvedFeishuAccount,
    *,
    query: str | None = None,
    limit: int | None = None,
) -> list[FeishuDirectoryGroup]:
    """
    Return groups from config (groups keys + groupAllowFrom).

    Mirrors TS listFeishuDirectoryGroups().
    """
    q = (query or "").strip().lower()
    ids: set[str] = set()

    groups = getattr(account, "groups", None) or {}
    for group_id in (groups.keys() if isinstance(groups, dict) else []):
        trimmed = group_id.strip()
        if trimmed and trimmed != "*":
            ids.add(trimmed)

    group_allow_from = getattr(account, "group_allow_from", None) or []
    for entry in group_allow_from:
        trimmed = str(entry).strip()
        if trimmed and trimmed != "*":
            ids.add(trimmed)

    results: list[FeishuDirectoryGroup] = []
    for raw in sorted(ids):
        if q and q not in raw.lower():
            continue
        results.append(FeishuDirectoryGroup(kind="group", id=raw))
        if limit and limit > 0 and len(results) >= limit:
            break

    return results


# ---------------------------------------------------------------------------
# Live listings (API calls, with config fallback)
# ---------------------------------------------------------------------------

async def list_feishu_directory_peers_live(
    account: ResolvedFeishuAccount,
    *,
    query: str | None = None,
    limit: int = 50,
) -> list[FeishuDirectoryPeer]:
    """
    Enumerate users via contact.user.list API, with config-based fallback.

    Mirrors TS listFeishuDirectoryPeersLive().
    """
    if not getattr(account, "app_id", None) or not getattr(account, "app_secret", None):
        return list_feishu_directory_peers(account, query=query, limit=limit)

    try:
        from .client import create_feishu_client
        from lark_oapi.api.contact.v3 import ListUserRequest

        client = create_feishu_client(account)
        q = (query or "").strip().lower()
        peers: list[FeishuDirectoryPeer] = []
        page_size = min(limit, 50)

        loop = asyncio.get_running_loop()
        request = (
            ListUserRequest.builder()
            .page_size(page_size)
            .build()
        )
        response = await loop.run_in_executor(
            None, lambda: client.contact.v3.user.list(request)
        )

        if response.success() and response.data and response.data.items:
            for user in response.data.items:
                open_id = getattr(user, "open_id", "") or ""
                name = getattr(user, "name", "") or ""
                if not open_id:
                    continue
                if q and q not in open_id.lower() and q not in name.lower():
                    continue
                peers.append(FeishuDirectoryPeer(kind="user", id=open_id, name=name or None))
                if len(peers) >= limit:
                    break

        return peers

    except Exception as exc:
        logger.debug("[feishu] listFeishuDirectoryPeersLive error: %s — falling back to config", exc)
        return list_feishu_directory_peers(account, query=query, limit=limit)


async def list_feishu_directory_groups_live(
    account: ResolvedFeishuAccount,
    *,
    query: str | None = None,
    limit: int = 50,
) -> list[FeishuDirectoryGroup]:
    """
    Enumerate group chats via im.chat.list API, with config-based fallback.

    Mirrors TS listFeishuDirectoryGroupsLive().
    """
    if not getattr(account, "app_id", None) or not getattr(account, "app_secret", None):
        return list_feishu_directory_groups(account, query=query, limit=limit)

    try:
        from .client import create_feishu_client
        from lark_oapi.api.im.v1 import ListChatRequest

        client = create_feishu_client(account)
        q = (query or "").strip().lower()
        groups: list[FeishuDirectoryGroup] = []
        page_size = min(limit, 100)

        loop = asyncio.get_running_loop()
        request = ListChatRequest.builder().page_size(page_size).build()
        response = await loop.run_in_executor(
            None, lambda: client.im.v1.chat.list(request)
        )

        if response.success() and response.data and response.data.items:
            for chat in response.data.items:
                chat_id = getattr(chat, "chat_id", "") or ""
                name = getattr(chat, "name", "") or ""
                if not chat_id:
                    continue
                if q and q not in chat_id.lower() and q not in name.lower():
                    continue
                groups.append(FeishuDirectoryGroup(kind="group", id=chat_id, name=name or None))
                if len(groups) >= limit:
                    break

        return groups

    except Exception as exc:
        logger.debug("[feishu] listFeishuDirectoryGroupsLive error: %s — falling back to config", exc)
        return list_feishu_directory_groups(account, query=query, limit=limit)
