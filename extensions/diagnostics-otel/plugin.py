"""OpenTelemetry diagnostics extension.

Mirrors TypeScript: openclaw/extensions/diagnostics-otel/index.ts + service.ts

Subscribes to ``on_diagnostic_event`` and dispatches to
:class:`~openclaw.monitoring.otel.OpenTelemetryService` for tracing and metrics.
Events dispatched:
  - ``model.usage``  → ``record_tokens``, ``record_cost``, span ``openclaw.model.usage``
  - ``webhook.*``    → ``record_webhook``
  - ``message.*``    → ``record_message``
  - ``session.state_change``, ``session.stuck`` → ``record_session_state``, ``record_stuck_session``
  - ``run.attempt``  → ``record_run_duration``
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_unsubscribe_fn = None
_otel_service = None


def _handle_event(event_type: str, data: dict[str, Any]) -> None:
    """Dispatch a diagnostic event to the OpenTelemetry service."""
    global _otel_service
    if _otel_service is None:
        return

    try:
        if event_type == "model.usage":
            _handle_model_usage(data)
        elif event_type in ("webhook.received", "webhook.processed", "webhook.error"):
            _handle_webhook(event_type, data)
        elif event_type in ("message.queued", "message.processed"):
            _handle_message(event_type, data)
        elif event_type == "session.state_change":
            _handle_session_state(data)
        elif event_type == "session.stuck":
            _handle_session_stuck(data)
        elif event_type == "run.attempt":
            _handle_run_attempt(data)
    except Exception as exc:
        logger.debug(f"diagnostics-otel: handler error for {event_type}: {exc}")


def _handle_model_usage(data: dict[str, Any]) -> None:
    """Handle model.usage event — create span + metrics."""
    global _otel_service
    svc = _otel_service

    usage = data.get("usage") or {}
    provider = data.get("provider", "unknown")
    model = data.get("model", "unknown")
    session_key = data.get("session_key", "")
    duration_ms = data.get("duration_ms")
    cost_usd = data.get("cost_usd")

    # Span: openclaw.model.usage
    span_attrs = {
        "provider": provider,
        "model": model,
        "session_key": session_key,
    }
    if duration_ms is not None:
        span_attrs["duration_ms"] = duration_ms

    ctx_mgr = svc.start_span("openclaw.model.usage", attributes=span_attrs)
    if ctx_mgr is not None:
        try:
            span = ctx_mgr.__enter__()
            if span and hasattr(span, "set_attribute"):
                for k, v in span_attrs.items():
                    span.set_attribute(k, str(v))
        except Exception:
            pass
        finally:
            try:
                ctx_mgr.__exit__(None, None, None)
            except Exception:
                pass

    # Metrics
    input_tokens = usage.get("input", 0) or usage.get("promptTokens", 0) or 0
    output_tokens = usage.get("output", 0) or 0
    cache_read = usage.get("cacheRead", 0) or 0
    cache_write = usage.get("cacheWrite", 0) or 0
    total = usage.get("total", 0) or (input_tokens + output_tokens)

    attrs = {"provider": provider, "model": model}
    svc.record_tokens(input_tokens, "input", attrs)
    svc.record_tokens(output_tokens, "output", attrs)
    if cache_read:
        svc.record_tokens(cache_read, "cache_read", attrs)
    if cache_write:
        svc.record_tokens(cache_write, "cache_write", attrs)
    if total:
        svc.record_tokens(total, "total", attrs)

    if cost_usd is not None:
        svc.record_cost(cost_usd, attrs)

    if duration_ms is not None:
        svc.record_run_duration(duration_ms, attrs)

    context = data.get("context") or {}
    if context.get("used"):
        try:
            # context_tokens histogram
            counter = svc._histograms.get("context.tokens")
            if counter is not None:
                counter.record(int(context["used"]), attrs)
        except Exception:
            pass


def _handle_webhook(event_type: str, data: dict[str, Any]) -> None:
    global _otel_service
    svc = _otel_service
    channel = data.get("channel", "")
    if event_type == "webhook.received":
        svc.record_webhook(channel, "received")
    elif event_type == "webhook.processed":
        svc.record_webhook(channel, "processed")
    elif event_type == "webhook.error":
        svc.record_webhook(channel, "error")


def _handle_message(event_type: str, data: dict[str, Any]) -> None:
    global _otel_service
    svc = _otel_service
    session_key = data.get("session_key", "")
    if event_type == "message.queued":
        svc.record_message(session_key, "queued")
    elif event_type == "message.processed":
        svc.record_message(session_key, "processed")


def _handle_session_state(data: dict[str, Any]) -> None:
    global _otel_service
    session_key = data.get("session_key", "")
    new_state = data.get("new_state", "")
    _otel_service.record_session_state(session_key, new_state)


def _handle_session_stuck(data: dict[str, Any]) -> None:
    global _otel_service
    session_key = data.get("session_key", "")
    duration_sec = data.get("duration_sec", 0.0)
    _otel_service.record_stuck_session(session_key, duration_sec)


def _handle_run_attempt(data: dict[str, Any]) -> None:
    # run.attempt doesn't directly map to a specific metric; we use a counter
    global _otel_service
    svc = _otel_service
    try:
        counter = svc._counters.get("run.attempt")
        if counter is not None:
            attrs = {
                "model": data.get("model", ""),
                "session_key": data.get("session_key", ""),
            }
            counter.add(1, attrs)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Plugin API
# ---------------------------------------------------------------------------


def register(api: Any) -> None:
    """Register this plugin with the OpenClaw extension API."""
    global _otel_service, _unsubscribe_fn

    config = getattr(api, "config", None) or {}
    diagnostics_cfg = (config.get("diagnostics") or {}) if isinstance(config, dict) else {}
    otel_cfg = diagnostics_cfg.get("otel") or {}

    if not diagnostics_cfg.get("enabled", True):
        logger.debug("diagnostics-otel: diagnostics disabled, skipping")
        return
    if not otel_cfg.get("enabled", False):
        logger.debug("diagnostics-otel: otel not enabled in config")
        return

    try:
        from openclaw.monitoring.otel import OpenTelemetryService, initialize_otel

        endpoint = otel_cfg.get("endpoint")
        service_name = otel_cfg.get("serviceName", "openclaw")
        flush_interval_ms = otel_cfg.get("flushIntervalMs", 60000)

        _otel_service = initialize_otel(
            endpoint=endpoint,
            service_name=service_name,
            flush_interval_ms=flush_interval_ms,
        )

        from openclaw.infra.diagnostic_events import on_diagnostic_event

        _unsubscribe_fn = on_diagnostic_event(_handle_event)

        logger.info(
            f"diagnostics-otel: initialized (endpoint={endpoint or 'default'}, "
            f"service={service_name})"
        )

    except Exception as exc:
        logger.warning(f"diagnostics-otel: initialization failed: {exc}")


def unregister() -> None:
    """Unregister and clean up."""
    global _unsubscribe_fn, _otel_service

    if _unsubscribe_fn is not None:
        try:
            _unsubscribe_fn()
        except Exception:
            pass
        _unsubscribe_fn = None

    if _otel_service is not None:
        try:
            _otel_service.shutdown()
        except Exception:
            pass
        _otel_service = None


plugin = {
    "id": "diagnostics-otel",
    "name": "Diagnostics (OpenTelemetry)",
    "description": (
        "Exports OpenClaw agent/model usage metrics, traces, and logs to any "
        "OpenTelemetry-compatible backend (Jaeger, Prometheus, Datadog, OTLP, …)."
    ),
    "register": register,
    "unregister": unregister,
}
