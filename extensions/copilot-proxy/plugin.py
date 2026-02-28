"""Copilot Proxy extension — Local Copilot Proxy (VS Code LM) provider plugin.

Mirrors TypeScript: openclaw/extensions/copilot-proxy/index.ts

Registers an OpenAI-compatible provider that routes requests through a local
Copilot Proxy server (e.g. the VS Code Copilot extension running
``/v1/chat/completions``).

Configuration (in openclaw.json)::

    {
      "models": {
        "providers": {
          "copilot-proxy": {
            "baseUrl": "http://localhost:3000/v1",
            "apiKey": "n/a",
            "api": "openai-completions",
            "authHeader": false,
            "models": [...]
          }
        }
      }
    }
"""
from __future__ import annotations

import re
from typing import Any


DEFAULT_BASE_URL = "http://localhost:3000/v1"
DEFAULT_API_KEY = "n/a"
DEFAULT_CONTEXT_WINDOW = 128_000
DEFAULT_MAX_TOKENS = 8192
DEFAULT_MODEL_IDS: list[str] = [
    "gpt-5.2",
    "gpt-5.2-codex",
    "gpt-5.1",
    "gpt-5.1-codex",
    "gpt-5.1-codex-max",
    "gpt-5-mini",
    "claude-opus-4.6",
    "claude-opus-4.5",
    "claude-sonnet-4.5",
    "claude-haiku-4.5",
    "gemini-3-pro",
    "gemini-3-flash",
    "grok-code-fast-1",
]


def _normalize_base_url(value: str) -> str:
    """Ensure base URL ends with /v1 — mirrors TS normalizeBaseUrl()."""
    trimmed = value.strip().rstrip("/")
    if not trimmed:
        return DEFAULT_BASE_URL
    if not trimmed.endswith("/v1"):
        trimmed = f"{trimmed}/v1"
    return trimmed


def _parse_model_ids(raw: str) -> list[str]:
    """Parse comma/newline-separated model IDs — mirrors TS parseModelIds()."""
    seen: dict[str, None] = {}
    for part in re.split(r"[\n,]", raw):
        m = part.strip()
        if m and m not in seen:
            seen[m] = None
    return list(seen)


def _build_model_definition(model_id: str) -> dict[str, Any]:
    return {
        "id": model_id,
        "name": model_id,
        "api": "openai-completions",
        "reasoning": False,
        "input": ["text", "image"],
        "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
        "contextWindow": DEFAULT_CONTEXT_WINDOW,
        "maxTokens": DEFAULT_MAX_TOKENS,
    }


def register(api) -> None:
    from openclaw.plugins.types import ProviderPlugin, ProviderAuthMethod

    # Read config from PluginApi config dict
    config: dict = {}
    if hasattr(api, "_config"):
        config = api._config or {}
    elif hasattr(api, "context") and api.context:
        config = api.context.config or {}

    plugin_cfg = config.get("copilot-proxy", {}) if isinstance(config, dict) else {}

    raw_base_url: str = plugin_cfg.get("baseUrl", DEFAULT_BASE_URL)
    raw_model_ids: str = plugin_cfg.get("modelIds", ", ".join(DEFAULT_MODEL_IDS))

    base_url = _normalize_base_url(raw_base_url)
    model_ids = _parse_model_ids(raw_model_ids) or list(DEFAULT_MODEL_IDS)

    provider = ProviderPlugin(
        id="copilot-proxy",
        label="Copilot Proxy",
        docs_path="/providers/models",
        auth=[
            ProviderAuthMethod(
                id="local",
                label="Local proxy",
                kind="custom",
                hint=f"Base URL: {base_url} — edit models.providers.copilot-proxy to change",
            )
        ],
        models={
            mid: _build_model_definition(mid)
            for mid in model_ids
        },
    )
    api.register_provider(provider)

plugin = {
    "id": "copilot-proxy",
    "name": "Copilot Proxy",
    "description": "Local VS Code Copilot Proxy provider plugin.",
    "register": register,
}
