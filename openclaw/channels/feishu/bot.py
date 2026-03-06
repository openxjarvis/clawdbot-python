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
# Sender name resolution
# ---------------------------------------------------------------------------

async def _resolve_sender_name(
    client: Any,
    sender_id: str,
    account_id: str,
) -> str | None:
    """Fetch display name for a sender, with TTL cache. Mirrors TS senderNameCache."""
    cache_key = f"{account_id}:{sender_id}"
    cached = _sender_name_cache.get(cache_key)
    if cached:
        name, expire_at = cached
        if time.time() < expire_at:
            return name

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
                return name
    except Exception as e:
        logger.debug("[feishu] Failed to resolve sender name for %s: %s", sender_id, e)

    return None


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

    # 6. Resolve sender display name
    sender_name = ""
    if account.resolve_sender_names:
        sender_name = await _resolve_sender_name(client, sender_id, account.account_id) or ""

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

    # 13. Dispatch
    inbound = InboundMessage(
        channel_id=channel_id,
        message_id=message_id,
        sender_id=sender_id,
        sender_name=sender_name,
        chat_id=chat_id + scope_suffix,
        chat_type=chat_type_label,
        text=text,
        timestamp=str(int(message_ts)),
        reply_to=parent_id or None,
        account_id=account.account_id,
        attachments=attachments,
        metadata={
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
        },
    )

    logger.info(
        "[feishu] 📨 Message from %s (account=%s chat=%s): %s",
        sender_name or sender_id,
        account.account_id,
        chat_type_label,
        text[:80] if text else f"[{msg_type}]",
    )
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
