"""Tests for provider routing and _detect_compat() — no real tokens required"""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from openclaw.agents.providers.openai_provider import OpenAIProvider


class TestDetectCompat:
    """Verify _detect_compat() mirrors TS detectCompat() / getCompat() logic"""

    def test_native_openai_defaults(self):
        p = OpenAIProvider("gpt-4o", api_key="sk-test")
        compat = p._detect_compat()
        assert compat["supports_store"] is True
        assert compat["supports_developer_role"] is True
        assert compat["supports_reasoning_effort"] is True
        assert compat["max_tokens_field"] == "max_completion_tokens"
        assert compat["requires_tool_result_name"] is False
        assert compat["requires_thinking_as_text"] is False

    def test_xai_compat(self):
        p = OpenAIProvider(
            "grok-3",
            api_key="xai-test",
            base_url="https://api.x.ai/v1",
            provider_name_override="xai",
        )
        compat = p._detect_compat()
        assert compat["supports_store"] is False
        assert compat["supports_developer_role"] is False
        assert compat["supports_reasoning_effort"] is False
        assert compat["max_tokens_field"] == "max_completion_tokens"

    def test_deepseek_compat(self):
        p = OpenAIProvider(
            "deepseek-chat",
            api_key="ds-test",
            base_url="https://api.deepseek.com",
            provider_name_override="deepseek",
        )
        compat = p._detect_compat()
        assert compat["supports_store"] is False
        assert compat["supports_developer_role"] is False

    def test_mistral_compat(self):
        p = OpenAIProvider(
            "mistral-large-latest",
            api_key="ms-test",
            base_url="https://api.mistral.ai/v1",
            provider_name_override="mistral",
        )
        compat = p._detect_compat()
        assert compat["supports_store"] is False
        assert compat["max_tokens_field"] == "max_tokens"    # Mistral uses max_tokens
        assert compat["requires_tool_result_name"] is True
        assert compat["requires_thinking_as_text"] is True

    def test_zai_compat_by_url(self):
        p = OpenAIProvider(
            "glm-4-plus",
            api_key="zai-test",
            base_url="https://open.bigmodel.cn/api/paas/v4",
            provider_name_override="zai",
        )
        compat = p._detect_compat()
        assert compat["supports_store"] is False
        assert compat["supports_reasoning_effort"] is False

    def test_groq_compat(self):
        p = OpenAIProvider(
            "llama-3.3-70b-versatile",
            api_key="groq-test",
            base_url="https://api.groq.com/openai/v1",
            provider_name_override="groq",
        )
        compat = p._detect_compat()
        assert compat["supports_store"] is False

    def test_compat_cached(self):
        """_detect_compat() result is cached after first call"""
        p = OpenAIProvider("gpt-4o", api_key="sk-test")
        c1 = p._detect_compat()
        c2 = p._detect_compat()
        assert c1 is c2  # same dict object (cached)

    def test_xai_detected_by_url_only(self):
        """xAI should be detected even without provider_name_override"""
        p = OpenAIProvider("grok-3", base_url="https://api.x.ai/v1")
        compat = p._detect_compat()
        assert compat["supports_store"] is False
        assert compat["supports_reasoning_effort"] is False


