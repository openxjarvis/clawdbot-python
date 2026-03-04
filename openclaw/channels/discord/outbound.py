"""
Discord outbound sending.
Mirrors src/discord/send.outbound.ts and src/discord/send.messages.ts.

Functions:
  send_discord_text()    — chunked text (2000 chars / 17 lines), reply-to support
  send_discord_media()   — download + multipart file upload, caption
  send_discord_poll()    — Discord native polls
  send_discord_sticker() — send sticker by ID
  send_discord_webhook() — execute a webhook (webhookId + webhookToken)
  send_discord_embed()   — send rich embed
  edit_discord_message() — edit an existing message
  delete_discord_message() — delete a message

Target resolution mirrors parseAndResolveRecipient + resolveChannelId in TS:
  "user:<snowflake>"    → open DM channel
  "channel:<snowflake>" → use channel directly
  bare snowflake        → try as channel, fall back to DM
"""
from __future__ import annotations

import asyncio
import io
import logging
from typing import Any

from .media import load_outbound_media
from .streaming import _chunk_text

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Target resolution
# ---------------------------------------------------------------------------

async def resolve_send_target(client: Any, target: str) -> Any:
    """
    Resolve a target string to a discord.py channel/DM channel object.

    Supported formats:
      - "user:<snowflake>"    → create/fetch DM channel with user
      - "channel:<snowflake>" → fetch text/thread channel
      - bare numeric string   → try channel first, then DM
    """
    import discord

    # Strip prefix
    if target.startswith("user:"):
        user_id = int(target[5:])
        user = await client.fetch_user(user_id)
        # fetch_user always returns a User; create_dm() opens a DMChannel
        return await user.create_dm()

    if target.startswith("channel:"):
        ch_id = int(target[8:])
        ch = client.get_channel(ch_id)
        if ch is None:
            ch = await client.fetch_channel(ch_id)
        return ch

    # Bare ID
    try:
        ch_id = int(target)
        ch = client.get_channel(ch_id)
        if ch is None:
            ch = await client.fetch_channel(ch_id)
        return ch
    except (ValueError, discord.HTTPException):
        pass

    raise ValueError(f"Cannot resolve Discord target: {target!r}")


# ---------------------------------------------------------------------------
# Forum / Media channel detection
# ---------------------------------------------------------------------------

def _is_forum_or_media_channel(channel: Any) -> bool:
    """Return True only for Forum and Media channels that require thread creation.

    StageChannel is a voice channel, NOT a forum/media channel — it was
    incorrectly included here previously.
    """
    import discord
    return isinstance(channel, discord.ForumChannel) or (
        hasattr(discord, "MediaChannel") and isinstance(channel, discord.MediaChannel)
    )


# ---------------------------------------------------------------------------
# Text sending
# ---------------------------------------------------------------------------

async def send_discord_text(
    client: Any,
    target: str,
    text: str,
    reply_to: int | str | None = None,
    silent: bool = False,
    view: Any | None = None,
    embeds: list[Any] | None = None,
    chunk_limit: int = 2000,
    max_lines: int = 17,
    chunk_mode: str = "length",
    response_prefix: str | None = None,
) -> list[Any]:
    """
    Send text to a Discord channel, auto-chunked.
    Returns list of sent discord.Message objects.

    Mirrors sendDiscordText() + sendMessageDiscord() in TS.
    Supports Forum/Media channels (auto-creates a thread post).
    """
    import discord

    channel = await resolve_send_target(client, target)

    if response_prefix:
        text = f"{response_prefix}{text}"

    # Forum/Media channel: create a thread post
    if _is_forum_or_media_channel(channel):
        return await _send_to_forum(channel, text, view, embeds)

    chunks = _chunk_text(text, chunk_limit, max_lines, chunk_mode)
    sent: list[Any] = []

    for i, chunk in enumerate(chunks):
        kwargs: dict[str, Any] = {"content": chunk or "\u200b"}

        if i == 0 and reply_to:
            kwargs["reference"] = discord.MessageReference(
                message_id=int(reply_to),
                channel_id=channel.id,
            )
            kwargs["mention_author"] = False

        if silent:
            kwargs["silent"] = True

        if i == len(chunks) - 1:
            if view:
                kwargs["view"] = view
            if embeds:
                kwargs["embeds"] = embeds[:10]  # Discord max 10 embeds

        msg = await channel.send(**kwargs)
        sent.append(msg)

    return sent


