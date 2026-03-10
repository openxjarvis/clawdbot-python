"""Core inbound message handler for Feishu channel.

Receives raw Feishu events and converts them into InboundMessage objects,
enforcing dedup, policy (dm/group), mention filtering, and media download.

Mirrors TypeScript: extensions/feishu/src/bot.ts
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Awaitable

from ..base import ChatAttachment, InboundMessage
from .dedup import get_dedup
from .media import download_message_resource
from .mention import (
    extract_message_body,
    is_bot_mentioned,
    parse_mentions,
)
from .policy import (
    is_feishu_group_allowed,
    resolve_feishu_dm_policy,
    resolve_feishu_group_config,
    resolve_feishu_group_sender_allowed,
    resolve_feishu_reply_policy,
)
from .post import parse_post_content, parse_text_content

if TYPE_CHECKING:
    from .config import ResolvedFeishuAccount

logger = logging.getLogger(__name__)

# Sender name cache: {account_id:sender_id → (name, expire_at)}
_SENDER_NAME_TTL = 10 * 60  # 10 minutes
_sender_name_cache: dict[str, tuple[str, float]] = {}


# ---------------------------------------------------------------------------
# Permission error extraction — mirrors TS extractPermissionError in bot.ts
# ---------------------------------------------------------------------------

_IGNORED_PERMISSION_SCOPE_TOKENS = ["contact:contact.base:readonly"]

# Feishu API sometimes returns incorrect scope names in permission error responses.
# This map corrects known mismatches — mirrors TS FEISHU_SCOPE_CORRECTIONS.
_FEISHU_SCOPE_CORRECTIONS: dict[str, str] = {
    "contact:contact.base:readonly": "contact:user.base:readonly",
}

_PERMISSION_ERROR_COOLDOWN_S = 5 * 60  # 5 minutes
# Per-appId cache: {app_id → last_notified_timestamp}
_permission_error_notified_at: dict[str, float] = {}


def _correct_feishu_scope_in_url(url: str) -> str:
    """Apply known scope-name corrections to a Feishu permission grant URL."""
    from urllib.parse import quote, unquote
    corrected = url
    for wrong, right in _FEISHU_SCOPE_CORRECTIONS.items():
        corrected = corrected.replace(quote(wrong, safe=""), quote(right, safe=""))
        corrected = corrected.replace(wrong, right)
    return corrected


def _should_suppress_permission_error(message: str) -> bool:
    """Return True for known-spurious permission scope tokens that should be ignored."""
    msg_lower = message.lower()
    return any(token in msg_lower for token in _IGNORED_PERMISSION_SCOPE_TOKENS)


@dataclass
class _PermissionError:
    code: int
    message: str
    grant_url: str | None = None


def _extract_permission_error(err: Any) -> "_PermissionError | None":
    """Extract Feishu permission error (code 99991672) from an API exception.

    Mirrors TS extractPermissionError in extensions/feishu/src/bot.ts.
    Supports both lark-oapi exception shapes and raw dict response data.
    """
    if err is None:
        return None

    import re as _re

    # Try to extract code + message from common lark-oapi error shapes
    code: int | None = None
    msg: str = ""

    # lark_oapi response objects: err.code / err.msg
    if hasattr(err, "code") and hasattr(err, "msg"):
        code = getattr(err, "code", None)
        msg = str(getattr(err, "msg", "") or "")
    # Dict-like (e.g. from response.data)
    elif isinstance(err, dict):
        code = err.get("code")
        msg = str(err.get("msg", "") or "")
    # Exception with response attribute (requests/httpx style)
    elif hasattr(err, "response"):
        resp = err.response
        data = getattr(resp, "data", None) if resp else None
        if isinstance(data, dict):
            code = data.get("code")
            msg = str(data.get("msg", "") or "")
        elif hasattr(resp, "json"):
            try:
                data = resp.json()
                if isinstance(data, dict):
                    code = data.get("code")
                    msg = str(data.get("msg", "") or "")
            except Exception:
                pass
    # Exception message may contain error JSON
    else:
        try:
            err_str = str(err)
            # Look for "code":99991672 in the string
            if "99991672" not in err_str:
                return None
            _json_match = _re.search(r'\{[^{}]*"code"\s*:\s*99991672[^{}]*\}', err_str)
            if _json_match:
                data = json.loads(_json_match.group())
                code = data.get("code")
                msg = str(data.get("msg", "") or "")
        except Exception:
            return None

    if code != 99991672:
        return None

    # Extract grant URL from the message text
    url_match = _re.search(r"https://[^\s,]+/app/[^\s,]+", msg)
    grant_url = _correct_feishu_scope_in_url(url_match.group()) if url_match else None

    return _PermissionError(code=code, message=msg, grant_url=grant_url)


# ---------------------------------------------------------------------------
# Broadcast dispatch helpers — mirrors TS resolveBroadcastAgents / buildBroadcastSessionKey
# ---------------------------------------------------------------------------

def resolve_broadcast_agents(config: Any, peer_id: str) -> list[str] | None:
    """Return broadcast agent list for a given group peer_id, or None if not configured.

    Reads config.broadcast[peer_id] — a list of agent IDs to fan out to.
    Mirrors TS resolveBroadcastAgents in extensions/feishu/src/bot.ts.
    """
    if config is None:
        return None
    broadcast = None
    if hasattr(config, "broadcast"):
        broadcast = config.broadcast
    elif isinstance(config, dict):
        broadcast = config.get("broadcast")
    if not broadcast:
        return None
    if hasattr(broadcast, "__getitem__"):
        agents = broadcast.get(peer_id) if hasattr(broadcast, "get") else None
    else:
        return None
    if not agents or not isinstance(agents, (list, tuple)) or len(agents) == 0:
        return None
    return [str(a) for a in agents]


def build_broadcast_session_key(base_session_key: str, original_agent_id: str, target_agent_id: str) -> str:
    """Rewrite the agent ID prefix of a session key for a broadcast target agent.

    Session keys follow: agent:<agentId>:<channel>:<peerKind>:<peerId>
    Mirrors TS buildBroadcastSessionKey in extensions/feishu/src/bot.ts.
    """
    prefix = f"agent:{original_agent_id}:"
    if base_session_key.startswith(prefix):
        return f"agent:{target_agent_id}:{base_session_key[len(prefix):]}"
    return base_session_key


# Persistent broadcast dedup (cross-account): message_id → claimed_at timestamp
_broadcast_claimed: dict[str, float] = {}
_BROADCAST_CLAIM_TTL_S = 60 * 5  # 5 minutes


def _try_claim_broadcast(message_id: str) -> bool:
    """Claim a message for broadcast dispatch. Returns True if this process is the first claimer.

    Mirrors TS tryRecordMessagePersistent(ctx.messageId, "broadcast", log).
    Uses an in-process dict; for multi-process setups a shared store would be needed.
    """
    now = time.time()
    # Purge stale entries
    stale = [k for k, v in _broadcast_claimed.items() if now - v > _BROADCAST_CLAIM_TTL_S]
    for k in stale:
        del _broadcast_claimed[k]
    if message_id in _broadcast_claimed:
        return False
    _broadcast_claimed[message_id] = now
    return True


# ---------------------------------------------------------------------------
# Sender name resolution
# ---------------------------------------------------------------------------

@dataclass
class _SenderNameResult:
    name: str | None = None
    permission_error: "_PermissionError | None" = None


async def _resolve_sender_name(
    client: Any,
    sender_id: str,
    account_id: str,
) -> _SenderNameResult:
    """Fetch display name for a sender, with TTL cache.

    Returns a _SenderNameResult containing the name (if resolved) and any
    permission error encountered during the API call.
    Mirrors TS resolveFeishuSenderName in extensions/feishu/src/bot.ts.
    """
    cache_key = f"{account_id}:{sender_id}"
    cached = _sender_name_cache.get(cache_key)
    if cached:
        name, expire_at = cached
        if time.time() < expire_at:
            return _SenderNameResult(name=name)

    try:
        id_type = "open_id" if sender_id.startswith("ou_") else "user_id"
        from lark_oapi.api.contact.v3 import GetUserRequest

        loop = asyncio.get_running_loop()
        request = (
            GetUserRequest.builder()
            .user_id_type(id_type)
            .user_id(sender_id)
            .build()
        )
        response = await loop.run_in_executor(None, lambda: client.contact.v3.user.get(request))
        if response.success() and response.data and response.data.user:
            name = response.data.user.name or response.data.user.en_name or ""
            if name:
                _sender_name_cache[cache_key] = (name, time.time() + _SENDER_NAME_TTL)
                return _SenderNameResult(name=name)
        # Check if response itself is a permission error
        if not response.success():
            perm_err = _extract_permission_error(response)
            if perm_err is None and hasattr(response, "code"):
                perm_err = _PermissionError(
                    code=int(response.code),
                    message=str(getattr(response, "msg", "") or ""),
                ) if getattr(response, "code", None) == 99991672 else None
            if perm_err:
                return _SenderNameResult(permission_error=perm_err)
    except Exception as e:
        perm_err = _extract_permission_error(e)
        if perm_err:
            if _should_suppress_permission_error(perm_err.message):
                logger.debug("[feishu] Suppressing stale permission scope error: %s", perm_err.message)
                return _SenderNameResult()
            logger.debug("[feishu] Permission error resolving sender name: code=%s", perm_err.code)
            return _SenderNameResult(permission_error=perm_err)
        logger.debug("[feishu] Failed to resolve sender name for %s: %s", sender_id, e)

    return _SenderNameResult()


# ---------------------------------------------------------------------------
# Pairing helpers
# ---------------------------------------------------------------------------

async def _get_pairing_allow_from(channel_id: str) -> list[str]:
    """Read the pairing store for this channel to get paired sender IDs."""
    try:
        from openclaw.pairing.pairing_store import read_channel_allow_from_store
        return list(await asyncio.get_running_loop().run_in_executor(
            None, lambda: read_channel_allow_from_store(channel_id)
        ))
    except Exception:
        return []


async def _maybe_create_dynamic_agent(
    sender_id: str,
    account: Any,
) -> None:
    """Attempt to create a dynamic agent workspace for a new DM sender.

    Mirrors TS maybeCreateDynamicAgent() — only creates if the workspace
    doesn't already exist and max_agents limit hasn't been reached.
    Silently skips if the dynamic_agent module is unavailable.
    """
    try:
        from openclaw.agents.dynamic_agent import maybe_create_dynamic_agent  # type: ignore
        cfg = account.dynamic_agent_creation
        await maybe_create_dynamic_agent(
            sender_id=sender_id,
            workspace_template=cfg.workspace_template,
            agent_dir_template=cfg.agent_dir_template,
            max_agents=cfg.max_agents,
        )
    except ImportError:
        pass  # dynamic_agent module not yet available
    except Exception as e:
        logger.debug(
            "[feishu] Dynamic agent creation failed for sender %s: %s", sender_id, e
        )


async def _send_pairing_reply(
    client: Any,
    chat_id: str,
    sender_id: str,
    channel_id: str,
) -> None:
    """Send a pairing code to an unknown DM sender."""
    try:
        from openclaw.pairing.pairing_store import upsert_channel_pairing_request
        from openclaw.pairing.messages import format_pairing_request_message
        from lark_oapi.api.im.v1 import (
            CreateMessageRequest, CreateMessageRequestBody,
        )

        loop = asyncio.get_running_loop()
        pairing_info = await loop.run_in_executor(
            None, lambda: upsert_channel_pairing_request(channel_id, sender_id)
        )
        code = pairing_info.get("code", "")
        if not code:
            logger.debug("[feishu] Pairing cap reached for sender %s, no code issued", sender_id)
            return

        msg = format_pairing_request_message(code, channel_id, id_label="Feishu user ID")

        content = json.dumps({"text": msg})
        request = (
            CreateMessageRequest.builder()
            .receive_id_type("open_id")
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(sender_id)
                .content(content)
                .msg_type("text")
                .build()
            )
            .build()
        )
        await loop.run_in_executor(None, lambda: client.im.v1.message.create(request))
        logger.info("[feishu] Sent pairing request to sender %s (code=%s)", sender_id, code)
    except Exception as e:
        logger.warning("[feishu] Failed to send pairing reply to %s: %s", sender_id, e)


# ---------------------------------------------------------------------------
# Merge-forward expansion helper
# ---------------------------------------------------------------------------

async def _expand_merge_forward(
    client: Any,
    content_raw: str,
    fallback_msg_id: str,
) -> str:
    """Expand a merge_forward message into readable text.

    Feishu merge_forward messages carry a list of sub-message IDs in their
    content.  We fetch each via im.message.get and extract the text.

    Mirrors TS merge_forward handling in extensions/feishu/src/bot.ts:
      - Parse msg_id_list from content JSON
      - Fetch each sub-message via GetMessageRequest
      - Join their text bodies sorted by create_time
      - Fall back to a placeholder on any error

    Returns the combined text, or a fallback string if expansion fails.
    """
    try:
        from lark_oapi.api.im.v1 import GetMessageRequest

        content_dict = json.loads(content_raw) if content_raw else {}
        # Feishu merge_forward content has "msg_id_list" or "message_id_list"
        msg_ids: list[str] = (
            content_dict.get("msg_id_list")
            or content_dict.get("message_id_list")
            or []
        )
        if not msg_ids:
            return "[Merged and Forwarded Message]"

        loop = asyncio.get_running_loop()
        items_with_ts: list[tuple[int, str]] = []

        # Fetch up to 20 sub-messages to avoid excessive API calls
        for mid in msg_ids[:20]:
            try:
                req = GetMessageRequest.builder().message_id(mid).build()
                resp = await loop.run_in_executor(
                    None,
                    lambda r=req: client.im.v1.message.get(r),
                )
                if not resp.success() or not resp.data:
                    continue
                items = getattr(resp.data, "items", None) or []
                for item in items:
                    create_time_raw = getattr(item, "create_time", None) or 0
                    try:
                        ts = int(create_time_raw)
                    except (ValueError, TypeError):
                        ts = 0
                    body = getattr(item, "body", None)
                    if not body:
                        continue
                    c_raw = getattr(body, "content", "") or ""
                    if not c_raw:
                        continue
                    try:
                        cd = json.loads(c_raw)
                        t = cd.get("text", "") or ""
                        if t:
                            items_with_ts.append((ts, t))
                    except (json.JSONDecodeError, TypeError):
                        # Non-text content: skip (images/files in merged messages)
                        pass
            except Exception as _item_err:
                logger.debug("[feishu] merge_forward: failed to fetch %s: %s", mid, _item_err)

        if items_with_ts:
            items_with_ts.sort(key=lambda x: x[0])
            combined = "\n".join(t for _, t in items_with_ts)
            return f"[Merged and Forwarded Messages]\n{combined}"

        return "[Merged and Forwarded Message]"

    except Exception as exc:
        logger.warning("[feishu] merge_forward expansion failed for %s: %s", fallback_msg_id, exc)
        return "[Merged and Forwarded Message - fetch error]"


# ---------------------------------------------------------------------------
# Main inbound message handler
# ---------------------------------------------------------------------------

async def handle_feishu_message(
    event: Any,   # P2ImMessageReceiveV1
    client: Any,
    account: ResolvedFeishuAccount,
    bot_open_id: str | None,
    message_handler: Callable[[InboundMessage], Awaitable[None]],
    channel_id: str,
) -> None:
    """
    Process an inbound im.message.receive_v1 event.

    Steps:
      1. Dedup check
      2. Parse message content (text/post/image/file/audio/video/sticker)
      3. DM vs group routing
      4. Policy checks (dmPolicy / groupPolicy / allowlist)
      5. Mention gating in groups (requireMention)
      6. Build InboundMessage and dispatch to handler

    Mirrors TS handleFeishuMessage().
    """
    evt = event.event
    if evt is None:
        return

    msg = evt.message
    sender = evt.sender

    if msg is None or sender is None:
        return

    message_id: str = msg.message_id or ""
    chat_id: str = msg.chat_id or ""
    chat_type: str = msg.chat_type or "p2p"  # "p2p" or "group"
    msg_type: str = msg.message_type or "text"
    # lark_oapi EventMessage has `content` directly on the object (no .body wrapper)
    content_raw: str = msg.content or ""

    # Extract sender IDs
    sender_id_obj = sender.sender_id
    open_id: str = getattr(sender_id_obj, "open_id", "") or ""
    user_id: str = getattr(sender_id_obj, "user_id", "") or ""
    union_id: str = getattr(sender_id_obj, "union_id", "") or ""

    # Use open_id as primary sender_id, fall back to user_id
    sender_id: str = open_id or user_id or ""
    sender_ids: list[str] = [s for s in [open_id, user_id, union_id] if s]

    if not sender_id or not message_id or not chat_id:
        return

    # Message timestamp (ms → seconds); create_time is int in lark_oapi EventMessage
    create_time_raw = getattr(msg, "create_time", None)
    try:
        message_ts = int(create_time_raw) / 1000 if create_time_raw else time.time()
    except (ValueError, TypeError):
        message_ts = time.time()

    # 1. Dedup
    dedup = get_dedup(account.account_id)
    if not dedup.try_record(message_id):
        logger.debug("[feishu] Duplicate message %s skipped", message_id)
        return

    # 2. Parse mentions
    mentions = parse_mentions(getattr(msg, "mentions", None))
    is_p2p = chat_type == "p2p"

    # 3. Bot mention check
    bot_mentioned = is_bot_mentioned(mentions, bot_open_id) if (bot_open_id and mentions) else False

    # 3b. @_all in group also counts as a bot mention (mirrors TS @_all handling).
    # Feishu sends @_all as a special mention in the raw content JSON.
    if not bot_mentioned and not is_p2p:
        try:
            _raw_for_all_check = content_raw or ""
            if "@_all" in _raw_for_all_check or "@all" in _raw_for_all_check.lower():
                bot_mentioned = True
        except Exception:
            pass

    # 4. Skip messages from the bot itself
    if bot_open_id and open_id == bot_open_id:
        return

    # 5. Route: DM vs group
    if is_p2p:
        # DM policy check
        pairing_allow_from = await _get_pairing_allow_from(channel_id)
        allowed, reason = resolve_feishu_dm_policy(
            account,
            sender_id,
            sender_ids=sender_ids,
            pairing_allow_from=pairing_allow_from,
        )
        if not allowed:
            if account.dm_policy == "pairing":
                await _send_pairing_reply(client, chat_id, sender_id, channel_id)
            logger.debug("[feishu] DM from %s blocked: %s", sender_id, reason)
            return
    else:
        # Group policy check
        if not is_feishu_group_allowed(account, chat_id):
            return

        if not resolve_feishu_group_sender_allowed(
            account, chat_id, sender_id, sender_ids=sender_ids
        ):
            return

        group_cfg = resolve_feishu_group_config(account, chat_id)
        if not group_cfg.get("enabled", True):
            return

        require_mention = group_cfg.get("require_mention", account.require_mention)
        if require_mention and not bot_mentioned:
            # Not mentioned in a group that requires mention — skip silently
            return

    # 5b. Dynamic agent creation for new DM senders
    if is_p2p and account.dynamic_agent_creation.enabled:
        asyncio.create_task(
            _maybe_create_dynamic_agent(sender_id, account)
        )

    # 6. Resolve sender display name (best-effort) + check for permission errors
    # Mirrors TS resolveFeishuSenderName + permissionErrorForAgent logic in bot.ts.
    sender_name = ""
    permission_error_for_agent: "_PermissionError | None" = None
    if account.resolve_sender_names:
        _name_result = await _resolve_sender_name(client, sender_id, account.account_id)
        sender_name = _name_result.name or ""
        if _name_result.permission_error:
            app_key = getattr(account, "app_id", None) or account.account_id or "default"
            now = time.time()
            last_notified = _permission_error_notified_at.get(app_key, 0.0)
            if now - last_notified > _PERMISSION_ERROR_COOLDOWN_S:
                _permission_error_notified_at[app_key] = now
                permission_error_for_agent = _name_result.permission_error

    # 7. Parse message content → text + attachments
    text = ""
    attachments: list[ChatAttachment] = []

    if msg_type == "text":
        text = parse_text_content(content_raw)

    elif msg_type == "post":
        result = parse_post_content(content_raw)
        text = result.text
        for ref in result.media_refs:
            attachments.append(ChatAttachment(
                type=ref.type,
                url=ref.image_key or ref.file_key,
            ))

    elif msg_type == "image":
        try:
            content_dict = json.loads(content_raw) if content_raw else {}
            image_key = content_dict.get("image_key", "")
        except (json.JSONDecodeError, TypeError):
            image_key = ""
        if image_key:
            img_bytes = await download_message_resource(
                client, message_id, image_key, "image",
                max_mb=account.media_max_mb,
            )
            if img_bytes:
                attachments.append(ChatAttachment(
                    type="image",
                    content=_to_b64(img_bytes),
                    mime_type="image/jpeg",
                    filename=f"{image_key}.jpg",
                    size=len(img_bytes),
                ))

    elif msg_type in {"file", "audio", "media"}:
        try:
            content_dict = json.loads(content_raw) if content_raw else {}
            file_key = content_dict.get("file_key", "")
            file_name = content_dict.get("file_name", f"file_{message_id}")
        except (json.JSONDecodeError, TypeError):
            file_key, file_name = "", ""
        if file_key:
            file_bytes = await download_message_resource(
                client, message_id, file_key, "file",
                max_mb=account.media_max_mb,
            )
            if file_bytes:
                a_type = "audio" if msg_type == "audio" else ("video" if msg_type == "media" else "file")
                attachments.append(ChatAttachment(
                    type=a_type,
                    content=_to_b64(file_bytes),
                    filename=file_name,
                    size=len(file_bytes),
                ))

    elif msg_type == "sticker":
        try:
            content_dict = json.loads(content_raw) if content_raw else {}
            file_key = content_dict.get("file_key", "")
        except (json.JSONDecodeError, TypeError):
            file_key = ""
        if file_key:
            attachments.append(ChatAttachment(type="sticker", url=file_key))

    elif msg_type == "merge_forward":
        # Merge-forward messages: fetch sub-messages via im.message.get API.
        # The content carries a list of sub-message IDs that we expand into text.
        # Mirrors TS merge_forward handling in extensions/feishu/src/bot.ts.
        text = await _expand_merge_forward(client, content_raw, message_id)

    # 8. Strip bot @mention from text
    if mentions:
        text = extract_message_body(text, mentions, bot_open_id=bot_open_id)

    # 9. Determine chat_type label
    chat_type_label = "direct" if is_p2p else "group"

    # 10. Reply-in-thread / session scope metadata
    reply_policy = resolve_feishu_reply_policy(
        account,
        chat_id,
        message_id,
        is_group=not is_p2p,
    )

    # 11. Build root_id / parent_id for thread context
    root_id: str = getattr(msg, "root_id", "") or ""
    parent_id: str = getattr(msg, "parent_id", "") or ""
    thread_id: str = root_id or parent_id or ""

    # 12. Build session scope key suffix
    group_cfg_for_scope = resolve_feishu_group_config(account, chat_id) if not is_p2p else {}
    scope = group_cfg_for_scope.get("group_session_scope", account.group_session_scope)
    scope_suffix = _build_scope_suffix(
        scope, chat_id, sender_id, thread_id, is_p2p
    )

    # 13. Inject permission error notice into message body.
    # When Feishu API returns code 99991672 during sender name resolution, the agent
    # is notified so it can inform the user about the permission grant URL.
    # Mirrors TS buildFeishuAgentBody permissionErrorForAgent injection in bot.ts.
    effective_text = text
    if permission_error_for_agent:
        grant_url = permission_error_for_agent.grant_url or ""
        _perm_notice = (
            f"\n\n[System: The bot encountered a Feishu API permission error. "
            f"Please inform the user about this issue and provide the permission grant URL "
            f"for the admin to authorize. Permission grant URL: {grant_url}]"
        )
        effective_text = (effective_text or "") + _perm_notice

    # 14. Resolve broadcast agents for group messages.
    # Mirrors TS resolveBroadcastAgents + broadcast dispatch in bot.ts.
    broadcast_agents: list[str] | None = None
    if not is_p2p:
        try:
            from openclaw.config.loader import load_config as _lc
            _cfg = _lc()
            broadcast_agents = resolve_broadcast_agents(_cfg, chat_id)
        except Exception as _be:
            logger.debug("[feishu] broadcast config lookup failed: %s", _be)

    # 15. Build inbound message
    _meta: dict[str, Any] = {
        "feishu_account_id": account.account_id,
        "feishu_chat_id": chat_id,
        "feishu_message_id": message_id,
        "feishu_open_id": open_id,
        "feishu_user_id": user_id,
        "feishu_msg_type": msg_type,
        "feishu_root_id": root_id,
        "feishu_parent_id": parent_id,
        "feishu_reply_in_thread": reply_policy.get("reply_in_thread", False),
        "feishu_is_p2p": is_p2p,
        "feishu_bot_mentioned": bot_mentioned,
    }

    inbound = InboundMessage(
        channel_id=channel_id,
        message_id=message_id,
        sender_id=sender_id,
        sender_name=sender_name,
        chat_id=chat_id + scope_suffix,
        chat_type=chat_type_label,
        text=effective_text,
        timestamp=str(int(message_ts)),
        reply_to=parent_id or None,
        account_id=account.account_id,
        attachments=attachments,
        metadata=_meta,
    )

    logger.info(
        "[feishu] 📨 Message from %s (account=%s chat=%s): %s",
        sender_name or sender_id,
        account.account_id,
        chat_type_label,
        text[:80] if text else f"[{msg_type}]",
    )

    # 16. Dispatch: broadcast or single-agent
    if broadcast_agents:
        # Cross-account dedup: only one process/account handles broadcast dispatch.
        # Mirrors TS tryRecordMessagePersistent(ctx.messageId, "broadcast").
        if not _try_claim_broadcast(message_id):
            logger.debug(
                "[feishu] broadcast already claimed for message %s (account=%s); skipping",
                message_id, account.account_id,
            )
            return

        logger.info(
            "[feishu] Broadcasting message %s to %d agents: %s",
            message_id, len(broadcast_agents), broadcast_agents,
        )

        # Determine the "active" agent (the one that responds on Feishu).
        # Other agents receive the message as silent observers.
        # The active agent is the one that matches the normal route.
        from openclaw.routing.resolve_route import resolve_agent_route
        from openclaw.config.loader import load_config as _lc2
        _route_cfg = _lc2()
        _peer_kind = "group" if chat_type_label == "group" else "direct"
        try:
            _route = resolve_agent_route(
                cfg=_route_cfg,
                channel=channel_id,
                account_id=account.account_id,
                peer={"kind": _peer_kind, "id": chat_id},
            )
            original_agent_id = _route.agent_id
            base_session_key = _route.session_key
        except Exception as _re:
            logger.warning("[feishu] broadcast: route resolution failed: %s", _re)
            original_agent_id = "main"
            base_session_key = f"agent:main:{channel_id}:{_peer_kind}:{chat_id}"

        async def _dispatch_to_agent(agent_id: str) -> None:
            agent_session_key = build_broadcast_session_key(
                base_session_key, original_agent_id, agent_id
            )
            # Build a per-agent InboundMessage carrying the broadcast target agent ID.
            # channel_manager reads feishu_broadcast_agent_id to override the routed agent.
            agent_meta = dict(_meta)
            agent_meta["feishu_broadcast_agent_id"] = agent_id
            agent_meta["feishu_broadcast_session_key"] = agent_session_key
            agent_inbound = InboundMessage(
                channel_id=channel_id,
                message_id=message_id,
                sender_id=sender_id,
                sender_name=sender_name,
                chat_id=chat_id + scope_suffix,
                chat_type=chat_type_label,
                text=effective_text,
                timestamp=str(int(message_ts)),
                reply_to=parent_id or None,
                account_id=account.account_id,
                attachments=attachments,
                metadata=agent_meta,
            )
            try:
                await message_handler(agent_inbound)
            except Exception as _de:
                logger.error(
                    "[feishu] broadcast dispatch failed for agent=%s: %s",
                    agent_id, _de, exc_info=True,
                )

        await asyncio.gather(*[_dispatch_to_agent(aid) for aid in broadcast_agents])
    else:
        try:
            await message_handler(inbound)
        except Exception as e:
            logger.error("[feishu] Message handler error for %s: %s", message_id, e, exc_info=True)


# ---------------------------------------------------------------------------
# Card action handler (converts button click to synthetic message)
# ---------------------------------------------------------------------------

async def handle_feishu_card_action(
    event: Any,  # P2CardActionTrigger
    client: Any,
    account: ResolvedFeishuAccount,
    bot_open_id: str | None,
    message_handler: Callable[[InboundMessage], Awaitable[None]],
    channel_id: str,
) -> None:
    """
    Convert a card button action into a synthetic InboundMessage.

    When the agent sends a card with buttons (via [[buttons:...]] directive),
    pressing a button triggers this handler. It:
      1. Immediately patches the original card to disable all buttons — prevents
         double-press and gives instant visual feedback (mirrors TS bot-handlers.ts).
      2. Dispatches a synthetic InboundMessage to the agent so it can respond.

    Mirrors TS handleFeishuCardAction().
    """
    try:
        action = event.event
        operator = getattr(action, "operator", None)
        if not operator:
            return

        sender_id = (
            getattr(operator, "open_id", "") or
            getattr(operator, "user_id", "") or ""
        )
        if not sender_id:
            return

        # Action value: dict of button action parameters
        action_val = getattr(action, "action", None)
        if not action_val:
            return

        value: dict[str, Any] = getattr(action_val, "value", {}) or {}
        # Prefer the "callback" field set by card_builder.build_button_card(),
        # fall back to "text" or the whole value as JSON.
        callback = value.get("callback") or value.get("text") or json.dumps(value)
        text = callback  # what gets sent to the agent as the synthetic message

        # Get context for chat_id and message_id
        context = getattr(action, "context", None)
        chat_id = getattr(context, "open_chat_id", "") if context else ""
        message_id = getattr(context, "open_message_id", "") if context else ""

        if not chat_id:
            return

        # --- Disable buttons immediately (visual feedback, prevent double-press) ---
        # Fetch the original card content, rebuild it with all buttons disabled,
        # and PATCH the message. Done fire-and-forget so we don't delay the agent.
        if message_id:
            async def _disable_buttons() -> None:
                try:
                    from .send import get_feishu_message, patch_feishu_card
                    from .card_builder import build_card_with_disabled_buttons
                    msg_data = await get_feishu_message(client, message_id)
                    if msg_data:
                        raw_content = msg_data.get("body", {}).get("content", "")
                        if raw_content:
                            try:
                                card_json = json.loads(raw_content)
                                disabled_card = build_card_with_disabled_buttons(
                                    card_json, selected_callback=callback
                                )
                                await patch_feishu_card(client, message_id, disabled_card)
                            except Exception as _pe:
                                logger.debug("[feishu] Card disable patch error: %s", _pe)
                except Exception as _de:
                    logger.debug("[feishu] Card disable fetch error: %s", _de)

            asyncio.create_task(_disable_buttons())

        inbound = InboundMessage(
            channel_id=channel_id,
            message_id=f"card_action_{message_id}_{int(time.time()*1000)}",
            sender_id=sender_id,
            sender_name="",
            chat_id=chat_id,
            chat_type="group" if chat_id.startswith("oc_") else "direct",
            text=text,
            timestamp=str(int(time.time())),
            metadata={
                "feishu_account_id": account.account_id,
                "feishu_is_card_action": True,
                "feishu_action_value": value,
                "feishu_action_callback": callback,
            },
        )

        await message_handler(inbound)
    except Exception as e:
        logger.debug("[feishu] Card action handler error: %s", e)


# ---------------------------------------------------------------------------
# Reaction-as-message handler
# ---------------------------------------------------------------------------

async def handle_feishu_reaction(
    event: Any,
    client: Any,
    account: ResolvedFeishuAccount,
    bot_open_id: str | None,
    message_handler: Callable[[InboundMessage], Awaitable[None]],
    channel_id: str,
    *,
    is_own_message: bool,
) -> None:
    """
    Convert a reaction event on a bot message to a synthetic InboundMessage.

    reactionNotifications:
      "off"  → never
      "own"  → only on bot's own messages
      "all"  → any message

    Mirrors TS reaction event handling in monitor.account.ts.
    """
    mode = account.reaction_notifications
    if mode == "off":
        return
    if mode == "own" and not is_own_message:
        return

    try:
        evt = event.event
        user_id_obj = getattr(evt, "user_id", None)
        open_id = getattr(user_id_obj, "open_id", "") or "" if user_id_obj else ""
        reaction_type = getattr(getattr(evt, "reaction_type", None), "emoji_type", "") or ""
        message_id = getattr(evt, "message_id", "") or ""

        if not open_id or not message_id:
            return

        # Skip the Typing emoji (our own indicator)
        if reaction_type == "Typing":
            return

        text = f"[reaction:{reaction_type}]"
        inbound = InboundMessage(
            channel_id=channel_id,
            message_id=f"reaction_{message_id}_{open_id}_{int(time.time()*1000)}",
            sender_id=open_id,
            sender_name="",
            chat_id=message_id,
            chat_type="direct",
            text=text,
            timestamp=str(int(time.time())),
            metadata={
                "feishu_account_id": account.account_id,
                "feishu_is_reaction": True,
                "feishu_reaction_type": reaction_type,
                "feishu_message_id": message_id,
            },
        )
        await message_handler(inbound)
    except Exception as e:
        logger.debug("[feishu] Reaction handler error: %s", e)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_b64(data: bytes) -> str:
    import base64
    return base64.b64encode(data).decode("ascii")


def _build_scope_suffix(
    scope: str,
    chat_id: str,
    sender_id: str,
    thread_id: str,
    is_p2p: bool,
) -> str:
    """
    Build a suffix for the chat_id to scope sessions correctly.

    Mirrors TS groupSessionScope logic.
    """
    if is_p2p:
        return ""
    if scope == "group":
        return ""
    if scope == "group_sender":
        return f":{sender_id}"
    if scope == "group_topic":
        return f":{thread_id}" if thread_id else ""
    if scope == "group_topic_sender":
        if thread_id:
            return f":{thread_id}:{sender_id}"
        return f":{sender_id}"
    return ""
