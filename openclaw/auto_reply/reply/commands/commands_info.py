"""Info / status commands.

Port of TypeScript:
  commands-info.ts   → /help, /commands, /whoami
  commands-status.ts → /status
  commands-context-report.ts → /context, /context-report
  commands-export-session.ts → /export-session, /export
"""
from __future__ import annotations

import logging
import platform
import sys
import time
from typing import Any

from ..get_reply import ReplyPayload

logger = logging.getLogger(__name__)

async def handle_info_command(
    name: str,
    args: str,
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
    runtime: Any,
) -> ReplyPayload | None:
    if name == "help":
        return await _handle_help(ctx, cfg)
    if name in ("commands",):
        return await _handle_commands_list(ctx, cfg)
    if name == "status":
        return await _handle_status(ctx, cfg, session_key, runtime)
    if name in ("context", "context-report"):
        # Pass the full raw command body so /context list, /context detail, etc. work
        command_body = f"/{name}" + (f" {args}" if args else "")
        return await _handle_context(ctx, cfg, session_key, command_body=command_body)
    if name in ("whoami", "id"):  # /id is alias for /whoami
        return await _handle_whoami(ctx, cfg)
    if name in ("export-session", "export"):
        return await _handle_export_session(ctx, cfg, session_key)
    if name == "debug":
        return await _handle_debug(ctx, cfg, session_key)
    if name == "usage":
        return await _handle_usage(args, ctx, cfg, session_key)
    if name == "skill":
        return await _handle_skill(args, ctx, cfg, session_key, runtime)
    return None


# ---------------------------------------------------------------------------
# /help
# ---------------------------------------------------------------------------

async def _handle_help(ctx: Any, cfg: dict[str, Any]) -> ReplyPayload:
    lines = [
        "Available commands:",
        "",
        "  /help         Show this message",
        "  /commands     List all commands",
        "  /status       Show session status",
        "  /context      Show context info",
        "  /whoami       Show your identity",
        "",
        "  /new          Start a new session",
        "  /reset        Reset current session",
        "  /compact      Compact session history",
        "  /session      Session management",
        "",
        "  /model        Set AI model",
        "  /models       List available models",
        "  /think        Set thinking level",
        "  /verbose      Toggle verbose mode",
        "",
        "  /config       View/edit configuration",
        "  /system-prompt  View/set system prompt",
        "",
        "  /bash         Run a bash command",
        "  /subagents    List running sub-agents",
        "  /allowlist    Manage allowed senders",
        "  /tts          Toggle text-to-speech",
        "",
        "  stop / /stop  Abort current operation",
    ]
    return ReplyPayload(text="\n".join(lines))


# ---------------------------------------------------------------------------
# /commands
# ---------------------------------------------------------------------------

async def _handle_commands_list(ctx: Any, cfg: dict[str, Any]) -> ReplyPayload:
    try:
        from openclaw.auto_reply.commands_registry_data import get_builtin_commands
        cmds = get_builtin_commands()
        lines = ["Commands:"]
        for cmd in cmds:
            name_part = cmd.name
            aliases = getattr(cmd, "aliases", [])
            if aliases:
                name_part += f" ({', '.join(aliases)})"
            desc = getattr(cmd, "description", "")
            lines.append(f"  /{name_part}  — {desc}")
        return ReplyPayload(text="\n".join(lines))
    except Exception:
        return await _handle_help(ctx, cfg)


# ---------------------------------------------------------------------------
# /status
# ---------------------------------------------------------------------------

async def _handle_status(
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
    runtime: Any,
) -> ReplyPayload:
    lines: list[str] = []

    # Basic identity
    agent_id = _resolve_agent_id(session_key, cfg)
    lines.append(f"Session: {session_key or '(none)'}")
    if agent_id:
        lines.append(f"Agent: {agent_id}")

    # Model info
    provider, model = _resolve_model(cfg, runtime)
    lines.append(f"Model: {provider}/{model}")

    # Session entry info
    try:
        entry = _load_session_entry(session_key, cfg)
        if entry:
            if entry.get("ttsAuto"):
                lines.append(f"TTS: {entry['ttsAuto']}")
            if entry.get("model") or entry.get("provider"):
                m = entry.get("model") or model
                p = entry.get("provider") or provider
                lines.append(f"Session model: {p}/{m}")
    except Exception:
        pass

    # System info
    lines.append(f"Python: {sys.version.split()[0]}")

    # Uptime (if available)
    try:
        from openclaw.gateway.uptime import get_uptime_seconds
        uptime = get_uptime_seconds()
        lines.append(f"Uptime: {_format_duration(uptime)}")
    except Exception:
        pass

    return ReplyPayload(text="\n".join(lines))


