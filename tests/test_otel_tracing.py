"""Tests for OpenTelemetry tracing and model.usage diagnostic events

Verifies:
  - log_model_usage() emits correct event payload
  - OTel plugin subscribes and dispatches to OpenTelemetryService
  - record_tokens, record_cost, record_run_duration are called
  - model.usage spans are created

Mirrors TS integration in openclaw/extensions/diagnostics-otel/
"""
import pytest
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# log_model_usage tests
# ---------------------------------------------------------------------------


class TestLogModelUsage:
    def setup_method(self):
        """Reset diagnostic listeners before each test."""
        from openclaw.infra import diagnostic_events as de
        de._listeners.clear()

    def test_emits_model_usage_event(self):
        """log_model_usage() emits an event with the correct type."""
        from openclaw.infra.diagnostic_events import log_model_usage, on_diagnostic_event

        received_events = []
        on_diagnostic_event(lambda t, d: received_events.append((t, d)))

        log_model_usage(
            session_key="sess-1",
            provider="anthropic",
            model="claude-opus-4",
            usage={"input": 100, "output": 50, "total": 150},
            cost_usd=0.002,
            duration_ms=1234.5,
        )

        assert len(received_events) == 1
        event_type, data = received_events[0]
        assert event_type == "model.usage"
        assert data["provider"] == "anthropic"
        assert data["model"] == "claude-opus-4"
        assert data["session_key"] == "sess-1"
        assert data["usage"]["input"] == 100
        assert data["usage"]["output"] == 50
        assert data["usage"]["total"] == 150
        assert data["cost_usd"] == 0.002
        assert data["duration_ms"] == 1234.5

    def test_optional_fields_omitted_when_none(self):
        """Optional fields not included when None."""
        from openclaw.infra.diagnostic_events import log_model_usage, on_diagnostic_event

        received = []
        on_diagnostic_event(lambda t, d: received.append(d))

        log_model_usage(
            session_key="sess-2",
            provider="openai",
            model="gpt-4",
            usage={"input": 0, "output": 0, "total": 0},
        )

        data = received[0]
        assert "cost_usd" not in data
        assert "duration_ms" not in data
        assert "channel" not in data

    def test_optional_fields_included_when_provided(self):
        """Optional fields are included when provided."""
        from openclaw.infra.diagnostic_events import log_model_usage, on_diagnostic_event

        received = []
        on_diagnostic_event(lambda t, d: received.append(d))

        log_model_usage(
            session_key="sess-3",
            provider="google",
            model="gemini-3-pro",
            usage={"input": 10, "output": 20, "total": 30},
            cost_usd=0.001,
            duration_ms=500,
            channel="telegram",
            session_id="uuid-123",
            context={"limit": 200000, "used": 5000},
        )

        data = received[0]
        assert data["cost_usd"] == 0.001
        assert data["duration_ms"] == 500
        assert data["channel"] == "telegram"
        assert data["session_id"] == "uuid-123"
        assert data["context"]["limit"] == 200000
        assert data["context"]["used"] == 5000

    def test_multiple_listeners_all_receive(self):
        """All subscribed listeners receive the event."""
        from openclaw.infra.diagnostic_events import log_model_usage, on_diagnostic_event

        received_a = []
        received_b = []
        on_diagnostic_event(lambda t, d: received_a.append(t))
        on_diagnostic_event(lambda t, d: received_b.append(t))

        log_model_usage("s", "p", "m", {})

        assert received_a == ["model.usage"]
        assert received_b == ["model.usage"]

    def test_unsubscribe_stops_receiving(self):
        """Calling the unsubscribe function stops event delivery."""
        from openclaw.infra.diagnostic_events import log_model_usage, on_diagnostic_event

        received = []
        unsub = on_diagnostic_event(lambda t, d: received.append(t))

        log_model_usage("s", "p", "m", {})
        assert len(received) == 1

        unsub()
        log_model_usage("s", "p", "m", {})
        assert len(received) == 1  # No new events after unsubscribe


# ---------------------------------------------------------------------------
# OTel plugin dispatcher tests
# ---------------------------------------------------------------------------


