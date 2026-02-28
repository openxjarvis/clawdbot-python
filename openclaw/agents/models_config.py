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
        implicit["ollama"] = {
            "baseUrl": ollama_base,
            "models": [],  # Populated at runtime by Ollama client
        }

    # ── OpenAI-compatible providers — mirrors TS register-builtins.ts ──

    # xAI Grok
    if not explicit_providers.get("xai"):
        xai_key = os.environ.get("XAI_API_KEY", "").strip()
        if xai_key:
            implicit["xai"] = {
                "apiKey": xai_key,
                "baseUrl": "https://api.x.ai/v1",
                "models": [
                    {"id": "grok-3", "name": "Grok 3", "input": ["text"]},
                    {"id": "grok-3-mini", "name": "Grok 3 Mini", "input": ["text"]},
                    {"id": "grok-2-vision-1212", "name": "Grok 2 Vision", "input": ["text", "image"]},
                ],
            }

    # DeepSeek
    if not explicit_providers.get("deepseek"):
        deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        if deepseek_key:
            implicit["deepseek"] = {
                "apiKey": deepseek_key,
                "baseUrl": "https://api.deepseek.com",
                "models": [
                    {"id": "deepseek-chat", "name": "DeepSeek Chat", "input": ["text"]},
                    {"id": "deepseek-reasoner", "name": "DeepSeek R1", "input": ["text"], "reasoning": True},
                ],
            }

    # Zhipu AI (ZAI / GLM)
    if not explicit_providers.get("zai"):
        zai_key = (
            os.environ.get("ZAI_API_KEY", "").strip()
            or os.environ.get("ZHIPU_API_KEY", "").strip()
        )
        if zai_key:
            implicit["zai"] = {
                "apiKey": zai_key,
                "baseUrl": "https://open.bigmodel.cn/api/paas/v4",
                "models": [
                    {"id": "glm-4-plus", "name": "GLM-4 Plus", "input": ["text", "image"]},
                    {"id": "glm-4-flash", "name": "GLM-4 Flash", "input": ["text"]},
                ],
            }

    # Groq
    if not explicit_providers.get("groq"):
        groq_key = os.environ.get("GROQ_API_KEY", "").strip()
        if groq_key:
            implicit["groq"] = {
                "apiKey": groq_key,
                "baseUrl": "https://api.groq.com/openai/v1",
                "models": [
                    {"id": "llama-3.3-70b-versatile", "name": "Llama 3.3 70B", "input": ["text"]},
                    {"id": "mixtral-8x7b-32768", "name": "Mixtral 8x7B", "input": ["text"]},
                ],
            }

    # Mistral
    if not explicit_providers.get("mistral"):
        mistral_key = os.environ.get("MISTRAL_API_KEY", "").strip()
        if mistral_key:
            implicit["mistral"] = {
                "apiKey": mistral_key,
                "baseUrl": "https://api.mistral.ai/v1",
                "models": [
                    {"id": "mistral-large-latest", "name": "Mistral Large", "input": ["text"]},
                    {"id": "mistral-small-latest", "name": "Mistral Small", "input": ["text"]},
                ],
            }

    # Moonshot (Kimi)
    if not explicit_providers.get("moonshot"):
        moonshot_key = os.environ.get("MOONSHOT_API_KEY", "").strip()
        if moonshot_key:
            implicit["moonshot"] = {
                "apiKey": moonshot_key,
                "baseUrl": "https://api.moonshot.cn/v1",
                "models": [
                    {"id": "moonshot-v1-8k", "name": "Moonshot 8K", "input": ["text"]},
                    {"id": "moonshot-v1-32k", "name": "Moonshot 32K", "input": ["text"]},
                    {"id": "kimi-latest", "name": "Kimi Latest", "input": ["text"]},
                ],
            }

    # Together AI
    if not explicit_providers.get("together"):
        together_key = os.environ.get("TOGETHER_API_KEY", "").strip()
        if together_key:
            implicit["together"] = {
                "apiKey": together_key,
                "baseUrl": "https://api.together.xyz/v1",
                "models": [],
            }

    # OpenRouter
    if not explicit_providers.get("openrouter"):
        openrouter_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if openrouter_key:
            implicit["openrouter"] = {
                "apiKey": openrouter_key,
                "baseUrl": "https://openrouter.ai/api/v1",
                "models": [],
            }

    # HuggingFace
    if not explicit_providers.get("huggingface"):
        hf_key = (
            os.environ.get("HUGGINGFACE_API_KEY", "").strip()
            or os.environ.get("HF_API_KEY", "").strip()
        )
        if hf_key:
            implicit["huggingface"] = {
                "apiKey": hf_key,
                "baseUrl": "https://api-inference.huggingface.co/v1",
                "models": [],
            }

    # Cerebras
    if not explicit_providers.get("cerebras"):
        cerebras_key = os.environ.get("CEREBRAS_API_KEY", "").strip()
        if cerebras_key:
            implicit["cerebras"] = {
                "apiKey": cerebras_key,
                "baseUrl": "https://api.cerebras.ai/v1",
                "models": [
                    {"id": "llama3.1-70b", "name": "Llama 3.1 70B (Cerebras)", "input": ["text"]},
                ],
            }

    # Alibaba Qwen via DashScope
    if not explicit_providers.get("qwen-portal"):
        qwen_key = (
            os.environ.get("DASHSCOPE_API_KEY", "").strip()
            or os.environ.get("QWEN_API_KEY", "").strip()
        )
        if qwen_key:
            implicit["qwen-portal"] = {
                "apiKey": qwen_key,
                "baseUrl": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "models": [
                    {"id": "qwen-max", "name": "Qwen Max", "input": ["text", "image"]},
                    {"id": "qwen-turbo", "name": "Qwen Turbo", "input": ["text"]},
                ],
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


# ---------------------------------------------------------------------------
# Additional provider builders — mirrors TS models-config.providers.ts
# ---------------------------------------------------------------------------

MINIMAX_BASE_URL = "https://api.minimax.io/anthropic"
QIANFAN_BASE_URL = "https://qianfan.baidubce.com/v2"
SYNTHETIC_BASE_URL = "https://api.synthetic.new/anthropic"
HUGGINGFACE_BASE_URL = "https://router.huggingface.co/v1"


def build_minimax_provider() -> dict:
    """Build MiniMax provider config.

    Mirrors TS buildMinimaxProvider() in models-config.providers.ts.
    Uses anthropic-messages API against the MiniMax Anthropic-compatible portal.
    Auto-detected via MINIMAX_API_KEY env var.
    """
    return {
        "baseUrl": MINIMAX_BASE_URL,
        "api": "anthropic-messages",
        "apiKeyEnv": "MINIMAX_API_KEY",
        "models": [
            {
                "id": "MiniMax-M2.1",
                "name": "MiniMax M2.1",
                "reasoning": False,
                "input": ["text"],
                "contextWindow": 200000,
                "maxTokens": 8192,
            },
            {
                "id": "MiniMax-M2.1-lightning",
                "name": "MiniMax M2.1 Lightning",
                "reasoning": False,
                "input": ["text"],
                "contextWindow": 200000,
                "maxTokens": 8192,
            },
            {
                "id": "MiniMax-VL-01",
                "name": "MiniMax VL 01",
                "reasoning": False,
                "input": ["text", "image"],
                "contextWindow": 200000,
                "maxTokens": 8192,
            },
            {
                "id": "MiniMax-M2.5",
                "name": "MiniMax M2.5",
                "reasoning": True,
                "input": ["text"],
                "contextWindow": 200000,
                "maxTokens": 8192,
            },
            {
                "id": "MiniMax-M2.5-Lightning",
                "name": "MiniMax M2.5 Lightning",
                "reasoning": True,
                "input": ["text"],
                "contextWindow": 200000,
                "maxTokens": 8192,
            },
        ],
    }


def build_qianfan_provider() -> dict:
    """Build Baidu Qianfan provider config.

    Mirrors TS buildQianfanProvider() in models-config.providers.ts.
    Uses openai-completions API.  Auto-detected via QIANFAN_API_KEY env var.
    """
    return {
        "baseUrl": QIANFAN_BASE_URL,
        "api": "openai-completions",
        "apiKeyEnv": "QIANFAN_API_KEY",
        "models": [
            {
                "id": "deepseek-v3.2",
                "name": "DEEPSEEK V3.2",
                "reasoning": True,
                "input": ["text"],
                "contextWindow": 98304,
                "maxTokens": 32768,
            },
            {
                "id": "ernie-5.0-thinking-preview",
                "name": "ERNIE-5.0-Thinking-Preview",
                "reasoning": True,
                "input": ["text", "image"],
                "contextWindow": 119000,
                "maxTokens": 64000,
            },
        ],
    }


def build_synthetic_provider() -> dict:
    """Build Synthetic provider config.

    Mirrors TS buildSyntheticProvider() in models-config.providers.ts.
    Uses anthropic-messages API at https://api.synthetic.new/anthropic.
    Auto-detected via SYNTHETIC_API_KEY env var.
    """
    return {
        "baseUrl": SYNTHETIC_BASE_URL,
        "api": "anthropic-messages",
        "apiKeyEnv": "SYNTHETIC_API_KEY",
        "models": [
            {
                "id": "claude-3-7-sonnet-20250219",
                "name": "Claude 3.7 Sonnet (Synthetic)",
                "reasoning": True,
                "input": ["text", "image"],
                "contextWindow": 200000,
                "maxTokens": 64000,
            },
            {
                "id": "claude-opus-4-5",
                "name": "Claude Opus 4.5 (Synthetic)",
                "reasoning": True,
                "input": ["text", "image"],
                "contextWindow": 200000,
                "maxTokens": 32000,
            },
        ],
    }


async def build_huggingface_provider(api_key: str | None = None) -> dict:
    """Build HuggingFace provider config, optionally discovering models from the API.

    Mirrors TS buildHuggingfaceProvider() in models-config.providers.ts.
    Uses openai-completions API at https://router.huggingface.co/v1.
    Auto-detected via HUGGINGFACE_HUB_TOKEN or HF_TOKEN env var.

    If api_key is provided and non-empty, attempts to discover models from
    GET https://router.huggingface.co/v1/models.  Falls back to a static catalog.
    """
    import os
    resolved_key = (api_key or "").strip()
    if not resolved_key:
        resolved_key = (
            os.environ.get("HUGGINGFACE_HUB_TOKEN", "")
            or os.environ.get("HF_TOKEN", "")
        ).strip()

    discovered: list[dict] = []
    if resolved_key:
        try:
            import urllib.request
            import json as _json
            req = urllib.request.Request(
                f"{HUGGINGFACE_BASE_URL}/models",
                headers={"Authorization": f"Bearer {resolved_key}"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = _json.loads(resp.read())
            raw_models = data.get("data", []) if isinstance(data, dict) else data
            for m in raw_models:
                if not isinstance(m, dict):
                    continue
                mid = m.get("id", "")
                if not mid:
                    continue
                inputs = ["text"]
                arch = m.get("architecture", {}) or {}
                modalities = arch.get("input_modalities") or arch.get("modalities", [])
                if "image" in modalities:
                    inputs.append("image")
                discovered.append({
                    "id": mid,
                    "name": mid.replace("/", " / "),
                    "reasoning": False,
                    "input": inputs,
                    "contextWindow": 32768,
                    "maxTokens": 4096,
                })
        except Exception:
            pass

    if not discovered:
        discovered = [
            {
                "id": "meta-llama/Llama-3.1-8B-Instruct",
                "name": "Meta Llama 3.1 8B Instruct",
                "reasoning": False,
                "input": ["text"],
                "contextWindow": 131072,
                "maxTokens": 4096,
            },
            {
                "id": "Qwen/Qwen2.5-72B-Instruct",
                "name": "Qwen 2.5 72B Instruct",
                "reasoning": False,
                "input": ["text"],
                "contextWindow": 32768,
                "maxTokens": 4096,
            },
        ]

    return {
        "baseUrl": HUGGINGFACE_BASE_URL,
        "api": "openai-completions",
        "apiKeyEnv": "HUGGINGFACE_HUB_TOKEN",
        "models": discovered,
    }


def _detect_implicit_new_providers(implicit: dict) -> None:
    """Detect MiniMax, Qianfan, Synthetic and HuggingFace from env vars.

    Called during provider resolution to add implicit provider configs when
    the corresponding API key env vars are set.
    """
    import os

    if os.environ.get("MINIMAX_API_KEY", "").strip() and "minimax" not in implicit:
        implicit["minimax"] = {**build_minimax_provider(), "apiKey": os.environ["MINIMAX_API_KEY"].strip()}

    if os.environ.get("QIANFAN_API_KEY", "").strip() and "qianfan" not in implicit:
        implicit["qianfan"] = {**build_qianfan_provider(), "apiKey": os.environ["QIANFAN_API_KEY"].strip()}

    if os.environ.get("SYNTHETIC_API_KEY", "").strip() and "synthetic" not in implicit:
        implicit["synthetic"] = {**build_synthetic_provider(), "apiKey": os.environ["SYNTHETIC_API_KEY"].strip()}


__all__ = [
    "merge_provider_models",
    "merge_providers",
    "ensure_openclaw_models_json",
    "build_minimax_provider",
    "build_qianfan_provider",
    "build_synthetic_provider",
    "build_huggingface_provider",
    "MINIMAX_BASE_URL",
    "QIANFAN_BASE_URL",
    "SYNTHETIC_BASE_URL",
    "HUGGINGFACE_BASE_URL",
]