# ---------------------------------------------------------------------------
# /context — aligned with TS commands-context-report.ts buildContextReply()
# ---------------------------------------------------------------------------

def _format_int(n: int) -> str:
    return f"{n:,}"


def _estimate_tokens(chars: int) -> int:
    return max(0, (chars + 3) // 4)


def _format_chars_and_tokens(chars: int) -> str:
    return f"{_format_int(chars)} chars (~{_format_int(_estimate_tokens(chars))} tok)"


def _format_name_list(names: list[str], cap: int) -> str:
    if len(names) <= cap:
        return ", ".join(names)
    return ", ".join(names[:cap]) + f", … (+{len(names) - cap} more)"


def _format_list_top(
    entries: list[tuple[str, int]], cap: int
) -> tuple[list[str], int]:
    """Return (top_lines, omitted_count). Entries are (name, value) tuples."""
    sorted_entries = sorted(entries, key=lambda e: e[1], reverse=True)
    top = sorted_entries[:cap]
    omitted = max(0, len(sorted_entries) - len(top))
    lines = [f"- {name}: {_format_chars_and_tokens(value)}" for name, value in top]
    return lines, omitted


def _parse_context_sub(command_body: str) -> str:
    """Extract sub-command from '/context <sub>' command body."""
    body = command_body.strip()
    if body in ("/context", "/context-report"):
        return ""
    for prefix in ("/context ", "/context-report "):
        if body.startswith(prefix):
            return body[len(prefix):].strip().split()[0].lower() if body[len(prefix):].strip() else ""
    return ""


async def _handle_context(
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
    command_body: str = "/context",
) -> ReplyPayload:
    """Full /context command — mirrors TS buildContextReply().

    Sub-commands:
      (none) / help  → usage help
      list / show    → short breakdown
      detail / deep  → detailed breakdown with per-skill/per-tool sizes
      json           → machine-readable JSON
    """
    from openclaw.agents.system_prompt_bootstrap import (
        resolve_bootstrap_max_chars,
        resolve_bootstrap_total_max_chars,
    )

    sub = _parse_context_sub(command_body)

    if not sub or sub == "help":
        return ReplyPayload(text="\n".join([
            "🧠 /context",
            "",
            "What counts as context (high-level), plus a breakdown mode.",
            "",
            "Try:",
            "- /context list   (short breakdown)",
            "- /context detail (per-file + per-tool + per-skill + system prompt size)",
            "- /context json   (same, machine-readable)",
        ]))

    # Resolve report from session entry or build an estimate
    report: dict[str, Any] | None = None
    entry = _load_session_entry(session_key, cfg)
    if entry:
        raw_report = entry.get("systemPromptReport")
        if isinstance(raw_report, dict) and raw_report.get("source") == "run":
            report = raw_report

    if report is None:
        report = _build_context_report_estimate(session_key, cfg, entry)

    bootstrap_max_chars = report.get("bootstrapMaxChars") or resolve_bootstrap_max_chars(cfg)
    bootstrap_total_max_chars = report.get("bootstrapTotalMaxChars") or resolve_bootstrap_total_max_chars(cfg)
    workspace_dir = report.get("workspaceDir") or "(unknown)"
    source = report.get("source", "estimate")

    system_prompt_info = report.get("systemPrompt") or {}
    sp_chars = system_prompt_info.get("chars", 0)
    sp_project_chars = system_prompt_info.get("projectContextChars", 0)
    system_prompt_line = (
        f"System prompt ({source}): {_format_chars_and_tokens(sp_chars)} "
        f"(Project Context {_format_chars_and_tokens(sp_project_chars)})"
    )

    injected_files: list[dict[str, Any]] = report.get("injectedWorkspaceFiles") or []
    file_lines = []
    for f in injected_files:
        name = f.get("name", "?")
        missing = f.get("missing", False)
        truncated = f.get("truncated", False)
        raw_chars = f.get("rawChars", 0)
        injected_chars = f.get("injectedChars", 0)
        status = "MISSING" if missing else ("TRUNCATED" if truncated else "OK")
        raw_str = "0" if missing else _format_chars_and_tokens(raw_chars)
        inj_str = "0" if missing else _format_chars_and_tokens(injected_chars)
        file_lines.append(f"- {name}: {status} | raw {raw_str} | injected {inj_str}")

    skills_info = report.get("skills") or {}
    skills_prompt_chars = skills_info.get("promptChars", 0)
    skills_entries: list[dict[str, Any]] = skills_info.get("entries") or []
    skill_names = list(dict.fromkeys(e.get("name", "") for e in skills_entries))
    skills_line = f"Skills list (system prompt text): {_format_chars_and_tokens(skills_prompt_chars)} ({len(skill_names)} skills)"
    skills_names_line = f"Skills: {_format_name_list(skill_names, 20)}" if skill_names else "Skills: (none)"

    tools_info = report.get("tools") or {}
    tools_list_chars = tools_info.get("listChars", 0)
    tools_schema_chars = tools_info.get("schemaChars", 0)
    tools_entries: list[dict[str, Any]] = tools_info.get("entries") or []
    tool_names = [e.get("name", "") for e in tools_entries]
    tool_list_line = f"Tool list (system prompt text): {_format_chars_and_tokens(tools_list_chars)}"
    tool_schema_line = f"Tool schemas (JSON): {_format_chars_and_tokens(tools_schema_chars)} (counts toward context; not shown as text)"
    tools_names_line = f"Tools: {_format_name_list(tool_names, 30)}" if tool_names else "Tools: (none)"

    sandbox_info = report.get("sandbox") or {}
    sandbox_line = f"Sandbox: mode={sandbox_info.get('mode', 'unknown')} sandboxed={sandbox_info.get('sandboxed', False)}"

    # Bootstrap truncation warnings
    non_missing = [f for f in injected_files if not f.get("missing")]
    truncated_files = [f for f in non_missing if f.get("truncated")]
    raw_bootstrap_chars = sum(f.get("rawChars", 0) for f in non_missing)
    injected_bootstrap_chars = sum(f.get("injectedChars", 0) for f in non_missing)
    per_file_over_limit = sum(1 for f in non_missing if f.get("rawChars", 0) > bootstrap_max_chars)
    total_over_limit = raw_bootstrap_chars > bootstrap_total_max_chars
    bootstrap_warning_lines: list[str] = []
    if truncated_files:
        causes = []
        if per_file_over_limit > 0:
            causes.append(f"{per_file_over_limit} file(s) exceeded max/file")
        if total_over_limit:
            causes.append("raw total exceeded max/total")
        bootstrap_warning_lines.append(
            f"⚠ Bootstrap context is over configured limits: {len(truncated_files)} file(s) truncated "
            f"({_format_int(raw_bootstrap_chars)} raw chars -> {_format_int(injected_bootstrap_chars)} injected chars)."
        )
        if causes:
            bootstrap_warning_lines.append(f"Causes: {'; '.join(causes)}.")
        bootstrap_warning_lines.append(
            "Tip: increase `agents.defaults.bootstrapMaxChars` and/or `agents.defaults.bootstrapTotalMaxChars` if this truncation is not intentional."
        )

    context_tokens = entry.get("contextTokens") if entry else None
    total_tokens = entry.get("totalTokens") if entry else None
    totals_line = (
        f"Session tokens (cached): {_format_int(total_tokens)} total / ctx={context_tokens or '?'}"
        if total_tokens is not None
        else f"Session tokens (cached): unknown / ctx={context_tokens or '?'}"
    )

    if sub == "json":
        import json
        return ReplyPayload(text=json.dumps(report, indent=2, default=str))

    if sub not in ("list", "show", "detail", "deep"):
        return ReplyPayload(text="Unknown /context mode.\nUse: /context, /context list, /context detail, or /context json")

    bootstrap_max_label = f"{_format_int(bootstrap_max_chars)} chars"
    bootstrap_total_label = f"{_format_int(bootstrap_total_max_chars)} chars"

    if sub in ("detail", "deep"):
        per_skill_lines, per_skill_omitted = _format_list_top(
            [(e.get("name", "?"), e.get("blockChars", 0)) for e in skills_entries], 30
        )
        per_tool_schema_lines, per_tool_schema_omitted = _format_list_top(
            [(e.get("name", "?"), e.get("schemaChars", 0)) for e in tools_entries], 30
        )
        per_tool_summary_lines, per_tool_summary_omitted = _format_list_top(
            [(e.get("name", "?"), e.get("summaryChars", 0)) for e in tools_entries], 30
        )
        tool_props_lines = [
            f"- {e['name']}: {e['propertiesCount']} params"
            for e in sorted(tools_entries, key=lambda t: t.get("propertiesCount") or 0, reverse=True)[:30]
            if e.get("propertiesCount") is not None
        ]
        parts = [
            "🧠 Context breakdown (detailed)",
            f"Workspace: {workspace_dir}",
            f"Bootstrap max/file: {bootstrap_max_label}",
            f"Bootstrap max/total: {bootstrap_total_label}",
            sandbox_line,
            system_prompt_line,
        ]
        if bootstrap_warning_lines:
            parts += [""] + bootstrap_warning_lines
        parts += [
            "",
            "Injected workspace files:",
            *file_lines,
            "",
            skills_line,
            skills_names_line,
        ]
        if per_skill_lines:
            parts += ["Top skills (prompt entry size):", *per_skill_lines]
        if per_skill_omitted:
            parts.append(f"… (+{per_skill_omitted} more skills)")
        parts += [
            "",
            tool_list_line,
            tool_schema_line,
            tools_names_line,
            "Top tools (schema size):",
            *per_tool_schema_lines,
        ]
        if per_tool_schema_omitted:
            parts.append(f"… (+{per_tool_schema_omitted} more tools)")
        parts += ["", "Top tools (summary text size):", *per_tool_summary_lines]
        if per_tool_summary_omitted:
            parts.append(f"… (+{per_tool_summary_omitted} more tools)")
        if tool_props_lines:
            parts += ["", "Tools (param count):", *tool_props_lines]
        parts += ["", totals_line]
        return ReplyPayload(text="\n".join(p for p in parts if p is not None))

    # list / show
    parts = [
        "🧠 Context breakdown",
        f"Workspace: {workspace_dir}",
        f"Bootstrap max/file: {bootstrap_max_label}",
        f"Bootstrap max/total: {bootstrap_total_label}",
        sandbox_line,
        system_prompt_line,
    ]
    if bootstrap_warning_lines:
        parts += [""] + bootstrap_warning_lines
    parts += [
        "",
        "Injected workspace files:",
        *file_lines,
        "",
        skills_line,
        skills_names_line,
        tool_list_line,
        tool_schema_line,
        tools_names_line,
        "",
        totals_line,
    ]
    return ReplyPayload(text="\n".join(parts))


def _build_context_report_estimate(
    session_key: str,
    cfg: dict[str, Any],
    entry: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build a basic context report estimate when no run report is available."""
    from openclaw.agents.system_prompt_bootstrap import (
        resolve_bootstrap_max_chars,
        resolve_bootstrap_total_max_chars,
    )

    bootstrap_max = resolve_bootstrap_max_chars(cfg)
    bootstrap_total = resolve_bootstrap_total_max_chars(cfg)
    workspace_dir = ""
    try:
        workspace_dir = cfg.get("agents", {}).get("defaults", {}).get("workspace", "") or ""
    except Exception:
        pass

    injected_files: list[dict[str, Any]] = []
    if workspace_dir:
        from pathlib import Path
        from openclaw.agents.system_prompt_bootstrap import load_bootstrap_files
        try:
            files = load_bootstrap_files(Path(workspace_dir), cfg=cfg)
            for f in files:
                is_missing = "(File" in f.content or "(Error" in f.content
                raw_chars = 0 if is_missing else len(f.content)
                injected_files.append({
                    "name": f.path,
                    "path": f.path,
                    "missing": is_missing,
                    "rawChars": raw_chars,
                    "injectedChars": min(raw_chars, bootstrap_max),
                    "truncated": f.truncated,
                })
        except Exception:
            pass

    return {
        "source": "estimate",
        "generatedAt": int(time.time() * 1000),
        "sessionKey": session_key,
        "workspaceDir": workspace_dir,
        "bootstrapMaxChars": bootstrap_max,
        "bootstrapTotalMaxChars": bootstrap_total,
        "sandbox": {"mode": "unknown", "sandboxed": False},
        "systemPrompt": {"chars": 0, "projectContextChars": 0, "nonProjectContextChars": 0},
        "injectedWorkspaceFiles": injected_files,
        "skills": {"promptChars": 0, "entries": []},
        "tools": {"listChars": 0, "schemaChars": 0, "entries": []},
    }


# ---------------------------------------------------------------------------
# /whoami
# ---------------------------------------------------------------------------

async def _handle_whoami(ctx: Any, cfg: dict[str, Any]) -> ReplyPayload:
    lines = ["Identity:"]
    channel = str(
        getattr(ctx, "Surface", None) or getattr(ctx, "Provider", None) or "unknown"
    ).lower()
    lines.append(f"Channel: {channel}")
    sender_id = getattr(ctx, "SenderId", None) or getattr(ctx, "From", None) or ""
    if sender_id:
        lines.append(f"User id: {sender_id}")
    sender_username = getattr(ctx, "SenderUsername", None)
    if sender_username:
        handle = sender_username if sender_username.startswith("@") else f"@{sender_username}"
        lines.append(f"Username: {handle}")
    chat_type = getattr(ctx, "ChatType", None) or ""
    if chat_type == "group":
        chat_from = getattr(ctx, "From", None) or ""
        if chat_from:
            lines.append(f"Chat: {chat_from}")
    thread_id = getattr(ctx, "MessageThreadId", None)
    if thread_id is not None:
        lines.append(f"Thread: {thread_id}")
    if sender_id:
        lines.append(f"AllowFrom: {sender_id}")
    return ReplyPayload(text="\n".join(lines))


# ---------------------------------------------------------------------------
# /export-session
# ---------------------------------------------------------------------------

async def _handle_export_session(
    ctx: Any, cfg: dict[str, Any], session_key: str
) -> ReplyPayload:
    import json
    try:
        entry = _load_session_entry(session_key, cfg)
        if not entry:
            return ReplyPayload(text="No session data found.")
        # Remove sensitive fields
        safe_entry = {k: v for k, v in entry.items() if k not in ("systemPrompt", "apiKey")}
        return ReplyPayload(text=f"Session export:\n```json\n{json.dumps(safe_entry, indent=2)}\n```")
    except Exception as exc:
        return ReplyPayload(text=f"Export failed: {exc}")


# ---------------------------------------------------------------------------
# /debug
# ---------------------------------------------------------------------------

async def _handle_debug(ctx: Any, cfg: dict[str, Any], session_key: str) -> ReplyPayload:
    lines = ["Debug info:"]
    lines.append(f"Python: {sys.version}")
    lines.append(f"Platform: {platform.platform()}")
    lines.append(f"Session key: {session_key or '(none)'}")

    ctx_fields = [
        "SessionKey", "ChatType", "CommandSource", "Surface", "Provider",
        "From", "To", "SenderId", "SenderName",
    ]
    for field in ctx_fields:
        val = getattr(ctx, field, None)
        if val is not None:
            lines.append(f"  ctx.{field}: {val}")

    return ReplyPayload(text="\n".join(lines))


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _resolve_agent_id(session_key: str, cfg: dict[str, Any]) -> str:
    if not session_key:
        return ""
    try:
        from openclaw.routing.session_key import parse_agent_session_key
        parsed = parse_agent_session_key(session_key)
        return parsed.get("agent_id") or parsed.get("agentId") or "" if parsed else ""
    except Exception:
        parts = session_key.split(":")
        return parts[1] if len(parts) > 1 else ""


def _resolve_model(cfg: dict[str, Any], runtime: Any) -> tuple[str, str]:
    if runtime:
        provider = getattr(runtime, "provider", None) or getattr(runtime, "default_provider", None)
        model = getattr(runtime, "model", None) or getattr(runtime, "default_model", None)
        if provider and model:
            return str(provider), str(model)
    # From config
    if cfg:
        agents_cfg = cfg.get("agents", {}).get("defaults", {})
        model_cfg = agents_cfg.get("model", {})
        primary = model_cfg.get("primary") or ""
        if "/" in primary:
            parts = primary.split("/", 1)
            return parts[0], parts[1]
    return "google", "gemini-2.0-flash"


def _load_session_entry(session_key: str, cfg: dict[str, Any]) -> dict | None:
    if not session_key:
        return None
    try:
        from openclaw.config.sessions import load_session_store, resolve_store_path
        store_path = resolve_store_path(cfg.get("session", {}).get("store"), {})
        store = load_session_store(store_path)
        return store.get(session_key.lower()) or store.get(session_key)
    except Exception:
        pass
    return None


def _format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds // 60)}m {int(seconds % 60)}s"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    return f"{h}h {m}m"


# ---------------------------------------------------------------------------
# /usage off|tokens|full|cost
# Mirrors TS handleUsageCommand() — per-response usage footer toggle
# ---------------------------------------------------------------------------

async def _handle_usage(
    args: str,
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
) -> ReplyPayload:
    """Control per-response usage footer or show local cost summary.

    /usage           — show current mode
    /usage off       — disable usage footer
    /usage tokens    — show token counts only
    /usage full      — show tokens + cost estimate
    /usage cost      — print local cost summary from session logs
    """
    mode = args.strip().lower()

    if mode == "cost":
        return await _usage_cost_summary(session_key, cfg)

    if not mode:
        # Show current setting
        try:
            entry = _load_session_entry(session_key, cfg)
            current = (entry or {}).get("responseUsage") or "off"
            return ReplyPayload(text=f"Usage footer: {current}")
        except Exception:
            return ReplyPayload(text="Usage footer: off")

    valid = ("off", "tokens", "full", "on")
    if mode not in valid:
        return ReplyPayload(text="Usage: /usage off|tokens|full|cost")

    normalized = "tokens" if mode == "on" else mode
    try:
        from openclaw.agents.sessions import patch_session_entry
        patch_session_entry(session_key, {"responseUsage": normalized}, cfg)
        return ReplyPayload(text=f"Usage footer: {normalized}")
    except Exception as exc:
        logger.warning(f"/usage error: {exc}")
        return ReplyPayload(text=f"Usage mode set to {normalized} (may not persist — {exc})")


async def _usage_cost_summary(session_key: str, cfg: dict[str, Any]) -> ReplyPayload:
    """Show local cost summary from session logs."""
    try:
        from openclaw.agents.session_store import load_all_sessions
        sessions = load_all_sessions(cfg)
        total_input = 0
        total_output = 0
        for s in sessions.values():
            if isinstance(s, dict):
                total_input += s.get("inputTokens") or 0
                total_output += s.get("outputTokens") or 0
        lines = [
            "📊 Local cost summary (all sessions):",
            f"  Input tokens:  {total_input:,}",
            f"  Output tokens: {total_output:,}",
            f"  Total tokens:  {total_input + total_output:,}",
            "",
            "Note: Actual cost depends on provider and model pricing.",
        ]
        return ReplyPayload(text="\n".join(lines))
    except Exception as exc:
        return ReplyPayload(text=f"Could not load cost summary: {exc}")


# ---------------------------------------------------------------------------
# /skill <name> [input] — run a skill by name
# Mirrors TS handleSkillCommand()
# ---------------------------------------------------------------------------

async def _handle_skill(
    args: str,
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
    runtime: Any,
) -> ReplyPayload:
    """Run a skill by name. Forwards to the agent as a skill invocation.

    /skill <name>         — invoke skill with no input
    /skill <name> <input> — invoke skill with input text
    """
    parts = args.strip().split(None, 1)
    if not parts:
        return ReplyPayload(text="Usage: /skill <name> [input]")

    skill_name = parts[0]
    skill_input = parts[1].strip() if len(parts) > 1 else ""

    # Look up skill path from runtime or skills registry
    try:
        from openclaw.agents.skills import resolve_skill_path
        skill_path = resolve_skill_path(skill_name, cfg)
        if not skill_path:
            return ReplyPayload(text=f"Skill not found: {skill_name}")

        # Forward to the agent as a skill run request
        message = f"Run skill: {skill_name}"
        if skill_input:
            message += f"\nInput: {skill_input}"

        return ReplyPayload(
            text=None,
            forward_to_agent=True,
            forward_message=message,
            forward_context={"skillName": skill_name, "skillInput": skill_input},
        )
    except ImportError:
        # Skills module not available — forward as plain message
        prompt = f"Please run the '{skill_name}' skill"
        if skill_input:
            prompt += f" with input: {skill_input}"
        return ReplyPayload(
            text=None,
            forward_to_agent=True,
            forward_message=prompt,
        )
    except Exception as exc:
        logger.warning(f"/skill error: {exc}")
        return ReplyPayload(text=f"Skill '{skill_name}' failed: {exc}")