async def _send_to_forum(
    channel: Any,
    text: str,
    view: Any | None,
    embeds: list[Any] | None,
) -> list[Any]:
    """
    Forum/Media channels require creating a thread post (POST /threads).
    Send the first chunk as the thread starter message.
    """
    chunks = _chunk_text(text)
    kwargs: dict[str, Any] = {
        "name": text[:100] if text else "Message",
        "content": chunks[0] if chunks else "\u200b",
    }
    if view:
        kwargs["view"] = view
    if embeds:
        kwargs["embeds"] = embeds[:10]

    thread = await channel.create_thread(**kwargs)
    sent = [thread.message]

    # Send remaining chunks into the thread
    for chunk in chunks[1:]:
        msg = await thread.send(content=chunk)
        sent.append(msg)

    return sent


# ---------------------------------------------------------------------------
# Media sending
# ---------------------------------------------------------------------------

async def send_discord_media(
    client: Any,
    target: str,
    media_url_or_path: str,
    caption: str | None = None,
    reply_to: int | str | None = None,
    spoiler: bool = False,
) -> Any | None:
    """
    Download media from URL/path and send as a Discord attachment.
    Mirrors sendDiscordMedia() in TS.
    """
    import discord

    try:
        data, filename = await load_outbound_media(media_url_or_path)
        channel = await resolve_send_target(client, target)

        if spoiler and not filename.startswith("SPOILER_"):
            filename = f"SPOILER_{filename}"

        file = discord.File(io.BytesIO(data), filename=filename)
        kwargs: dict[str, Any] = {"file": file}
        if caption:
            kwargs["content"] = caption
        if reply_to:
            kwargs["reference"] = discord.MessageReference(
                message_id=int(reply_to),
                channel_id=channel.id,
            )

        return await channel.send(**kwargs)
    except Exception as exc:
        logger.error("[discord][outbound] Failed to send media: %s", exc)
        raise


# ---------------------------------------------------------------------------
# Poll sending
# ---------------------------------------------------------------------------

async def send_discord_poll(
    client: Any,
    target: str,
    question: str,
    answers: list[str],
    duration_hours: int = 24,
    allow_multiselect: bool = False,
) -> Any | None:
    """
    Send a Discord native poll.
    Mirrors sendPollDiscord() in TS.
    """
    import discord

    try:
        channel = await resolve_send_target(client, target)

        # discord.Poll was added in discord.py 2.4; guard against older builds
        if not hasattr(discord, "Poll"):
            logger.warning(
                "[discord][outbound] discord.Poll not available in this discord.py version; "
                "sending poll as plain text instead."
            )
            options_text = "\n".join(f"{i + 1}. {a}" for i, a in enumerate(answers[:10]))
            await channel.send(f"**Poll:** {question}\n{options_text}")
            return None

        poll = discord.Poll(
            question=question,
            duration=duration_hours,
            multiple=allow_multiselect,
        )
        for answer in answers[:10]:  # Discord max 10 answers
            poll.add_answer(text=answer)
        return await channel.send(poll=poll)
    except Exception as exc:
        logger.error("[discord][outbound] Failed to send poll: %s", exc)
        raise


# ---------------------------------------------------------------------------
# Sticker sending
# ---------------------------------------------------------------------------

