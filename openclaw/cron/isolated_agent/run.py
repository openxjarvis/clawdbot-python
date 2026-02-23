"""Isolated agent execution for cron jobs.

Mirrors TypeScript: openclaw/src/cron/isolated-agent/run.ts

The main entry point `run_cron_isolated_agent_turn` delegates to the
gateway-provided `run_agent_fn` callback (which wraps PiAgentRuntime),
exactly as TS runCronIsolatedAgentTurn calls state.deps.runIsolatedAgentJob.

Caller (cron_bootstrap.py) provides run_agent_fn that handles the actual
agent execution via the configured pi runtime.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


async def run_cron_isolated_agent_turn(
    job: Any,
    run_agent_fn: Callable[..., Awaitable[dict[str, Any]]],
    message: str,
) -> dict[str, Any]:
    """
    Run an isolated agent turn for a cron job.

    Delegates to run_agent_fn (gateway callback), which executes the agent
    using pi_runtime or an equivalent, and returns a result dict.

    Returns dict with:
        status: "ok" | "error" | "skipped"
        summary: str | None
        output_text: str | None
        delivered: bool
        session_id: str | None
        session_key: str | None
        model: str | None
        provider: str | None
        usage: dict | None
        error: str | None
    """
    try:
        result = await run_agent_fn(job=job, message=message)
    except Exception as err:
        logger.error(f"cron: isolated agent run failed for job {getattr(job, 'id', '?')!r}: {err}")
        return {
            "status": "error",
            "error": str(err),
            "summary": None,
            "output_text": None,
            "delivered": False,
            "session_id": None,
            "session_key": None,
            "model": None,
            "provider": None,
            "usage": None,
        }

    # Normalise result keys (support both snake_case and camelCase)
    status = result.get("status") or ("ok" if result.get("success") else "error")
    summary = result.get("summary")
    output_text = result.get("output_text") or result.get("outputText")
    delivered = bool(result.get("delivered"))
    session_id = result.get("session_id") or result.get("sessionId")
    session_key = result.get("session_key") or result.get("sessionKey")
    model = result.get("model")
    provider = result.get("provider")
    usage = result.get("usage")
    error = result.get("error")

    return {
        "status": status,
        "summary": summary,
        "output_text": output_text,
        "delivered": delivered,
        "session_id": session_id,
        "session_key": session_key,
        "model": model,
        "provider": provider,
        "usage": usage,
        "error": error,
    }


# ---------------------------------------------------------------------------
# Helpers (retained for use in tests / fallback implementations)
# ---------------------------------------------------------------------------

def extract_summary(text: str, max_length: int = 200) -> str:
    """Extract a short summary from agent output text."""
    if not text:
        return ""
    paragraphs = text.split("\n\n")
    first = paragraphs[0].strip() if paragraphs else text.strip()
    if len(first) <= max_length:
        return first
    # Truncate at word boundary
    cut = first[:max_length]
    last_space = cut.rfind(" ")
    return (cut[:last_space] + "…") if last_space > 0 else (cut + "…")


def detect_self_sent_via_messaging(messages: list[Any]) -> bool:
    """Check if agent already sent message via a messaging tool call."""
    messaging_tools = {
        "send_telegram_message",
        "send_discord_message",
        "send_slack_message",
        "send_message",
        "channel_send",
    }
    for msg in messages:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                name = (tc.get("name") or "").lower()
                if any(mt in name for mt in messaging_tools):
                    return True
    return False


async def post_summary_to_main_session(
    job: Any,
    result: dict[str, Any],
    main_session_callback: Any,
) -> None:
    """Post execution summary back to main session."""
    if result.get("status") not in ("ok", None) or result.get("error"):
        return
    summary = (result.get("summary") or "").strip()
    if not summary:
        return
    message = f"Cron job '{getattr(job, 'name', job)}' completed:\n\n{summary}"
    try:
        if main_session_callback:
            await main_session_callback(message)
    except Exception as e:
        logger.error(f"cron: error posting summary to main session: {e}")
