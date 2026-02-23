"""Tool/utility commands.

Port of TypeScript:
  commands-bash.ts    → /bash
  commands-subagents.ts → /subagents
  commands-allowlist.ts + commands-approve.ts → /allowlist, /approve
  commands-ptt.ts     → /ptt (push-to-talk)
  commands-tts.ts     → /tts (text-to-speech)
  commands-plugin.ts  → /plugin
"""
from __future__ import annotations

import asyncio
import logging
import subprocess
from typing import Any

from ..get_reply import ReplyPayload

logger = logging.getLogger(__name__)


async def handle_tools_command(
    name: str,
    args: str,
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
    runtime: Any,
) -> ReplyPayload | None:
    if name in ("bash", "shell"):
        return await _handle_bash(args, ctx, cfg, session_key)
    if name == "subagents":
        return await _handle_subagents(args, ctx, cfg, session_key)
    if name == "allowlist":
        return await _handle_allowlist(args, ctx, cfg)
    if name == "approve":
        return await _handle_approve(args, ctx, cfg)
    if name == "ptt":
        return await _handle_ptt(args, ctx, cfg, session_key)
    if name == "tts":
        return await _handle_tts(args, ctx, cfg, session_key)
    if name == "plugin":
        return await _handle_plugin(args, ctx, cfg)
    return None


# ---------------------------------------------------------------------------
# /bash <command>  (mirrors TS commands-bash.ts → handleBashChatCommand)
# ---------------------------------------------------------------------------

_BASH_TIMEOUT_SECONDS = 30
_BASH_MAX_OUTPUT_CHARS = 4096


async def _handle_bash(
    args: str,
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
) -> ReplyPayload:
    if not args.strip():
        return ReplyPayload(text="Usage: /bash <command>")

    # Authorization check — only allowed senders may run bash
    authorized = getattr(ctx, "CommandAuthorized", None)
    if authorized is False:
        return ReplyPayload(text="Not authorized to run bash commands.")

    try:
        result = await asyncio.wait_for(
            asyncio.create_subprocess_shell(
                args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            ),
            timeout=_BASH_TIMEOUT_SECONDS,
        )
        stdout_bytes, _ = await result.communicate()
        output = stdout_bytes.decode("utf-8", errors="replace")
        exit_code = result.returncode or 0
    except asyncio.TimeoutError:
        return ReplyPayload(text=f"Command timed out after {_BASH_TIMEOUT_SECONDS}s")
    except Exception as exc:
        return ReplyPayload(text=f"Error running command: {exc}")

    if len(output) > _BASH_MAX_OUTPUT_CHARS:
        output = output[:_BASH_MAX_OUTPUT_CHARS] + "\n[…truncated]"

    status = "✅" if exit_code == 0 else f"❌ (exit {exit_code})"
    return ReplyPayload(text=f"```\n{output.rstrip()}\n```\n{status}")


# ---------------------------------------------------------------------------
# /subagents
# ---------------------------------------------------------------------------

async def _handle_subagents(
    args: str,
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
) -> ReplyPayload:
    sub = args.strip().lower()
    if not sub or sub == "list":
        return await _subagents_list(session_key, cfg)
    if sub in ("stop", "kill", "abort"):
        return await _subagents_stop(session_key, cfg)
    return ReplyPayload(text="Usage: /subagents [list|stop]")


async def _subagents_list(session_key: str, cfg: dict[str, Any]) -> ReplyPayload:
    try:
        from openclaw.agents.subagent_registry import list_subagent_runs_for_requester
        from openclaw.routing.session_key import normalize_main_key
        requester = normalize_main_key(session_key) if session_key else session_key
        runs = list_subagent_runs_for_requester(requester)
        if not runs:
            return ReplyPayload(text="No sub-agents running.")
        active = [r for r in runs if not r.get("ended_at")]
        done = len(runs) - len(active)
        lines = [f"Sub-agents: {len(active)} active, {done} done"]
        for r in active[:5]:
            label = r.get("label") or r.get("child_session_key") or r.get("run_id") or "(unknown)"
            lines.append(f"  ● {label}")
        return ReplyPayload(text="\n".join(lines))
    except Exception as exc:
        return ReplyPayload(text=f"Could not list sub-agents: {exc}")