async def send_discord_sticker(
    client: Any,
    target: str,
    sticker_ids: list[int | str],
) -> Any | None:
    """
    Send sticker(s) by ID.
    Mirrors sendStickerDiscord() in TS.
    """
    import discord

    try:
        channel = await resolve_send_target(client, target)
        stickers = []
        for sid in sticker_ids[:3]:  # Discord max 3 stickers
            try:
                sticker = await client.fetch_sticker(int(sid))
                stickers.append(sticker)
            except Exception:
                pass
        if not stickers:
            return None
        return await channel.send(stickers=stickers)
    except Exception as exc:
        logger.error("[discord][outbound] Failed to send sticker: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Webhook execution
# ---------------------------------------------------------------------------

async def send_discord_webhook(
    webhook_id: str | int,
    webhook_token: str,
    text: str,
    username: str | None = None,
    avatar_url: str | None = None,
    thread_id: int | str | None = None,
    embeds: list[Any] | None = None,
) -> Any | None:
    """
    Execute a Discord webhook.
    Mirrors sendWebhookMessageDiscord() in TS.
    """
    import discord

    try:
        webhook = discord.Webhook.partial(
            int(webhook_id),
            webhook_token,
            session=None,  # will be handled by aiohttp connector
        )
        import aiohttp
        async with aiohttp.ClientSession() as session:
            webhook_with_session = discord.Webhook.partial(
                int(webhook_id),
                webhook_token,
                session=session,
            )
            kwargs: dict[str, Any] = {"content": text}
            if username:
                kwargs["username"] = username
            if avatar_url:
                kwargs["avatar_url"] = avatar_url
            if thread_id:
                kwargs["thread"] = discord.Object(id=int(thread_id))
            if embeds:
                kwargs["embeds"] = embeds[:10]
            return await webhook_with_session.send(**kwargs, wait=True)
    except Exception as exc:
        logger.error("[discord][outbound] Failed to send webhook: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Embed sending
# ---------------------------------------------------------------------------

async def send_discord_embed(
    client: Any,
    target: str,
    title: str | None = None,
    description: str | None = None,
    color: int | str | None = None,
    fields: list[dict] | None = None,
    footer: str | None = None,
    thumbnail_url: str | None = None,
    image_url: str | None = None,
    url: str | None = None,
    reply_to: int | str | None = None,
) -> Any | None:
    """
    Build and send a Discord embed.
    """
    import discord

    try:
        channel = await resolve_send_target(client, target)

        embed_color: discord.Color | int | None = None
        if isinstance(color, str):
            try:
                embed_color = int(color.lstrip("#"), 16)
            except (ValueError, AttributeError):
                embed_color = None
        elif isinstance(color, int):
            embed_color = color

        embed = discord.Embed(
            title=title,
            description=description,
            color=embed_color,
            url=url,
        )
        if footer:
            embed.set_footer(text=footer)
        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)
        if image_url:
            embed.set_image(url=image_url)
        for field in (fields or []):
            embed.add_field(
                name=field.get("name", ""),
                value=field.get("value", ""),
                inline=field.get("inline", False),
            )

        kwargs: dict[str, Any] = {"embed": embed}
        if reply_to:
            kwargs["reference"] = discord.MessageReference(
                message_id=int(reply_to),
                channel_id=channel.id,
            )
        return await channel.send(**kwargs)
    except Exception as exc:
        logger.error("[discord][outbound] Failed to send embed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Edit / Delete
# ---------------------------------------------------------------------------

async def edit_discord_message(
    client: Any,
    channel_id: int | str,
    message_id: int | str,
    new_content: str,
) -> Any | None:
    try:
        channel = client.get_channel(int(channel_id))
        if channel is None:
            channel = await client.fetch_channel(int(channel_id))
        msg = await channel.fetch_message(int(message_id))
        return await msg.edit(content=new_content)
    except Exception as exc:
        logger.error("[discord][outbound] Failed to edit message: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Voice message sending — mirrors src/discord/voice-message.ts
# ---------------------------------------------------------------------------

_DISCORD_VOICE_MESSAGE_FLAG = 1 << 13  # IS_VOICE_MESSAGE
_SUPPRESS_NOTIFICATIONS_FLAG = 1 << 12
_WAVEFORM_SAMPLES = 256


async def _generate_waveform(audio_path: str) -> str:
    """Generate a base64-encoded waveform (256 samples, 0-255) from an audio file.

    Uses ffmpeg to extract raw PCM and sample amplitude values.
    Falls back to a placeholder waveform on failure.
    Mirrors generateWaveform() in voice-message.ts.
    """
    import asyncio
    import base64
    import math
    import os
    import struct
    import tempfile

    tmp_pcm = tempfile.mktemp(suffix=".raw")
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", audio_path,
            "-f", "s16le", "-acodec", "pcm_s16le", "-ac", "1", "-ar", "8000",
            tmp_pcm,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()

        if proc.returncode != 0:
            raise RuntimeError("ffmpeg PCM extraction failed")

        with open(tmp_pcm, "rb") as f:
            pcm_raw = f.read()

        num_samples = len(pcm_raw) // 2
        if num_samples == 0:
            raise ValueError("Empty PCM data")

        step = max(1, num_samples // _WAVEFORM_SAMPLES)
        waveform: list[int] = []
        for i in range(_WAVEFORM_SAMPLES):
            start = i * step * 2
            end = min(start + step * 2, len(pcm_raw))
            chunk = pcm_raw[start:end]
            if not chunk:
                waveform.append(0)
                continue
            vals = struct.unpack(f"<{len(chunk) // 2}h", chunk[:len(chunk) & ~1])
            avg = sum(abs(v) for v in vals) / max(1, len(vals))
            waveform.append(min(255, int(avg / 32767.0 * 255)))

        while len(waveform) < _WAVEFORM_SAMPLES:
            waveform.append(0)

        return base64.b64encode(bytes(waveform[:_WAVEFORM_SAMPLES])).decode()

    except Exception:
        # Placeholder waveform — sine-wave pattern
        import math as _math
        waveform_data = [
            min(255, max(0, int(128 + 64 * _math.sin((i / _WAVEFORM_SAMPLES) * _math.pi * 8))))
            for i in range(_WAVEFORM_SAMPLES)
        ]
        import base64 as _b64
        return _b64.b64encode(bytes(waveform_data)).decode()
    finally:
        try:
            os.unlink(tmp_pcm)
        except OSError:
            pass


async def _get_audio_duration(audio_path: str) -> float:
    """Get audio duration in seconds using ffprobe."""
    import asyncio

    try:
        proc = await asyncio.create_subprocess_exec(
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            audio_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await proc.communicate()
        return round(float(stdout.decode().strip()), 2)
    except Exception:
        return 0.0


async def send_discord_voice_message(
    client: Any,
    target: str,
    audio_path: str,
    reply_to: int | str | None = None,
    silent: bool = False,
) -> Any | None:
    """
    Send a voice message to Discord with waveform and duration metadata.

    Follows Discord's voice message protocol:
      1. Request upload URL
      2. PUT audio bytes to CDN
      3. POST message with IS_VOICE_MESSAGE flag, duration_secs, waveform

    Mirrors sendDiscordVoiceMessage() in src/discord/voice-message.ts.
    Requires ffmpeg and ffprobe in PATH.
    """
    import aiohttp

    try:
        channel = await resolve_send_target(client, target)
        channel_id = str(channel.id)

        # Read audio file
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()

        # Compute waveform + duration in parallel
        waveform, duration_secs = await asyncio.gather(
            _generate_waveform(audio_path),
            _get_audio_duration(audio_path),
        )

        # Step 1: Request upload URL from Discord
        token = client.http.token  # type: ignore[attr-defined]
        headers = {"Authorization": f"Bot {token}", "Content-Type": "application/json"}
        upload_url_api = f"https://discord.com/api/v10/channels/{channel_id}/attachments"
        payload = {
            "files": [{"filename": "voice-message.ogg", "file_size": len(audio_bytes), "id": "0"}]
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(upload_url_api, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"Failed to get upload URL: {resp.status}")
                upload_data = await resp.json()

        attachment = upload_data.get("attachments", [{}])[0]
        upload_url: str = attachment.get("upload_url", "")
        upload_filename: str = attachment.get("upload_filename", "")
        if not upload_url:
            raise RuntimeError("No upload_url in response")

        # Step 2: Upload audio bytes to CDN
        async with aiohttp.ClientSession() as session:
            async with session.put(
                upload_url,
                data=audio_bytes,
                headers={"Content-Type": "audio/ogg"},
            ) as upload_resp:
                if upload_resp.status not in (200, 204):
                    raise RuntimeError(f"CDN upload failed: {upload_resp.status}")

        # Step 3: Send voice message with metadata
        flags = _DISCORD_VOICE_MESSAGE_FLAG
        if silent:
            flags |= _SUPPRESS_NOTIFICATIONS_FLAG

        msg_payload: dict[str, Any] = {
            "flags": flags,
            "attachments": [{
                "id": "0",
                "filename": "voice-message.ogg",
                "uploaded_filename": upload_filename,
                "duration_secs": duration_secs,
                "waveform": waveform,
            }],
        }
        if reply_to:
            msg_payload["message_reference"] = {
                "message_id": str(reply_to),
                "fail_if_not_exists": False,
            }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"https://discord.com/api/v10/channels/{channel_id}/messages",
                json=msg_payload,
                headers=headers,
            ) as msg_resp:
                if msg_resp.status not in (200, 201):
                    raise RuntimeError(f"Voice message send failed: {msg_resp.status}")
                return await msg_resp.json()

    except Exception as exc:
        logger.error("[discord][outbound] Failed to send voice message: %s", exc)
        return None


async def delete_discord_message(
    client: Any,
    channel_id: int | str,
    message_id: int | str,
) -> bool:
    try:
        channel = client.get_channel(int(channel_id))
        if channel is None:
            channel = await client.fetch_channel(int(channel_id))
        msg = await channel.fetch_message(int(message_id))
        await msg.delete()
        return True
    except Exception as exc:
        logger.error("[discord][outbound] Failed to delete message: %s", exc)
        return False
