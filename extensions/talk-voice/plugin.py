"""talk-voice extension — list/set ElevenLabs Talk voice.

Mirrors TypeScript: openclaw/extensions/talk-voice/index.ts
"""
from __future__ import annotations

import asyncio
from typing import Any

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mask(s: str, keep: int = 6) -> str:
    trimmed = s.strip()
    if len(trimmed) <= keep:
        return "***"
    return f"{trimmed[:keep]}\u2026"


def _is_likely_voice_id(value: str) -> bool:
    v = value.strip()
    if not (10 <= len(v) <= 64):
        return False
    import re
    return bool(re.match(r"^[a-zA-Z0-9_-]+$", v))


async def _list_voices(api_key: str) -> list[dict]:
    """Fetch ElevenLabs voice list."""
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.elevenlabs.io/v1/voices",
                headers={"xi-api-key": api_key},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if not resp.ok:
                    raise RuntimeError(f"ElevenLabs voices API error ({resp.status})")
                data = await resp.json()
                voices = data.get("voices") if isinstance(data, dict) else None
                return voices if isinstance(voices, list) else []
    except ImportError:
        pass

    # Fallback: httpx
    try:
        import httpx
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.elevenlabs.io/v1/voices",
                headers={"xi-api-key": api_key},
            )
            resp.raise_for_status()
            data = resp.json()
            voices = data.get("voices") if isinstance(data, dict) else None
            return voices if isinstance(voices, list) else []
    except ImportError:
        pass

    # Fallback: urllib (sync, run in executor)
    import json
    import urllib.request

    def _fetch() -> list[dict]:
        req = urllib.request.Request(
            "https://api.elevenlabs.io/v1/voices",
            headers={"xi-api-key": api_key},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            voices = data.get("voices") if isinstance(data, dict) else None
            return voices if isinstance(voices, list) else []

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch)


def _format_voice_list(voices: list[dict], limit: int) -> str:
    limit = max(1, min(limit, 50))
    sliced = voices[:limit]
    lines: list[str] = [f"Voices: {len(voices)}", ""]
    for v in sliced:
        name = (v.get("name") or "").strip() or "(unnamed)"
        category = (v.get("category") or "").strip()
        meta = f" \u00b7 {category}" if category else ""
        lines.append(f"- {name}{meta}")
        lines.append(f"  id: {v.get('voice_id', '')}")
    if len(voices) > len(sliced):
        lines.append("")
        lines.append(f"(showing first {len(sliced)})")
    return "\n".join(lines)


def _find_voice(voices: list[dict], query: str) -> dict | None:
    q = query.strip()
    if not q:
        return None
    lower = q.lower()
    # Exact voice_id
    for v in voices:
        if v.get("voice_id") == q:
            return v
    # Exact name (case-insensitive)
    for v in voices:
        if (v.get("name") or "").strip().lower() == lower:
            return v
    # Partial name
    for v in voices:
        if lower in (v.get("name") or "").strip().lower():
            return v
    return None


def _load_config():
    try:
        from openclaw.config.loader import load_config
        return load_config()
    except Exception:
        return None


def _config_to_dict(cfg) -> dict:
    if isinstance(cfg, dict):
        return cfg
    if hasattr(cfg, "model_dump"):
        return cfg.model_dump()
    if hasattr(cfg, "__dict__"):
        return cfg.__dict__
    return {}


async def _write_config(cfg_dict: dict) -> None:
    try:
        from openclaw.config.loader import write_config_file
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, write_config_file, cfg_dict)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

def register(api) -> None:
    from openclaw.plugins.types import OpenClawPluginCommandDefinition

    async def handle_voice(ctx) -> dict:
        args = (getattr(ctx, "args", None) or "").strip()
        tokens = [t for t in args.split() if t]
        action = (tokens[0].lower() if tokens else "status")

        cfg = _load_config()
        cfg_dict = _config_to_dict(cfg) if cfg is not None else {}

        talk_cfg = cfg_dict.get("talk") or {}
        api_key = (talk_cfg.get("apiKey") or "").strip()

        if not api_key:
            return {
                "text": (
                    "Talk voice is not configured.\n\n"
                    "Missing: talk.apiKey (ElevenLabs API key).\n"
                    "Set it on the gateway, then retry."
                )
            }

        current_voice_id = (talk_cfg.get("voiceId") or "").strip()

        if action == "status":
            return {
                "text": (
                    "Talk voice status:\n"
                    f"- talk.voiceId: {current_voice_id if current_voice_id else '(unset)'}\n"
                    f"- talk.apiKey: {_mask(api_key)}"
                )
            }

        if action == "list":
            limit_raw = tokens[1] if len(tokens) > 1 else "12"
            try:
                limit = int(limit_raw)
            except ValueError:
                limit = 12
            voices = await _list_voices(api_key)
            return {"text": _format_voice_list(voices, limit)}

        if action == "set":
            query = " ".join(tokens[1:]).strip()
            if not query:
                return {"text": "Usage: /voice set <voiceId|name>"}
            voices = await _list_voices(api_key)
            chosen = _find_voice(voices, query)
            if not chosen:
                hint = query if _is_likely_voice_id(query) else f'"{query}"'
                return {"text": f"No voice found for {hint}. Try: /voice list"}

            import copy
            next_cfg = copy.deepcopy(cfg_dict)
            talk = next_cfg.setdefault("talk", {})
            talk["voiceId"] = chosen["voice_id"]
            await _write_config(next_cfg)

            name = (chosen.get("name") or "").strip() or "(unnamed)"
            return {"text": f"\u2705 Talk voice set to {name}\n{chosen['voice_id']}"}

        return {
            "text": "\n".join([
                "Voice commands:",
                "",
                "/voice status",
                "/voice list [limit]",
                "/voice set <voiceId|name>",
            ])
        }

    api.register_command(OpenClawPluginCommandDefinition(
        name="voice",
        description="List/set ElevenLabs Talk voice (affects iOS Talk playback).",
        handler=handle_voice,
        accepts_args=True,
    ))


plugin = {
    "id": "talk-voice",
    "name": "Talk Voice",
    "description": "Manage Talk voice selection (list/set).",
    "register": register,
}
