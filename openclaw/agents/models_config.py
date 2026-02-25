"""Models config writer — ensures models.json is up-to-date in the agent dir.

Aligned with TypeScript openclaw/src/agents/models-config.ts.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_MODE = "merge"


# ---------------------------------------------------------------------------
# Provider model merging helpers — mirrors TS mergeProviderModels / mergeProviders
# ---------------------------------------------------------------------------

def merge_provider_models(
    implicit: dict[str, Any],
    explicit: dict[str, Any],
) -> dict[str, Any]:
    """Merge two ProviderConfig dicts, deduplicating models by id.

    Explicit entries take precedence; implicit entries fill in missing models.
    Mirrors TS mergeProviderModels().
    """
    implicit_models: list[Any] = implicit.get("models") or []
    explicit_models: list[Any] = explicit.get("models") or []

    if not implicit_models:
        return {**implicit, **explicit}

    def get_id(model: Any) -> str:
        if not isinstance(model, dict):
            return ""
        return str(model.get("id") or "").strip()

    seen: set[str] = {get_id(m) for m in explicit_models if get_id(m)}
    extra = [
        m for m in implicit_models
        if get_id(m) and get_id(m) not in seen
    ]
    merged_models = list(explicit_models) + extra
    return {**implicit, **explicit, "models": merged_models}


def merge_providers(
    implicit: dict[str, Any] | None,
    explicit: dict[str, Any] | None,
) -> dict[str, Any]:
    """Merge implicit and explicit provider dicts.

    Mirrors TS mergeProviders().
    """
    out: dict[str, Any] = dict(implicit or {})
    for key, explicit_entry in (explicit or {}).items():
        provider_key = key.strip()
        if not provider_key:
            continue
        existing = out.get(provider_key)
        out[provider_key] = (
            merge_provider_models(existing, explicit_entry)
            if existing is not None
            else explicit_entry
        )
    return out


# ---------------------------------------------------------------------------
# Implicit provider discovery (Python equivalent of models-config.providers.ts)
# ---------------------------------------------------------------------------

def _resolve_implicit_providers(
    agent_dir: str,
    explicit_providers: dict[str, Any],
) -> dict[str, Any]:
    """Discover implicit provider configs that are present in the environment.

    Returns a dict of provider_id -> ProviderConfig. Checks environment for
    API keys and injects well-known default model lists.
    """
    implicit: dict[str, Any] = {}

    # Anthropic
    if not explicit_providers.get("anthropic"):
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if anthropic_key:
            implicit["anthropic"] = {
                "apiKey": anthropic_key,
                "models": [
                    {"id": "claude-opus-4-5", "name": "Claude Opus 4.5",
                     "input": ["text", "image"], "reasoning": True},
                    {"id": "claude-sonnet-4-5", "name": "Claude Sonnet 4.5",
                     "input": ["text", "image"], "reasoning": True},
                ],
            }

    # OpenAI
    if not explicit_providers.get("openai"):
        openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if openai_key:
            implicit["openai"] = {
                "apiKey": openai_key,
                "models": [
                    {"id": "gpt-4o", "name": "GPT-4o", "input": ["text", "image"]},
                    {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "input": ["text", "image"]},
                    {"id": "o1", "name": "o1", "input": ["text"], "reasoning": True},
                ],
            }

    # Google Gemini
    if not explicit_providers.get("google"):
        gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if gemini_key:
            implicit["google"] = {
                "apiKey": gemini_key,
                "models": [
                    {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro",
                     "input": ["text", "image"], "reasoning": True},
                    {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash",
                     "input": ["text", "image"]},
                ],
            }

    # Ollama (no auth required, local endpoint)
    if not explicit_providers.get("ollama"):
        ollama_base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        # Only include if explicitly pointed to or if default port is reachable
        implicit["ollama"] = {
            "baseUrl": ollama_base,
            "models": [],  # Populated at runtime by Ollama client
        }

    return implicit


def _normalize_providers(
    providers: dict[str, Any],
    agent_dir: str,
) -> dict[str, Any]:
    """Post-process providers dict before writing to models.json.

    Strips empty model lists if provider has no models.
    """
    out: dict[str, Any] = {}
    for provider_id, config in providers.items():
        if not isinstance(config, dict):
            continue
        models = config.get("models")
        if isinstance(models, list) and len(models) == 0:
            # If we have no models but have a baseUrl / apiKey, keep provider
            if config.get("baseUrl") or config.get("apiKey"):
                out[provider_id] = config
        else:
            out[provider_id] = config
    return out


# ---------------------------------------------------------------------------
# Main entry point — mirrors TS ensureOpenClawModelsJson
# ---------------------------------------------------------------------------

async def ensure_openclaw_models_json(
    config: Any = None,
    agent_dir_override: str | None = None,
) -> dict[str, Any]:
    """Write (or update) {agentDir}/models.json based on config + implicit discovery.

    Mirrors TS ensureOpenClawModelsJson().
    Returns {"agent_dir": str, "wrote": bool}.
    """
    from .agent_paths import resolve_openclaw_agent_dir

    if config is None:
        try:
            from openclaw.config.loader import load_config
            config = load_config(as_dict=True)
        except Exception:
            config = {}

    agent_dir = (
        agent_dir_override.strip()
        if agent_dir_override and agent_dir_override.strip()
        else resolve_openclaw_agent_dir()
    )

    cfg = config if isinstance(config, dict) else {}
    explicit_providers: dict[str, Any] = {}
    models_section = cfg.get("models") or {}
    if isinstance(models_section, dict):
        explicit_providers = models_section.get("providers") or {}

    implicit_providers = _resolve_implicit_providers(agent_dir, explicit_providers)
    providers = merge_providers(implicit_providers, explicit_providers)

    # Bedrock: check for AWS credentials (simplified — TS does full SDK discovery)
    if not providers.get("amazon-bedrock"):
        if os.environ.get("AWS_ACCESS_KEY_ID") or os.environ.get("AWS_PROFILE"):
            aws_region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
            providers["amazon-bedrock"] = {
                "region": aws_region,
                "models": [],
            }

    if not providers:
        return {"agent_dir": agent_dir, "wrote": False}

    mode = "merge"
    if isinstance(models_section, dict):
        mode = models_section.get("mode") or _DEFAULT_MODE

    target_path = Path(agent_dir) / "models.json"
    merged_providers = providers

    if mode == "merge" and target_path.exists():
        try:
            with open(target_path, encoding="utf-8") as fh:
                existing = json.load(fh)
            if (
                isinstance(existing, dict)
                and isinstance(existing.get("providers"), dict)
            ):
                existing_providers: dict[str, Any] = existing["providers"]
                merged_providers = {**existing_providers, **providers}
        except Exception:
            pass

    normalized = _normalize_providers(merged_providers, agent_dir)
    next_content = json.dumps({"providers": normalized}, indent=2) + "\n"

    try:
        existing_raw = target_path.read_text(encoding="utf-8")
    except Exception:
        existing_raw = ""

    if existing_raw == next_content:
        return {"agent_dir": agent_dir, "wrote": False}

    target_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    target_path.write_text(next_content, encoding="utf-8")
    # Restrict file permissions (best-effort on non-POSIX)
    try:
        os.chmod(target_path, 0o600)
    except Exception:
        pass

    return {"agent_dir": agent_dir, "wrote": True}


__all__ = [
    "merge_provider_models",
    "merge_providers",
    "ensure_openclaw_models_json",
]
