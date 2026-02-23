"""Model / thinking commands.

Port of TypeScript:
  commands-models.ts → /model, /models
  directive-handling.model-picker.ts → model picker
  directive-handling.levels.ts → /think, /verbose, /reasoning
"""
from __future__ import annotations

import logging
from typing import Any

from ..get_reply import ReplyPayload

logger = logging.getLogger(__name__)

# Known model shortcuts
_MODEL_ALIASES: dict[str, str] = {
    "flash": "google/gemini-2.0-flash",
    "flash-lite": "google/gemini-2.0-flash-lite",
    "flash-exp": "google/gemini-2.0-flash",
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

_THINK_LEVELS = {"off", "low", "medium", "high"}
_VERBOSE_LEVELS = {"off", "on", "low", "medium", "high"}


async def handle_model_command(
    name: str,
    args: str,
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
    runtime: Any,
) -> ReplyPayload | None:
    if name in ("model", "m"):
        return await _handle_set_model(args, ctx, cfg, session_key)
    if name == "models":
        return await _handle_list_models(ctx, cfg)
    if name == "think":
        return await _handle_think(args, ctx, cfg, session_key)
    if name == "verbose":
        return await _handle_verbose(args, ctx, cfg, session_key)
    if name == "reasoning":
        return await _handle_reasoning(args, ctx, cfg, session_key)
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
    resolved = _MODEL_ALIASES.get(raw.lower(), raw)
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

async def _handle_think(
    args: str,
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
) -> ReplyPayload:
    level = args.strip().lower()
    if not level:
        # Show current
        entry = _load_session_entry(session_key, cfg)
        current = (entry or {}).get("thinkLevel") or "medium"
        return ReplyPayload(text=f"Current thinking level: {current}")
    if level not in _THINK_LEVELS:
        return ReplyPayload(text=f"Invalid think level: {level}\nChoose from: {', '.join(_THINK_LEVELS)}")
    try:
        _update_session_field(session_key, cfg, "thinkLevel", level)
        return ReplyPayload(text=f"Thinking level set to: {level}")
    except Exception as exc:
        return ReplyPayload(text=f"Could not set think level: {exc}")


# ---------------------------------------------------------------------------
# /verbose [off|on|low|medium|high]
# ---------------------------------------------------------------------------

async def _handle_verbose(
    args: str,
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
) -> ReplyPayload:
    level = args.strip().lower()
    if not level:
        entry = _load_session_entry(session_key, cfg)
        current = (entry or {}).get("verboseLevel") or "off"
        return ReplyPayload(text=f"Current verbose level: {current}")
    if level not in _VERBOSE_LEVELS:
        return ReplyPayload(text=f"Invalid verbose level: {level}\nChoose from: {', '.join(_VERBOSE_LEVELS)}")
    try:
        _update_session_field(session_key, cfg, "verboseLevel", level)
        return ReplyPayload(text=f"Verbose level set to: {level}")
    except Exception as exc:
        return ReplyPayload(text=f"Could not set verbose level: {exc}")


# ---------------------------------------------------------------------------
# /reasoning [off|auto|high]
# ---------------------------------------------------------------------------

async def _handle_reasoning(
    args: str,
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
) -> ReplyPayload:
    level = args.strip().lower()
    valid = {"off", "auto", "high"}
    if not level:
        entry = _load_session_entry(session_key, cfg)
        current = (entry or {}).get("reasoningLevel") or "auto"
        return ReplyPayload(text=f"Current reasoning level: {current}")
    if level not in valid:
        return ReplyPayload(text=f"Invalid reasoning level: {level}\nChoose from: {', '.join(valid)}")
    try:
        _update_session_field(session_key, cfg, "reasoningLevel", level)
        return ReplyPayload(text=f"Reasoning level set to: {level}")
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
