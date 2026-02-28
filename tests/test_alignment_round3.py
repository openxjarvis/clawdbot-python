"""
Round-3 alignment tests: TranscriptPolicy, fence protection, queue drop policy,
and new model providers.

Mirrors the test strategy from the Round 3 plan:
- TestTranscriptPolicy      — resolve_transcript_policy() for Google/Mistral/Anthropic/OpenRouter-Gemini
- TestFenceProtection       — parse_fence_spans(), is_safe_fence_break(), streaming split safety
- TestQueueDropPolicy       — drop 'old'/'new', reset_all_lanes()
- TestNewProviders          — builder functions return correct api_key_env, base_url, model list
"""
from __future__ import annotations

import asyncio
import pytest


# ---------------------------------------------------------------------------
# Phase 1.1 — TranscriptPolicy
# ---------------------------------------------------------------------------

class TestTranscriptPolicy:
    def _policy(self, model_api=None, provider=None, model_id=None):
        from openclaw.agents.history_utils import resolve_transcript_policy
        return resolve_transcript_policy(model_api=model_api, provider=provider, model_id=model_id)

    def test_google_gemini_full_sanitize(self):
        p = self._policy(model_api="google-ai-studio", provider="google", model_id="gemini-2.0-flash")
        assert p.sanitize_mode == "full"
        assert p.sanitize_tool_call_ids is True
        assert p.tool_call_id_mode == "strict"
        assert p.repair_tool_use_result_pairing is True
        assert p.apply_google_turn_ordering is True
        assert p.validate_gemini_turns is True
        assert p.validate_anthropic_turns is False
        assert p.allow_synthetic_tool_results is True

    def test_anthropic_policy(self):
        p = self._policy(model_api="anthropic-messages", provider="anthropic", model_id="claude-3-5-sonnet")
        assert p.sanitize_mode == "full"
        assert p.sanitize_tool_call_ids is True
        assert p.tool_call_id_mode == "strict"
        assert p.repair_tool_use_result_pairing is True
        assert p.validate_anthropic_turns is True
        assert p.apply_google_turn_ordering is False
        assert p.allow_synthetic_tool_results is True

    def test_mistral_strict9(self):
        p = self._policy(provider="mistral", model_id="mistral-large-latest")
        assert p.sanitize_tool_call_ids is True
        assert p.tool_call_id_mode == "strict9"
        assert p.sanitize_mode == "full"

    def test_mistral_from_model_id(self):
        p = self._policy(model_api="openai-completions", provider="openrouter", model_id="mistralai/Mistral-7B-Instruct-v0.1")
        assert p.tool_call_id_mode == "strict9"

    def test_openrouter_gemini_thought_signatures(self):
        p = self._policy(model_api="openai-completions", provider="openrouter", model_id="google/gemini-2.0-flash")
        assert p.sanitize_thought_signatures is not None
        assert p.sanitize_thought_signatures.allow_base64_only is True
        assert p.sanitize_thought_signatures.include_camel_case is True
        assert p.sanitize_mode == "full"

    def test_openai_images_only(self):
        p = self._policy(model_api="openai-completions", provider="openai", model_id="gpt-4o")
        assert p.sanitize_mode == "images-only"
        assert p.sanitize_tool_call_ids is False
        assert p.repair_tool_use_result_pairing is False
        assert p.apply_google_turn_ordering is False
        assert p.allow_synthetic_tool_results is False
        assert p.sanitize_thought_signatures is None

    def test_openai_codex_images_only(self):
        p = self._policy(model_api="openai-codex-responses", provider="openai-codex")
        assert p.sanitize_mode == "images-only"
        assert p.sanitize_tool_call_ids is False

    def test_unknown_provider_images_only(self):
        p = self._policy(model_api="some-unknown-api", provider="some-provider")
        assert p.sanitize_mode == "images-only"

    def test_antigravity_claude_preserve_signatures(self):
        p = self._policy(model_api="antigravity", provider="antigravity", model_id="claude-3-5-sonnet")
        assert p.preserve_signatures is True
        assert p.normalize_antigravity_thinking_blocks is True

    def test_google_vertex_claude_antigravity(self):
        p = self._policy(model_api="google-vertex", provider="google-vertex", model_id="claude-opus-4")
        assert p.preserve_signatures is True
        assert p.normalize_antigravity_thinking_blocks is True

    def test_no_args_returns_default(self):
        p = self._policy()
        assert p.sanitize_mode == "images-only"
        assert p.sanitize_tool_call_ids is False

    def test_transcript_policy_dataclass_fields(self):
        from openclaw.agents.history_utils import TranscriptPolicy
        p = TranscriptPolicy()
        assert hasattr(p, "sanitize_mode")
        assert hasattr(p, "sanitize_tool_call_ids")
        assert hasattr(p, "tool_call_id_mode")
        assert hasattr(p, "repair_tool_use_result_pairing")
        assert hasattr(p, "preserve_signatures")
        assert hasattr(p, "sanitize_thought_signatures")
        assert hasattr(p, "normalize_antigravity_thinking_blocks")
        assert hasattr(p, "apply_google_turn_ordering")
        assert hasattr(p, "validate_gemini_turns")
        assert hasattr(p, "validate_anthropic_turns")
        assert hasattr(p, "allow_synthetic_tool_results")