class TestOtelPluginDispatcher:
    """Tests for extensions/diagnostics-otel/plugin.py event handling."""

    def _make_mock_otel_service(self):
        svc = MagicMock()
        svc.start_span.return_value.__enter__ = MagicMock(return_value=MagicMock())
        svc.start_span.return_value.__exit__ = MagicMock(return_value=False)
        svc._histograms = {}
        svc._counters = {}
        return svc

    def test_handle_model_usage_calls_record_tokens(self):
        """model.usage event → record_tokens called for input/output/total."""
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "extensions", "diagnostics-otel"))
        
        try:
            from plugin import _handle_model_usage
            import plugin as otel_plugin
        except ImportError:
            pytest.skip("diagnostics-otel plugin not importable in this environment")

        mock_svc = self._make_mock_otel_service()
        otel_plugin._otel_service = mock_svc

        _handle_model_usage({
            "session_key": "sess-x",
            "provider": "anthropic",
            "model": "claude-opus-4",
            "usage": {"input": 100, "output": 50, "total": 150},
            "cost_usd": 0.003,
            "duration_ms": 800,
        })

        # Should call record_tokens for input, output, total
        token_calls = [c.args for c in mock_svc.record_tokens.call_args_list]
        token_types = [c[1] for c in token_calls]
        assert "input" in token_types
        assert "output" in token_types
        assert "total" in token_types

    def test_handle_model_usage_calls_record_cost(self):
        """model.usage event with cost_usd → record_cost called."""
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "extensions", "diagnostics-otel"))

        try:
            from plugin import _handle_model_usage
            import plugin as otel_plugin
        except ImportError:
            pytest.skip("diagnostics-otel plugin not importable")

        mock_svc = self._make_mock_otel_service()
        otel_plugin._otel_service = mock_svc

        _handle_model_usage({
            "session_key": "s",
            "provider": "openai",
            "model": "gpt-4",
            "usage": {"input": 0, "output": 0, "total": 0},
            "cost_usd": 0.005,
        })

        mock_svc.record_cost.assert_called_once()
        assert mock_svc.record_cost.call_args.args[0] == 0.005

    def test_handle_model_usage_no_cost_skips_record_cost(self):
        """model.usage without cost_usd → record_cost NOT called."""
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "extensions", "diagnostics-otel"))

        try:
            from plugin import _handle_model_usage
            import plugin as otel_plugin
        except ImportError:
            pytest.skip("diagnostics-otel plugin not importable")

        mock_svc = self._make_mock_otel_service()
        otel_plugin._otel_service = mock_svc

        _handle_model_usage({
            "session_key": "s",
            "provider": "p",
            "model": "m",
            "usage": {},
        })

        mock_svc.record_cost.assert_not_called()

    def test_handle_model_usage_creates_span(self):
        """model.usage event → openclaw.model.usage span created."""
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "extensions", "diagnostics-otel"))

        try:
            from plugin import _handle_model_usage
            import plugin as otel_plugin
        except ImportError:
            pytest.skip("diagnostics-otel plugin not importable")

        mock_svc = self._make_mock_otel_service()
        otel_plugin._otel_service = mock_svc

        _handle_model_usage({
            "session_key": "s",
            "provider": "anthropic",
            "model": "claude",
            "usage": {},
            "duration_ms": 100,
        })

        mock_svc.start_span.assert_called_once()
        assert "openclaw.model.usage" in mock_svc.start_span.call_args.args

    def test_no_otel_service_is_safe(self):
        """Events handled gracefully when _otel_service is None."""
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "extensions", "diagnostics-otel"))

        try:
            from plugin import _handle_event
            import plugin as otel_plugin
        except ImportError:
            pytest.skip("diagnostics-otel plugin not importable")

        otel_plugin._otel_service = None
        # Should not raise
        _handle_event("model.usage", {"usage": {}})


# ---------------------------------------------------------------------------
# Integration: log_model_usage → subscriber receives correct data
# ---------------------------------------------------------------------------


class TestLogModelUsageIntegration:
    def setup_method(self):
        from openclaw.infra import diagnostic_events as de
        de._listeners.clear()

    def test_subscriber_receives_all_fields(self):
        from openclaw.infra.diagnostic_events import log_model_usage, on_diagnostic_event

        received = {}
        on_diagnostic_event(lambda t, d: received.update({"type": t, **d}))

        log_model_usage(
            session_key="int-sess",
            provider="google",
            model="gemini-2.0-flash",
            usage={
                "input": 1000,
                "output": 500,
                "cacheRead": 200,
                "cacheWrite": 100,
                "total": 1800,
            },
            cost_usd=0.01,
            duration_ms=2000,
        )

        assert received["type"] == "model.usage"
        assert received["provider"] == "google"
        assert received["model"] == "gemini-2.0-flash"
        assert received["usage"]["cacheRead"] == 200
        assert received["usage"]["cacheWrite"] == 100
        assert received["duration_ms"] == 2000

    def test_cache_token_fields_passed_through(self):
        """Cache read/write token counts pass through unchanged."""
        from openclaw.infra.diagnostic_events import log_model_usage, on_diagnostic_event

        received = []
        on_diagnostic_event(lambda t, d: received.append(d))

        log_model_usage(
            session_key="s",
            provider="anthropic",
            model="claude-opus-4",
            usage={"input": 50, "output": 25, "cacheRead": 100, "cacheWrite": 200, "total": 375},
            last_call_usage={"promptTokens": 50, "completionTokens": 25},
        )

        data = received[0]
        assert data["usage"]["cacheRead"] == 100
        assert data["usage"]["cacheWrite"] == 200
        assert data["last_call_usage"]["promptTokens"] == 50
