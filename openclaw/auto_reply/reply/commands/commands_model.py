"""Model / thinking commands.

Port of TypeScript:
  commands-models.ts → /model, /models
  directive-handling.model.ts → maybeHandleModelDirectiveInfo,
                                resolveModelSelectionFromDirective
  directive-handling.levels.ts → /think, /verbose, /reasoning
"""
from __future__ import annotations

import logging
import re
from typing import Any, TypedDict

from ..get_reply import ReplyPayload

logger = logging.getLogger(__name__)

# Mirrors TS ThinkLevel: "off"|"minimal"|"low"|"medium"|"high"|"xhigh"
_THINK_LEVELS = {"off", "minimal", "low", "medium", "high", "xhigh"}
# Mirrors TS VerboseLevel: "off"|"on"|"full"
_VERBOSE_LEVELS = {"off", "on", "full"}


def _build_model_alias_index_from_cfg(cfg: Any) -> dict[str, Any]:
    """Build alias index from config using model_selection module."""
    try:
        from openclaw.agents.model_selection import build_model_alias_index, DEFAULT_PROVIDER
        return build_model_alias_index(cfg if isinstance(cfg, dict) else {}, DEFAULT_PROVIDER)
    except Exception:
        from openclaw.agents.model_selection import ModelAliasIndex
        return ModelAliasIndex()


def build_model_alias_index(cfg: Any) -> Any:
    """Build and return a model alias index from config."""
    return _build_model_alias_index_from_cfg(cfg)


# ---------------------------------------------------------------------------
# Config-driven alias lookup — replaces old hardcoded _MODEL_ALIASES dict
# ---------------------------------------------------------------------------

def get_model_aliases(cfg: Any | None) -> dict[str, str]:
    """Return resolved alias→model mapping from config.

    Mirrors TS buildModelAliasIndex() but returns a plain dict for CLI use.
    Falls back to built-in defaults if config provides no aliases.
    """
    aliases: dict[str, str] = {}
    if cfg and isinstance(cfg, dict):
        alias_idx = _build_model_alias_index_from_cfg(cfg)
        for alias_lower, entry in (alias_idx.by_alias or {}).items():
            ref = entry.get("ref")
            if ref:
                aliases[alias_lower] = f"{ref.provider}/{ref.model}"

    if not aliases:
        # Built-in defaults (kept for zero-config environments)
        aliases = {
            "flash": "google/gemini-2.0-flash",
            "flash-lite": "google/gemini-2.0-flash-lite",
            "pro": "google/gemini-1.5-pro",
            "gemini": "google/gemini-2.0-flash",
            "opus": "anthropic/claude-opus-4-5",
            "sonnet": "anthropic/claude-sonnet-4-5",
            "haiku": "anthropic/claude-haiku-3-5",
            "claude": "anthropic/claude-sonnet-4-5",
            "gpt4": "openai/gpt-4",
            "gpt4o": "openai/gpt-4o",
            "gpt4o-mini": "openai/gpt-4o-mini",
            "o1": "openai/o1",
            "o3": "openai/o3",
        }
    return aliases

async def handle_model_command(
    name: str,
    args: str,
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
    runtime: Any,
) -> ReplyPayload | None:
    if name in ("model", "m", "models"):
        if name == "models" and not args.strip():
            return await _handle_list_models(ctx, cfg)
        return await _handle_set_model(args, ctx, cfg, session_key)
    if name in ("think", "thinking", "t"):
        return await _handle_think(args, ctx, cfg, session_key)
    if name in ("verbose", "v"):
        return await _handle_verbose(args, ctx, cfg, session_key)
    if name in ("reasoning", "reason"):
        return await _handle_reasoning(args, ctx, cfg, session_key)
    if name in ("elevated", "elev"):
        return await _handle_elevated(args, ctx, cfg, session_key)
    if name == "exec":
        return await _handle_exec_directive(args, ctx, cfg, session_key)
    return None


# ---------------------------------------------------------------------------
# /model [model-name]
# ---------------------------------------------------------------------------