# ---------------------------------------------------------------------------
# Phase 1.2 — Fence Protection
# ---------------------------------------------------------------------------

class TestFenceProtection:
    def _parse(self, text):
        from openclaw.markdown.fences import parse_fence_spans
        return parse_fence_spans(text)

    def _safe(self, text, idx):
        from openclaw.markdown.fences import parse_fence_spans, is_safe_fence_break
        spans = parse_fence_spans(text)
        return is_safe_fence_break(spans, idx)

    def test_no_fences_all_safe(self):
        text = "Hello world\nNo code here\n"
        assert self._safe(text, 5) is True
        assert self._safe(text, 11) is True

    def test_closed_fence_outside_safe(self):
        text = "Before\n```python\ncode\n```\nAfter\n"
        # Before the fence
        assert self._safe(text, 3) is True
        # After the fence
        after_idx = text.index("After") + 2
        assert self._safe(text, after_idx) is True

    def test_inside_closed_fence_unsafe(self):
        text = "Before\n```python\ncode here\n```\nAfter\n"
        # Index inside the code block
        code_idx = text.index("code here") + 3
        assert self._safe(text, code_idx) is False

    def test_unclosed_fence_unsafe(self):
        text = "Before\n```python\ncode without closing\n"
        code_idx = text.index("code without") + 3
        assert self._safe(text, code_idx) is False

    def test_tilde_fence(self):
        text = "Before\n~~~python\ncode\n~~~\nAfter\n"
        code_idx = text.index("code") + 1
        assert self._safe(text, code_idx) is False
        after_idx = text.index("After") + 2
        assert self._safe(text, after_idx) is True

    def test_nested_does_not_close_early(self):
        # Inner ``` does not close ~~~
        text = "~~~\nline1\n```\nline2\n~~~\n"
        spans = self._parse(text)
        assert len(spans) == 1

    def test_parse_fence_spans_closed(self):
        text = "```python\ncode\n```\n"
        spans = self._parse(text)
        assert len(spans) == 1
        assert spans[0].marker == "```"
        assert text[spans[0].start:spans[0].start + 3] == "```"

    def test_parse_fence_spans_unclosed(self):
        text = "```python\ncode\n"
        spans = self._parse(text)
        assert len(spans) == 1
        assert spans[0].end == len(text)

    def test_fence_span_open_line(self):
        text = "```python\ncode\n```\n"
        spans = self._parse(text)
        assert spans[0].open_line == "```python"

    def test_empty_buffer(self):
        spans = self._parse("")
        assert spans == []

    def test_find_fence_span_at(self):
        from openclaw.markdown.fences import parse_fence_spans, find_fence_span_at
        text = "Before\n```\ncode\n```\nAfter\n"
        spans = parse_fence_spans(text)
        code_idx = text.index("code") + 1
        span = find_fence_span_at(spans, code_idx)
        assert span is not None

    def test_block_streaming_import(self):
        # Ensure fences is importable from block_streaming context
        from openclaw.auto_reply.reply.block_streaming import BlockReplyCoalescer
        assert BlockReplyCoalescer is not None