async def _subagents_stop(session_key: str, cfg: dict[str, Any]) -> ReplyPayload:
    try:
        from ..get_reply import set_abort_memory, format_abort_reply_text
        if session_key:
            set_abort_memory(session_key, True)
        return ReplyPayload(text=format_abort_reply_text())
    except Exception as exc:
        return ReplyPayload(text=f"Could not stop sub-agents: {exc}")


# ---------------------------------------------------------------------------
# /allowlist
# ---------------------------------------------------------------------------

async def _handle_allowlist(args: str, ctx: Any, cfg: dict[str, Any]) -> ReplyPayload:
    parts = args.strip().split(None, 1)
    sub = parts[0].lower() if parts else "list"
    target = parts[1].strip() if len(parts) > 1 else ""

    if not sub or sub == "list":
        allow_from = cfg.get("allowFrom") or []
        if not allow_from:
            return ReplyPayload(text="Allowlist: empty (all senders allowed)")
        return ReplyPayload(text="Allowlist:\n" + "\n".join(f"  • {x}" for x in allow_from))

    if sub == "add" and target:
        allow_from = list(cfg.get("allowFrom") or [])
        if target not in allow_from:
            allow_from.append(target)
            cfg["allowFrom"] = allow_from
        return ReplyPayload(text=f"Added {target} to allowlist.")

    if sub in ("remove", "del", "rm") and target:
        allow_from = list(cfg.get("allowFrom") or [])
        if target in allow_from:
            allow_from.remove(target)
            cfg["allowFrom"] = allow_from
            return ReplyPayload(text=f"Removed {target} from allowlist.")
        return ReplyPayload(text=f"{target} not in allowlist.")

    return ReplyPayload(text="Usage: /allowlist [list|add <id>|remove <id>]")


# ---------------------------------------------------------------------------
# /approve <sender-id>
# ---------------------------------------------------------------------------

async def _handle_approve(args: str, ctx: Any, cfg: dict[str, Any]) -> ReplyPayload:
    target = args.strip()
    if not target:
        return ReplyPayload(text="Usage: /approve <sender-id>")
    return await _handle_allowlist(f"add {target}", ctx, cfg)


# ---------------------------------------------------------------------------
# /ptt [on|off|status]  — Push-to-talk
# ---------------------------------------------------------------------------

async def _handle_ptt(
    args: str,
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
) -> ReplyPayload:
    sub = args.strip().lower()
    try:
        from openclaw.tts.tts import set_ptt_enabled, is_ptt_enabled, resolve_tts_config
        tts_cfg = resolve_tts_config(cfg)
        if not sub or sub == "status":
            enabled = is_ptt_enabled(tts_cfg)
            return ReplyPayload(text=f"Push-to-talk: {'enabled' if enabled else 'disabled'}")
        if sub == "on":
            set_ptt_enabled(tts_cfg, True)
            return ReplyPayload(text="Push-to-talk enabled.")
        if sub == "off":
            set_ptt_enabled(tts_cfg, False)
            return ReplyPayload(text="Push-to-talk disabled.")
    except Exception:
        pass
    return ReplyPayload(text="Usage: /ptt [on|off|status]")


# ---------------------------------------------------------------------------
# /tts [on|off|status|provider <name>|limit <n>|summary <on|off>|audio <text>]
# ---------------------------------------------------------------------------