async def _handle_set_model(
    args: str,
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
) -> ReplyPayload:
    if not args:
        return await _handle_current_model(ctx, cfg, session_key)

    raw = args.strip()
    model_aliases = get_model_aliases(cfg)
    resolved = model_aliases.get(raw.lower(), raw)
    if "/" not in resolved:
        resolved = f"google/{resolved}"

    provider, model = resolved.split("/", 1)

    try:
        _update_session_model(session_key, cfg, provider=provider, model=model)
        return ReplyPayload(text=f"Model set to {provider}/{model}")
    except Exception as exc:
        logger.warning(f"/model set error: {exc}")
        return ReplyPayload(text=f"Could not set model: {exc}")


async def _handle_current_model(
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
) -> ReplyPayload:
    """Show current model."""
    provider, model = _resolve_current_model(cfg, session_key)
    return ReplyPayload(text=f"Current model: {provider}/{model}")


async def _handle_list_models(ctx: Any, cfg: dict[str, Any]) -> ReplyPayload:
    """List available models."""
    lines = ["Available models:"]
    lines.append("\nGoogle Gemini:")
    lines.append("  google/gemini-2.0-flash       (flash)")
    lines.append("  google/gemini-2.0-flash-lite  (flash-lite)")
    lines.append("  google/gemini-1.5-pro         (pro)")
    lines.append("\nAnthropic Claude:")
    lines.append("  anthropic/claude-opus-4-5     (opus)")
    lines.append("  anthropic/claude-sonnet-4-5   (sonnet, claude)")
    lines.append("  anthropic/claude-haiku-3-5    (haiku)")
    lines.append("\nOpenAI:")
    lines.append("  openai/gpt-4o                 (gpt4o)")
    lines.append("  openai/gpt-4o-mini            (gpt4o-mini)")
    lines.append("  openai/o1                     (o1)")
    lines.append("\nUsage: /model <name-or-alias>")
    return ReplyPayload(text="\n".join(lines))


# ---------------------------------------------------------------------------
# /think [off|low|medium|high]
# ---------------------------------------------------------------------------

def _normalize_think_level(raw: str) -> str | None:
    """Mirrors TS normalizeThinkLevel: 'off'|'minimal'|'low'|'medium'|'high'|'xhigh'."""
    key = raw.strip().lower()
    if not key:
        return None
    if key in ("off", "false", "no", "0", "none", "disable", "disabled"):
        return "off"
    if key in ("minimal", "min"):
        return "minimal"
    if key in ("low", "lite", "light", "quick"):
        return "low"
    if key in ("medium", "med", "default", "normal"):
        return "medium"
    if key in ("high", "deep", "extended"):
        return "high"
    if key in ("xhigh", "extra-high", "max", "maximum", "extreme"):
        return "xhigh"
    return None


async def _handle_think(
    args: str,
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
) -> ReplyPayload:
    raw = args.strip()
    if not raw:
        entry = _load_session_entry(session_key, cfg)
        current = (entry or {}).get("thinkLevel") or "medium"
        return ReplyPayload(text=f"Think: {current}")
    level = _normalize_think_level(raw)
    if level is None:
        return ReplyPayload(text=f"Invalid think level: {raw}\nChoose from: off, minimal, low, medium, high, xhigh")
    try:
        _update_session_field(session_key, cfg, "thinkLevel", level)
        return ReplyPayload(text=f"Think: {level}")
    except Exception as exc:
        return ReplyPayload(text=f"Could not set think level: {exc}")


# ---------------------------------------------------------------------------
# /verbose [off|on|low|medium|high]
# ---------------------------------------------------------------------------

def _normalize_verbose_level(raw: str) -> str | None:
    """Mirrors TS normalizeVerboseLevel / normalizeOnOffFullLevel."""
    key = raw.strip().lower()
    if not key:
        return None
    if key in ("off", "false", "no", "0"):
        return "off"
    if key in ("full", "all", "everything"):
        return "full"
    if key in ("on", "minimal", "true", "yes", "1"):
        return "on"
    return None


async def _handle_verbose(
    args: str,
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
) -> ReplyPayload:
    raw = args.strip()
    if not raw:
        entry = _load_session_entry(session_key, cfg)
        current = (entry or {}).get("verboseLevel") or "off"
        return ReplyPayload(text=f"Verbose: {current}")
    level = _normalize_verbose_level(raw)
    if level is None:
        return ReplyPayload(text=f"Invalid verbose level: {raw}\nChoose from: on, off, full")
    try:
        _update_session_field(session_key, cfg, "verboseLevel", level)
        return ReplyPayload(text=f"Verbose: {level}")
    except Exception as exc:
        return ReplyPayload(text=f"Could not set verbose level: {exc}")