# ---------------------------------------------------------------------------
# Phase 1.3 — Queue Drop Policy
# ---------------------------------------------------------------------------

class TestQueueDropPolicy:
    def _make_queue(self):
        from openclaw.agents.queuing.queue import QueueManager
        return QueueManager()

    def test_reset_all_lanes_method_exists(self):
        qm = self._make_queue()
        assert callable(qm.reset_all_lanes)

    def test_reset_all_lanes_clears_active(self):
        qm = self._make_queue()
        # Increment generation manually to simulate activity
        for lane_obj in qm._fixed_lanes.values():
            lane_obj.active = 3
            lane_obj.generation = 1
        qm.reset_all_lanes()
        for lane_obj in qm._fixed_lanes.values():
            assert lane_obj.active == 0
            assert lane_obj.generation >= 2

    def test_enqueue_session_signature(self):
        import inspect
        from openclaw.agents.queuing.queue import QueueManager
        sig = inspect.signature(QueueManager.enqueue_session)
        params = set(sig.parameters.keys())
        assert "warn_after_ms" in params
        assert "on_wait" in params
        assert "drop_policy" in params

    def test_enqueue_in_lane_signature(self):
        import inspect
        from openclaw.agents.queuing.queue import QueueManager
        sig = inspect.signature(QueueManager.enqueue_in_lane)
        params = set(sig.parameters.keys())
        assert "warn_after_ms" in params
        assert "on_wait" in params
        assert "drop_policy" in params

    def test_drop_policy_new_raises(self):
        """Test that drop_policy='new' raises when lane queue is non-empty."""
        from openclaw.agents.queuing.queue import QueueManager
        from openclaw.agents.queuing.lanes import CommandLane
        import asyncio as _asyncio

        async def _test():
            qm = QueueManager()
            lane_obj = qm.get_lane(CommandLane.CRON)

            async def fake_task():
                return "fake"

            dummy_future: _asyncio.Future = _asyncio.get_event_loop().create_future()

            # Put directly into the lane queue (bypassing enqueue wrapper)
            await lane_obj.queue.put((fake_task, dummy_future, 999, 0))

            # Now drop_policy='new' should see queue non-empty and raise
            async def noop():
                return "noop"
            with pytest.raises(RuntimeError, match="busy"):
                await qm.enqueue_in_lane(CommandLane.CRON, noop, drop_policy="new")

            # Drain the fake item
            try:
                lane_obj.queue.get_nowait()
            except Exception:
                pass

        _asyncio.run(_test())

    def test_default_warn_after_ms(self):
        from openclaw.agents.queuing.queue import DEFAULT_WARN_AFTER_MS
        assert DEFAULT_WARN_AFTER_MS == 2_000

    def test_drop_policy_type_exported(self):
        from openclaw.agents.queuing.queue import DropPolicy
        assert DropPolicy is not None


# ---------------------------------------------------------------------------
# Phase 3 — New Providers
# ---------------------------------------------------------------------------

class TestMiniMaxProvider:
    def test_base_url(self):
        from openclaw.agents.models_config import build_minimax_provider, MINIMAX_BASE_URL
        p = build_minimax_provider()
        assert p["baseUrl"] == MINIMAX_BASE_URL
        assert MINIMAX_BASE_URL == "https://api.minimax.io/anthropic"

    def test_api_type(self):
        from openclaw.agents.models_config import build_minimax_provider
        p = build_minimax_provider()
        assert p["api"] == "anthropic-messages"

    def test_api_key_env(self):
        from openclaw.agents.models_config import build_minimax_provider
        p = build_minimax_provider()
        assert p["apiKeyEnv"] == "MINIMAX_API_KEY"

    def test_has_models(self):
        from openclaw.agents.models_config import build_minimax_provider
        p = build_minimax_provider()
        assert len(p["models"]) >= 2

    def test_m21_model_present(self):
        from openclaw.agents.models_config import build_minimax_provider
        p = build_minimax_provider()
        ids = [m["id"] for m in p["models"]]
        assert "MiniMax-M2.1" in ids

    def test_m21_lightning_present(self):
        from openclaw.agents.models_config import build_minimax_provider
        p = build_minimax_provider()
        ids = [m["id"] for m in p["models"]]
        assert "MiniMax-M2.1-lightning" in ids