class TestProviderRouting:
    """Verify _create_provider() in MultiProviderRuntime routes correctly"""

    def _make_runtime(self, provider_name: str, model: str, **kwargs):
        """Helper to create a MultiProviderRuntime with minimal config"""
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from openclaw.agents.runtime import MultiProviderRuntime
        rt = MultiProviderRuntime.__new__(MultiProviderRuntime)
        rt.provider_name = provider_name
        rt.model_name = model
        rt.api_key = kwargs.get("api_key")
        rt.base_url = kwargs.get("base_url")
        rt.extra_params = {}
        rt.event_listeners = []
        return rt

    def test_openai_route(self):
        rt = self._make_runtime("openai", "gpt-4o")
        provider = rt._create_provider()
        assert isinstance(provider, OpenAIProvider)
        assert provider.provider_name == "openai"

    def test_xai_route(self):
        with patch.dict(os.environ, {"XAI_API_KEY": "xai-test"}):
            rt = self._make_runtime("xai", "grok-3")
            provider = rt._create_provider()
        assert isinstance(provider, OpenAIProvider)
        assert provider.provider_name == "xai"
        assert "x.ai" in (provider.base_url or "")

    def test_deepseek_route(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "ds-test"}):
            rt = self._make_runtime("deepseek", "deepseek-chat")
            provider = rt._create_provider()
        assert isinstance(provider, OpenAIProvider)
        assert provider.provider_name == "deepseek"
        assert "deepseek.com" in (provider.base_url or "")

    def test_groq_route(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": "groq-test"}):
            rt = self._make_runtime("groq", "llama-3.3-70b-versatile")
            provider = rt._create_provider()
        assert isinstance(provider, OpenAIProvider)
        assert "groq" in (provider.base_url or "")

    def test_mistral_route(self):
        with patch.dict(os.environ, {"MISTRAL_API_KEY": "ms-test"}):
            rt = self._make_runtime("mistral", "mistral-large-latest")
            provider = rt._create_provider()
        assert isinstance(provider, OpenAIProvider)
        assert "mistral" in (provider.base_url or "")

    def test_zai_route(self):
        with patch.dict(os.environ, {"ZAI_API_KEY": "zai-test"}):
            rt = self._make_runtime("zai", "glm-4-plus")
            provider = rt._create_provider()
        assert isinstance(provider, OpenAIProvider)
        assert "bigmodel.cn" in (provider.base_url or "")

    def test_zhipu_normalizes_to_zai(self):
        """'zhipu' should be treated same as 'zai'"""
        with patch.dict(os.environ, {"ZAI_API_KEY": "zai-test"}):
            rt = self._make_runtime("zhipu", "glm-4-plus")
            provider = rt._create_provider()
        assert isinstance(provider, OpenAIProvider)
        assert "bigmodel.cn" in (provider.base_url or "")

    def test_kimi_coding_normalizes_to_moonshot(self):
        """'kimi-code' normalizes to 'kimi-coding' then routes to moonshot"""
        from openclaw.agents.model_selection import normalize_provider_id
        assert normalize_provider_id("kimi-code") == "kimi-coding"

    def test_z_ai_normalizes_to_zai(self):
        from openclaw.agents.model_selection import normalize_provider_id
        assert normalize_provider_id("z.ai") == "zai"
        assert normalize_provider_id("z-ai") == "zai"

    def test_opencode_zen_normalizes(self):
        from openclaw.agents.model_selection import normalize_provider_id
        assert normalize_provider_id("opencode-zen") == "opencode"

    def test_anthropic_route(self):
        from openclaw.agents.providers.anthropic_provider import AnthropicProvider
        rt = self._make_runtime("anthropic", "claude-sonnet-4-5")
        provider = rt._create_provider()
        assert isinstance(provider, AnthropicProvider)

    def test_gemini_route(self):
        from openclaw.agents.providers.gemini_provider import GeminiProvider
        rt = self._make_runtime("gemini", "gemini-2.0-flash")
        provider = rt._create_provider()
        assert isinstance(provider, GeminiProvider)


class TestModelsConfigEnvVarDiscovery:
    """Verify models_config.py discovers new providers from environment variables"""

    def test_xai_discovered(self):
        from openclaw.agents.models_config import _resolve_implicit_providers
        with patch.dict(os.environ, {"XAI_API_KEY": "xai-test-key"}, clear=False):
            implicit = _resolve_implicit_providers("/tmp/test", {})
        assert "xai" in implicit
        assert implicit["xai"]["apiKey"] == "xai-test-key"
        assert len(implicit["xai"]["models"]) > 0

    def test_deepseek_discovered(self):
        from openclaw.agents.models_config import _resolve_implicit_providers
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "ds-key"}, clear=False):
            implicit = _resolve_implicit_providers("/tmp/test", {})
        assert "deepseek" in implicit
        assert implicit["deepseek"]["apiKey"] == "ds-key"

    def test_zai_discovered_via_zhipu_key(self):
        from openclaw.agents.models_config import _resolve_implicit_providers
        with patch.dict(os.environ, {"ZHIPU_API_KEY": "zhipu-key"}, clear=False):
            implicit = _resolve_implicit_providers("/tmp/test", {})
        assert "zai" in implicit

    def test_groq_discovered(self):
        from openclaw.agents.models_config import _resolve_implicit_providers
        with patch.dict(os.environ, {"GROQ_API_KEY": "groq-key"}, clear=False):
            implicit = _resolve_implicit_providers("/tmp/test", {})
        assert "groq" in implicit

    def test_mistral_discovered(self):
        from openclaw.agents.models_config import _resolve_implicit_providers
        with patch.dict(os.environ, {"MISTRAL_API_KEY": "ms-key"}, clear=False):
            implicit = _resolve_implicit_providers("/tmp/test", {})
        assert "mistral" in implicit

    def test_explicit_provider_not_overridden(self):
        """Explicit provider config should not be overridden by implicit discovery"""
        from openclaw.agents.models_config import _resolve_implicit_providers
        explicit = {"xai": {"apiKey": "explicit-key", "models": []}}
        with patch.dict(os.environ, {"XAI_API_KEY": "env-key"}, clear=False):
            implicit = _resolve_implicit_providers("/tmp/test", explicit)
        assert "xai" not in implicit

    def test_no_env_vars_no_new_providers(self):
        from openclaw.agents.models_config import _resolve_implicit_providers
        clean_env = {k: v for k, v in os.environ.items()
                     if k not in ("XAI_API_KEY", "DEEPSEEK_API_KEY", "ZAI_API_KEY",
                                  "ZHIPU_API_KEY", "GROQ_API_KEY", "MISTRAL_API_KEY",
                                  "MOONSHOT_API_KEY", "TOGETHER_API_KEY", "OPENROUTER_API_KEY",
                                  "HUGGINGFACE_API_KEY", "HF_API_KEY", "CEREBRAS_API_KEY",
                                  "DASHSCOPE_API_KEY", "QWEN_API_KEY",
                                  "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY")}
        with patch.dict(os.environ, clean_env, clear=True):
            implicit = _resolve_implicit_providers("/tmp/test", {})
        # Should still have ollama (no auth required)
        assert "ollama" in implicit
        # Should not have API-key-based providers
        for p in ("xai", "deepseek", "zai", "groq", "mistral"):
            assert p not in implicit