# ---------------------------------------------------------------------------
# /reasoning [off|auto|high]
# ---------------------------------------------------------------------------

def _normalize_reasoning_level(raw: str) -> str | None:
    """Mirrors TS normalizeReasoningLevel: 'off'|'on'|'stream'."""
    key = raw.strip().lower()
    if not key:
        return None
    if key in ("off", "false", "no", "0", "hide", "hidden", "disable", "disabled"):
        return "off"
    if key in ("on", "true", "yes", "1", "show", "visible", "enable", "enabled"):
        return "on"
    if key in ("stream", "streaming", "draft", "live"):
        return "stream"
    return None


async def _handle_reasoning(
    args: str,
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
) -> ReplyPayload:
    raw = args.strip()
    if not raw:
        entry = _load_session_entry(session_key, cfg)
        current = (entry or {}).get("reasoningLevel") or "on"
        return ReplyPayload(text=f"Reasoning: {current}")
    level = _normalize_reasoning_level(raw)
    if level is None:
        return ReplyPayload(text=f"Invalid reasoning level: {raw}\nChoose from: on, off, stream")
    try:
        _update_session_field(session_key, cfg, "reasoningLevel", level)
        return ReplyPayload(text=f"Reasoning: {level}")
    except Exception as exc:
        return ReplyPayload(text=f"Could not set reasoning level: {exc}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_current_model(cfg: dict[str, Any], session_key: str) -> tuple[str, str]:
    # Try session entry first
    if session_key:
        try:
            entry = _load_session_entry(session_key, cfg)
            if entry:
                m = entry.get("model")
                p = entry.get("provider")
                if m and p:
                    return p, m
        except Exception:
            pass
    # Fall back to config
    if cfg:
        agents_cfg = cfg.get("agents", {}).get("defaults", {})
        primary = agents_cfg.get("model", {}).get("primary") or ""
        if "/" in primary:
            p, m = primary.split("/", 1)
            return p, m
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
        return None


def _update_session_model(session_key: str, cfg: dict[str, Any], provider: str, model: str) -> None:
    """Persist model selection to session store."""
    try:
        from openclaw.config.sessions import load_session_store, resolve_store_path, save_session_store
        import time
        store_path = resolve_store_path(cfg.get("session", {}).get("store"), {})
        store = load_session_store(store_path)
        key = session_key.lower()
        entry = store.get(key) or store.get(session_key) or {}
        entry["provider"] = provider
        entry["model"] = model
        entry["updatedAt"] = int(time.time() * 1000)
        store[key] = entry
        save_session_store(store_path, store)
    except Exception as exc:
        raise RuntimeError(f"Could not persist model: {exc}") from exc


def _update_session_field(session_key: str, cfg: dict[str, Any], field: str, value: Any) -> None:
    """Persist a single field to the session store."""
    try:
        from openclaw.config.sessions import load_session_store, resolve_store_path, save_session_store
        import time
        store_path = resolve_store_path(cfg.get("session", {}).get("store"), {})
        store = load_session_store(store_path)
        key = session_key.lower()
        entry = store.get(key) or store.get(session_key) or {}
        entry[field] = value
        entry["updatedAt"] = int(time.time() * 1000)
        store[key] = entry
        save_session_store(store_path, store)
    except Exception as exc:
        raise RuntimeError(f"Could not persist field {field}: {exc}") from exc


# ---------------------------------------------------------------------------
# Model directive data types
# ---------------------------------------------------------------------------

class ModelDirectiveSelection(TypedDict, total=False):
    provider: str
    model: str
    is_default: bool
    alias: str


# ---------------------------------------------------------------------------
# maybe_handle_model_directive_info — mirrors TS maybeHandleModelDirectiveInfo()
# ---------------------------------------------------------------------------

async def maybe_handle_model_directive_info(
    directives: dict[str, Any],
    cfg: Any,
    provider: str,
    model: str,
    default_provider: str = "google",
    default_model: str = "gemini-2.0-flash",
    surface: str | None = None,
    **_kwargs: Any,
) -> ReplyPayload | None:
    """Handle /model (summary), /model status (detailed), /model list.

    Mirrors TS maybeHandleModelDirectiveInfo().
    Returns None if the directive is not a status/summary/list request.
    """
    if not directives.get("has_model_directive"):
        return None

    raw_directive = (directives.get("raw_model_directive") or "").strip()
    directive_lower = raw_directive.lower()

    wants_status = directive_lower == "status"
    wants_summary = not raw_directive
    wants_legacy_list = directive_lower == "list"

    if not wants_summary and not wants_status and not wants_legacy_list:
        return None

    if directives.get("raw_model_profile"):
        return ReplyPayload(text="Auth profile override requires a model selection.")

    current = f"{provider}/{model}"
    is_telegram = surface == "telegram"

    if wants_legacy_list:
        return await _handle_list_models(None, cfg)

    if wants_summary:
        if is_telegram:
            return ReplyPayload(
                text="\n".join([
                    f"Current: {current}",
                    "",
                    "Tap below to browse models, or use:",
                    "/model <provider/model> to switch",
                    "/model status for details",
                ])
            )
        return ReplyPayload(
            text="\n".join([
                f"Current: {current}",
                "",
                "Switch: /model <provider/model>",
                "Browse: /models (providers) or /models <provider> (models)",
                "More: /model status",
            ])
        )

    # wants_status — detailed view
    lines = [f"Current: {current}"]
    default_label = f"{default_provider}/{default_model}"
    if current != default_label:
        lines.append(f"Default: {default_label}")

    cfg_dict = cfg if isinstance(cfg, dict) else {}
    agent_model = cfg_dict.get("agents", {}).get("defaults", {}).get("model")
    if agent_model:
        if isinstance(agent_model, str):
            lines.append(f"Agent: {agent_model}")
        elif isinstance(agent_model, dict):
            primary = agent_model.get("primary")
            if primary:
                lines.append(f"Agent: {primary}")

    lines.extend(["", "Switch: /model <provider/model>", "Browse: /models"])
    return ReplyPayload(text="\n".join(lines))


# ---------------------------------------------------------------------------
# resolve_model_selection_from_directive — mirrors TS resolveModelSelectionFromDirective()
# ---------------------------------------------------------------------------

def resolve_model_selection_from_directive(
    directives: dict[str, Any],
    cfg: Any,
    default_provider: str = "google",
    default_model: str = "gemini-2.0-flash",
    allowed_model_keys: set[str] | None = None,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Validate and resolve a model directive into a selection.

    Mirrors TS resolveModelSelectionFromDirective().
    Returns {"model_selection": ..., "profile_override": ..., "error_text": ...}.
    """
    has_directive = directives.get("has_model_directive", False)
    raw_model_directive = (directives.get("raw_model_directive") or "").strip()
    raw_model_profile = (directives.get("raw_model_profile") or "").strip()

    if not has_directive or not raw_model_directive:
        if raw_model_profile:
            return {"error_text": "Auth profile override requires a model selection."}
        return {}

    raw = raw_model_directive

    # Reject numeric selection
    if re.fullmatch(r"[0-9]+", raw):
        return {
            "error_text": "\n".join([
                "Numeric model selection is not supported in chat.",
                "",
                "Browse: /models or /models <provider>",
                "Switch: /model <provider/model>",
            ])
        }

    # Resolve via model_selection
    try:
        from openclaw.agents.model_selection import (
            model_key,
            resolve_model_ref_from_string,
            build_model_alias_index,
        )
        alias_index = build_model_alias_index(
            cfg if isinstance(cfg, dict) else {},
            default_provider,
        )
        explicit = resolve_model_ref_from_string(raw, default_provider, alias_index)
    except Exception:
        explicit = None

    model_selection: ModelDirectiveSelection | None = None

    if explicit:
        ref = explicit["ref"]
        explicit_key = f"{ref.provider}/{ref.model}"
        if not allowed_model_keys or explicit_key in allowed_model_keys:
            model_selection = ModelDirectiveSelection(
                provider=ref.provider,
                model=ref.model,
                is_default=(
                    ref.provider == default_provider and ref.model == default_model
                ),
            )
            if explicit.get("alias"):
                model_selection["alias"] = explicit["alias"]

    if not model_selection:
        return {
            "error_text": "\n".join([
                f"Unknown model: {raw}",
                "",
                "Browse: /models or /models <provider>",
                "Switch: /model <provider/model>",
            ])
        }

    profile_override: str | None = None
    if raw_model_profile:
        profile_override = raw_model_profile or None

    return {"model_selection": model_selection, "profile_override": profile_override}


# ---------------------------------------------------------------------------
# /elevated on|off|ask|full — exec elevation mode
# Mirrors TS handleElevatedDirective()
# ---------------------------------------------------------------------------

async def _handle_elevated(
    args: str,
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
) -> ReplyPayload:
    """Set or show the elevated exec mode for this session.

    Modes:
      on   — same as 'ask' (prompt before each exec)
      off  — no elevation
      ask  — prompt before each exec
      full — skip exec approval prompts (most permissive)
    """
    mode = args.strip().lower()

    if not mode:
        try:
            entry = _load_session_entry_for_model(session_key, cfg)
            current = (entry or {}).get("elevatedLevel") or "off"
            return ReplyPayload(text=f"Elevated exec mode: {current}")
        except Exception:
            return ReplyPayload(text="Elevated exec mode: off")

    valid = ("on", "off", "ask", "full")
    if mode not in valid:
        return ReplyPayload(text="Usage: /elevated on|off|ask|full")

    normalized = "ask" if mode == "on" else mode
    try:
        from openclaw.agents.sessions import patch_session_entry
        patch_session_entry(session_key, {"elevatedLevel": normalized}, cfg)
        return ReplyPayload(text=f"Elevated exec mode: {normalized}")
    except Exception as exc:
        logger.warning(f"/elevated error: {exc}")
        return ReplyPayload(text=f"Elevated: {normalized} (may not persist — {exc})")


# ---------------------------------------------------------------------------
# /exec host=<sandbox|gateway|node> security=<deny|allowlist|full> ask=<...>
# Mirrors TS handleExecDirective()
# ---------------------------------------------------------------------------

async def _handle_exec_directive(
    args: str,
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
) -> ReplyPayload:
    """Show or override exec settings for this session."""
    if not args.strip():
        # Show current
        try:
            entry = _load_session_entry_for_model(session_key, cfg)
            e = entry or {}
            host = e.get("execHost") or "gateway"
            security = e.get("execSecurity") or "allowlist"
            ask = e.get("execAsk") or "on-miss"
            node = e.get("execNode") or ""
            lines = [
                f"Exec settings:",
                f"  host={host}",
                f"  security={security}",
                f"  ask={ask}",
            ]
            if node:
                lines.append(f"  node={node}")
            return ReplyPayload(text="\n".join(lines))
        except Exception:
            return ReplyPayload(text="Exec settings: (default)")

    # Parse key=value pairs
    updates: dict[str, str] = {}
    for token in args.split():
        if "=" in token:
            k, v = token.split("=", 1)
            key_map = {"host": "execHost", "security": "execSecurity", "ask": "execAsk", "node": "execNode"}
            if k in key_map:
                updates[key_map[k]] = v

    if not updates:
        return ReplyPayload(text="Usage: /exec host=<sandbox|gateway|node> security=<deny|allowlist|full> ask=<off|on-miss|always>")

    try:
        from openclaw.agents.sessions import patch_session_entry
        patch_session_entry(session_key, updates, cfg)
        parts = [f"{k.replace('exec', '').lower()}={v}" for k, v in updates.items()]
        return ReplyPayload(text=f"Exec updated: {', '.join(parts)}")
    except Exception as exc:
        logger.warning(f"/exec error: {exc}")
        return ReplyPayload(text=f"Exec update failed: {exc}")


def _load_session_entry_for_model(session_key: str, cfg: dict[str, Any]) -> dict | None:
    """Load session entry (shared helper for model commands)."""
    if not session_key:
        return None
    try:
        from openclaw.config.sessions import load_session_store, resolve_store_path
        store_path = resolve_store_path(cfg.get("session", {}).get("store"), {})
        store = load_session_store(store_path)
        return store.get(session_key.lower()) or store.get(session_key)
    except Exception:
        return None