class TestQianfanProvider:
    def test_base_url(self):
        from openclaw.agents.models_config import build_qianfan_provider, QIANFAN_BASE_URL
        p = build_qianfan_provider()
        assert p["baseUrl"] == QIANFAN_BASE_URL
        assert QIANFAN_BASE_URL == "https://qianfan.baidubce.com/v2"

    def test_api_type(self):
        from openclaw.agents.models_config import build_qianfan_provider
        p = build_qianfan_provider()
        assert p["api"] == "openai-completions"

    def test_api_key_env(self):
        from openclaw.agents.models_config import build_qianfan_provider
        p = build_qianfan_provider()
        assert p["apiKeyEnv"] == "QIANFAN_API_KEY"

    def test_has_deepseek_model(self):
        from openclaw.agents.models_config import build_qianfan_provider
        p = build_qianfan_provider()
        ids = [m["id"] for m in p["models"]]
        assert "deepseek-v3.2" in ids

    def test_reasoning_models(self):
        from openclaw.agents.models_config import build_qianfan_provider
        p = build_qianfan_provider()
        for m in p["models"]:
            assert m.get("reasoning") is True


class TestSyntheticProvider:
    def test_base_url(self):
        from openclaw.agents.models_config import build_synthetic_provider, SYNTHETIC_BASE_URL
        p = build_synthetic_provider()
        assert p["baseUrl"] == SYNTHETIC_BASE_URL
        assert SYNTHETIC_BASE_URL == "https://api.synthetic.new/anthropic"

    def test_api_type(self):
        from openclaw.agents.models_config import build_synthetic_provider
        p = build_synthetic_provider()
        assert p["api"] == "anthropic-messages"

    def test_api_key_env(self):
        from openclaw.agents.models_config import build_synthetic_provider
        p = build_synthetic_provider()
        assert p["apiKeyEnv"] == "SYNTHETIC_API_KEY"

    def test_has_models(self):
        from openclaw.agents.models_config import build_synthetic_provider
        p = build_synthetic_provider()
        assert len(p["models"]) >= 1

    def test_model_has_required_fields(self):
        from openclaw.agents.models_config import build_synthetic_provider
        p = build_synthetic_provider()
        for m in p["models"]:
            assert "id" in m
            assert "contextWindow" in m
            assert "maxTokens" in m


class TestHuggingFaceProvider:
    def test_base_url(self):
        from openclaw.agents.models_config import HUGGINGFACE_BASE_URL
        assert HUGGINGFACE_BASE_URL == "https://router.huggingface.co/v1"

    def test_sync_fallback_catalog(self):
        async def _run():
            from openclaw.agents.models_config import build_huggingface_provider
            p = await build_huggingface_provider(api_key=None)
            assert p["baseUrl"].startswith("https://")
            assert p["api"] == "openai-completions"
            assert len(p["models"]) >= 1
        asyncio.run(_run())

    def test_api_key_env(self):
        async def _run():
            from openclaw.agents.models_config import build_huggingface_provider
            p = await build_huggingface_provider()
            assert p["apiKeyEnv"] == "HUGGINGFACE_HUB_TOKEN"
        asyncio.run(_run())

    def test_model_ids_non_empty(self):
        async def _run():
            from openclaw.agents.models_config import build_huggingface_provider
            p = await build_huggingface_provider()
            for m in p["models"]:
                assert m["id"].strip() != ""
        asyncio.run(_run())