async def _handle_tts(
    args: str,
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
) -> ReplyPayload:
    sub_parts = args.strip().split(None, 1) if args.strip() else ["status"]
    sub = sub_parts[0].lower()
    sub_args = sub_parts[1].strip() if len(sub_parts) > 1 else ""

    try:
        from openclaw.tts.tts import (
            is_tts_enabled, set_tts_enabled, get_tts_provider, set_tts_provider,
            get_tts_max_length, set_tts_max_length,
            is_summarization_enabled, set_summarization_enabled,
            text_to_speech, resolve_tts_config, resolve_tts_prefs_path,
        )
        tts_cfg = resolve_tts_config(cfg)
        prefs_path = resolve_tts_prefs_path(tts_cfg)

        if sub == "on":
            set_tts_enabled(prefs_path, True)
            return ReplyPayload(text="TTS enabled.")
        if sub == "off":
            set_tts_enabled(prefs_path, False)
            return ReplyPayload(text="TTS disabled.")
        if sub == "status":
            enabled = is_tts_enabled(tts_cfg, prefs_path)
            provider = get_tts_provider(tts_cfg, prefs_path)
            max_len = get_tts_max_length(prefs_path)
            summarize = is_summarization_enabled(prefs_path)
            lines = [
                f"TTS status: {'enabled' if enabled else 'disabled'}",
                f"Provider: {provider}",
                f"Max length: {max_len}",
                f"Auto-summary: {'on' if summarize else 'off'}",
            ]
            return ReplyPayload(text="\n".join(lines))
        if sub == "provider":
            if not sub_args:
                p = get_tts_provider(tts_cfg, prefs_path)
                return ReplyPayload(text=f"TTS provider: {p}")
            set_tts_provider(prefs_path, sub_args.lower())
            return ReplyPayload(text=f"TTS provider set to {sub_args.lower()}.")
        if sub == "limit":
            if not sub_args:
                n = get_tts_max_length(prefs_path)
                return ReplyPayload(text=f"TTS limit: {n} chars")
            try:
                n = int(sub_args)
                set_tts_max_length(prefs_path, n)
                return ReplyPayload(text=f"TTS limit set to {n}.")
            except ValueError:
                return ReplyPayload(text="Usage: /tts limit <number>")
        if sub == "summary":
            if not sub_args:
                s = is_summarization_enabled(prefs_path)
                return ReplyPayload(text=f"TTS auto-summary: {'on' if s else 'off'}")
            set_summarization_enabled(prefs_path, sub_args.lower() == "on")
            return ReplyPayload(text=f"TTS summary {'enabled' if sub_args.lower() == 'on' else 'disabled'}.")
        if sub == "audio":
            if not sub_args:
                return ReplyPayload(text="Usage: /tts audio <text>")
            channel = str(
                getattr(ctx, "Surface", None) or getattr(ctx, "Provider", None) or "unknown"
            ).lower()
            result = await text_to_speech(text=sub_args, cfg=cfg, channel=channel, prefs_path=prefs_path)
            if result.get("success") and result.get("audio_path"):
                return ReplyPayload(
                    media_url=result["audio_path"],
                    audio_as_voice=result.get("voice_compatible", False),
                )
            return ReplyPayload(text=f"TTS error: {result.get('error', 'unknown')}")
    except ImportError:
        pass
    except Exception as exc:
        logger.warning(f"/tts error: {exc}")
        return ReplyPayload(text=f"TTS error: {exc}")

    return ReplyPayload(
        text="TTS usage: /tts [on|off|status|provider <name>|limit <n>|summary <on|off>|audio <text>]"
    )


# ---------------------------------------------------------------------------
# /plugin [list|info <name>]
# ---------------------------------------------------------------------------

async def _handle_plugin(args: str, ctx: Any, cfg: dict[str, Any]) -> ReplyPayload:
    sub = args.strip().lower() if args else "list"
    try:
        from openclaw.plugins.hook_runner import get_global_hook_runner
        runner = get_global_hook_runner()
        if not runner:
            return ReplyPayload(text="No plugins loaded.")
        plugins = getattr(runner, "plugins", []) or []
        if not plugins:
            return ReplyPayload(text="No plugins loaded.")
        lines = ["Plugins:"]
        for p in plugins:
            name = getattr(p, "name", None) or str(p)
            version = getattr(p, "version", None)
            lines.append(f"  • {name}" + (f" v{version}" if version else ""))
        return ReplyPayload(text="\n".join(lines))
    except Exception as exc:
        return ReplyPayload(text=f"Could not list plugins: {exc}")
