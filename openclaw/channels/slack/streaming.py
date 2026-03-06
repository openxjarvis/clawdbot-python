"""Slack native AI streaming — wraps chat.startStream / appendStream / stopStream.

Implements the "Agents & AI Apps" streaming UX available in Slack's official
AI apps API. Text grows word-by-word in a single live-updating Slack message.

Requires:
  - nativeStreaming: true in the account config
  - streaming: "partial" in the account config
  - A valid thread_ts (Slack streaming is always threaded)
  - For DMs: recipient_user_id must be set (prevents missing_recipient_user_id error)

Mirrors TypeScript: src/slack/streaming.ts + src/slack/stream-mode.ts
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Stream session
# ---------------------------------------------------------------------------

@dataclass
class SlackStreamSession:
    """Holds the stream_id and context for an active Slack AI stream."""
    stream_id: str
    channel: str
    thread_ts: str
    client: Any
    team_id: str | None = None
    user_id: str | None = None
    _active: bool = field(default=True, init=False, repr=False)
    _last_text: str = field(default="", init=False, repr=False)


# ---------------------------------------------------------------------------
# Low-level API wrappers (run sync SDK calls off-thread)
# ---------------------------------------------------------------------------

async def start_slack_stream(
    client: Any,
    channel: str,
    thread_ts: str,
    *,
    team_id: str | None = None,
    user_id: str | None = None,
) -> SlackStreamSession | None:
    """
    Call chat.startStream to begin a live-updating Slack AI stream.

    Returns the session on success, None on failure.
    Mirrors TS startSlackStream().
    """
    loop = asyncio.get_running_loop()
    try:
        kwargs: dict[str, Any] = {
            "channel": channel,
            "thread_ts": thread_ts,
        }
        if team_id:
            kwargs["recipient_team_id"] = team_id
        if user_id:
            # Required for DM streams — Slack returns missing_recipient_user_id without it
            kwargs["recipient_user_id"] = user_id

        resp = await loop.run_in_executor(
            None, lambda: client.chat_startStream(**kwargs)
        )
        if not resp.get("ok"):
            logger.warning("[slack-stream] chat.startStream failed: %s", resp)
            return None

        stream_id = resp.get("stream_id") or resp.get("ts") or ""
        if not stream_id:
            logger.warning("[slack-stream] chat.startStream: no stream_id in response")
            return None

        logger.debug("[slack-stream] started stream_id=%s channel=%s thread=%s", stream_id, channel, thread_ts)
        return SlackStreamSession(
            stream_id=stream_id,
            channel=channel,
            thread_ts=thread_ts,
            client=client,
            team_id=team_id,
            user_id=user_id,
        )
    except Exception as exc:
        logger.warning("[slack-stream] chat.startStream error: %s", exc)
        return None


async def append_slack_stream(
    session: SlackStreamSession,
    markdown_text: str,
) -> bool:
    """
    Call chat.appendStream to add text to the live stream.

    Slack streaming is append-only — this sends only the NEW suffix of the text.
    Mirrors TS appendSlackStream() + applyAppendOnlyStreamUpdate().
    """
    if not session._active:
        return False
    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(
            None,
            lambda: session.client.chat_appendStream(
                stream_id=session.stream_id,
                markdown_text=markdown_text,
            ),
        )
        return True
    except Exception as exc:
        logger.debug("[slack-stream] chat.appendStream error: %s", exc)
        return False


async def stop_slack_stream(
    session: SlackStreamSession,
    final_text: str = "",
) -> bool:
    """
    Call chat.stopStream to finalize the stream and convert it to a normal message.

    Mirrors TS stopSlackStream().
    """
    if not session._active:
        return False
    session._active = False
    loop = asyncio.get_running_loop()
    try:
        kwargs: dict[str, Any] = {"stream_id": session.stream_id}
        if final_text:
            kwargs["markdown_text"] = final_text
        await loop.run_in_executor(
            None,
            lambda: session.client.chat_stopStream(**kwargs),
        )
        logger.debug("[slack-stream] stopped stream_id=%s", session.stream_id)
        return True
    except Exception as exc:
        logger.warning("[slack-stream] chat.stopStream error: %s", exc)
        return False


# ---------------------------------------------------------------------------
# SlackDraftStream — high-level wrapper compatible with the draft_stream protocol
# ---------------------------------------------------------------------------

class SlackDraftStream:
    """
    Wraps SlackStreamSession as a draft_stream-compatible object.

    Protocol (mirrors Feishu's FeishuReplyDispatcher protocol so the existing
    Feishu branch in _run_agent_now handles Slack streaming without extra code):
      - update(text)        — async; appends only the NEW suffix to the stream
      - stream_finalize(text, buttons=) — async; stops the stream with final text
      - is_streaming_active() → bool

    The `text` argument to `update()` is CUMULATIVE (full accumulated text),
    not a delta. We compute the suffix to append by tracking `_last_delivered`.
    Mirrors TS applyAppendOnlyStreamUpdate().
    """

    def __init__(
        self,
        client: Any,
        channel: str,
        thread_ts: str,
        *,
        team_id: str | None = None,
        user_id: str | None = None,
    ) -> None:
        self._client = client
        self._channel = channel
        self._thread_ts = thread_ts
        self._team_id = team_id
        self._user_id = user_id

        self._session: SlackStreamSession | None = None
        self._last_delivered: str = ""
        self._started = False

    async def _ensure_started(self) -> bool:
        """Lazily start the stream on the first update."""
        if self._started:
            return self._session is not None
        self._started = True
        self._session = await start_slack_stream(
            self._client,
            self._channel,
            self._thread_ts,
            team_id=self._team_id,
            user_id=self._user_id,
        )
        return self._session is not None

    async def update(self, text: str) -> None:
        """Push incremental text. text is the full accumulated response so far."""
        if not await self._ensure_started():
            return
        if not self._session:
            return

        # Append-only: compute suffix since last delivery
        if text.startswith(self._last_delivered):
            suffix = text[len(self._last_delivered):]
        else:
            # Rare: text was replaced rather than extended; send full text as suffix
            suffix = text

        if not suffix:
            return

        ok = await append_slack_stream(self._session, suffix)
        if ok:
            self._last_delivered = text

    async def stream_finalize(
        self,
        final_text: str,
        buttons: list[list[dict]] | None = None,
    ) -> str | None:
        """Finalize the stream. Returns None (no message_id available from Slack stopStream)."""
        if not await self._ensure_started():
            return None
        if self._session:
            # Compute any unsent suffix for the final stop call
            if final_text.startswith(self._last_delivered):
                final_suffix = final_text[len(self._last_delivered):]
            else:
                final_suffix = ""  # everything was already appended
            await stop_slack_stream(self._session, final_text=final_suffix or "")
        return None

    def is_streaming_active(self) -> bool:
        """True if the stream was started and not yet finalized."""
        return self._started and self._session is not None and self._session._active

    async def stop_typing(self) -> None:
        """No-op for Slack — no emoji-reaction typing indicator."""
        pass


__all__ = [
    "SlackStreamSession",
    "start_slack_stream",
    "append_slack_stream",
    "stop_slack_stream",
    "SlackDraftStream",
]
