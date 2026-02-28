"""OpenTelemetry diagnostics extension.

Mirrors TypeScript: openclaw/extensions/diagnostics-otel/src/service.ts

Subscribes to diagnostic events and dispatches to OTEL exporters:
  - model.usage      → tokens counter, cost counter, run duration histogram, span
  - webhook.received → webhook_received counter
  - webhook.processed→ webhook_duration histogram, span
  - webhook.error    → webhook_error counter, error span
  - message.queued   → message_queued counter, queue_depth histogram
  - message.processed→ message_processed counter, message_duration histogram, span
  - queue.lane.enqueue → lane_enqueue counter, queue_depth histogram
  - queue.lane.dequeue → lane_dequeue counter, queue_depth histogram, queue_wait histogram
  - session.state    → session_state counter
  - session.stuck    → session_stuck counter, session_stuck_age histogram, error span
  - run.attempt      → run_attempt counter
  - diagnostic.heartbeat → queue_depth histogram
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_SERVICE_NAME = "openclaw"


# ---------------------------------------------------------------------------
# URL / config helpers (mirrors TS normalizeEndpoint / resolveOtelUrl)
# ---------------------------------------------------------------------------

def _normalize_endpoint(endpoint: str | None) -> str | None:
    if not endpoint:
        return None
    trimmed = endpoint.strip().rstrip("/")
    return trimmed or None


def _resolve_otel_url(endpoint: str | None, path: str) -> str | None:
    if not endpoint:
        return None
    if "/v1/" in endpoint:
        return endpoint
    return f"{endpoint}/{path}"


def _resolve_sample_rate(value: Any) -> float | None:
    if not isinstance(value, (int, float)):
        return None
    if not (0.0 <= float(value) <= 1.0):
        return None
    return float(value)


# ---------------------------------------------------------------------------
# Log handler — bridges Python logging to OTEL LoggerProvider
# ---------------------------------------------------------------------------

class _OtelLogHandler(logging.Handler):
    """Forwards Python log records to an OTEL LoggerProvider logger."""

    _SEVERITY_MAP: dict[int, int] = {
        logging.DEBUG: 5,
        logging.INFO: 9,
        logging.WARNING: 13,
        logging.ERROR: 17,
        logging.CRITICAL: 21,
    }

    def __init__(self, otel_logger: Any) -> None:
        super().__init__()
        self._otel_logger = otel_logger

    def emit(self, record: logging.LogRecord) -> None:
        try:
            import datetime
            severity = self._SEVERITY_MAP.get(record.levelno, 9)
            attributes: dict[str, Any] = {
                "openclaw.log.level": record.levelname,
                "openclaw.logger": record.name,
            }
            if record.pathname:
                attributes["code.filepath"] = record.pathname
            if record.lineno:
                attributes["code.lineno"] = record.lineno
            if record.funcName:
                attributes["code.function"] = record.funcName

            self._otel_logger.emit({
                "body": self.format(record),
                "severity_text": record.levelname,
                "severity_number": severity,
                "attributes": attributes,
                "timestamp": datetime.datetime.fromtimestamp(record.created),
            })
        except Exception:
            pass


# ---------------------------------------------------------------------------
# OtelMetrics — thin wrapper around OTEL API primitives
# ---------------------------------------------------------------------------

class _OtelState:
    """Holds OTEL SDK, provider, and all meter instruments."""

    def __init__(
        self,
        sdk: Any,
        tracer: Any,
        meter: Any,
        log_provider: Any,
        log_handler: Any,
        traces_enabled: bool,
        instruments: dict[str, Any],
    ) -> None:
        self.sdk = sdk
        self.tracer = tracer
        self.meter = meter
        self.log_provider = log_provider
        self.log_handler = log_handler
        self.traces_enabled = traces_enabled
        self.instruments = instruments

    def counter(self, name: str) -> Any:
        return self.instruments.get(name)

    def histogram(self, name: str) -> Any:
        return self.instruments.get(name)

    def span_with_duration(
        self, name: str, attributes: dict, duration_ms: float | int | None = None
    ) -> Any:
        if not self.tracer:
            return None
        import time
        start_time = (
            time.time_ns() - int(max(0, duration_ms) * 1_000_000)
            if duration_ms is not None
            else None
        )
        kwargs: dict[str, Any] = {"attributes": attributes}
        if start_time is not None:
            kwargs["start_time"] = start_time
        return self.tracer.start_span(name, **kwargs)


# ---------------------------------------------------------------------------
# Event handlers (mirror TS record* functions)
# ---------------------------------------------------------------------------

def _record_model_usage(state: _OtelState, evt: dict) -> None:
    usage = evt.get("usage") or {}
    attrs: dict[str, Any] = {
        "openclaw.channel": evt.get("channel") or "unknown",
        "openclaw.provider": evt.get("provider") or "unknown",
        "openclaw.model": evt.get("model") or "unknown",
    }
    tokens_counter = state.counter("openclaw.tokens")
    cost_counter = state.counter("openclaw.cost.usd")
    dur_histogram = state.histogram("openclaw.run.duration_ms")
    ctx_histogram = state.histogram("openclaw.context.tokens")

    if tokens_counter:
        def _add_token(value: Any, token_type: str) -> None:
            v = int(value or 0)
            if v:
                tokens_counter.add(v, {**attrs, "openclaw.token": token_type})

        _add_token(usage.get("input") or usage.get("promptTokens"), "input")
        _add_token(usage.get("output"), "output")
        _add_token(usage.get("cacheRead"), "cache_read")
        _add_token(usage.get("cacheWrite"), "cache_write")
        _add_token(usage.get("total"), "total")

    if cost_counter and evt.get("costUsd"):
        cost_counter.add(float(evt["costUsd"]), attrs)

    if dur_histogram and evt.get("durationMs") is not None:
        dur_histogram.record(float(evt["durationMs"]), attrs)

    if ctx_histogram:
        context = evt.get("context") or {}
        if context.get("limit"):
            ctx_histogram.record(int(context["limit"]), {**attrs, "openclaw.context": "limit"})
        if context.get("used"):
            ctx_histogram.record(int(context["used"]), {**attrs, "openclaw.context": "used"})

    if not state.traces_enabled:
        return
    span_attrs: dict[str, Any] = {
        **attrs,
        "openclaw.sessionKey": evt.get("sessionKey") or "",
        "openclaw.sessionId": evt.get("sessionId") or "",
        "openclaw.tokens.input": usage.get("input") or 0,
        "openclaw.tokens.output": usage.get("output") or 0,
        "openclaw.tokens.cache_read": usage.get("cacheRead") or 0,
        "openclaw.tokens.cache_write": usage.get("cacheWrite") or 0,
        "openclaw.tokens.total": usage.get("total") or 0,
    }
    span = state.span_with_duration("openclaw.model.usage", span_attrs, evt.get("durationMs"))
    if span:
        span.end()


def _record_webhook_received(state: _OtelState, evt: dict) -> None:
    attrs: dict[str, Any] = {
        "openclaw.channel": evt.get("channel") or "unknown",
        "openclaw.webhook": evt.get("updateType") or "unknown",
    }
    c = state.counter("openclaw.webhook.received")
    if c:
        c.add(1, attrs)


def _record_webhook_processed(state: _OtelState, evt: dict) -> None:
    attrs: dict[str, Any] = {
        "openclaw.channel": evt.get("channel") or "unknown",
        "openclaw.webhook": evt.get("updateType") or "unknown",
    }
    h = state.histogram("openclaw.webhook.duration_ms")
    if h and evt.get("durationMs") is not None:
        h.record(float(evt["durationMs"]), attrs)
    if not state.traces_enabled:
        return
    span_attrs: dict[str, Any] = {**attrs}
    if evt.get("chatId") is not None:
        span_attrs["openclaw.chatId"] = str(evt["chatId"])
    span = state.span_with_duration("openclaw.webhook.processed", span_attrs, evt.get("durationMs"))
    if span:
        span.end()


def _record_webhook_error(state: _OtelState, evt: dict) -> None:
    attrs: dict[str, Any] = {
        "openclaw.channel": evt.get("channel") or "unknown",
        "openclaw.webhook": evt.get("updateType") or "unknown",
    }
    c = state.counter("openclaw.webhook.error")
    if c:
        c.add(1, attrs)
    if not state.traces_enabled or not state.tracer:
        return
    span_attrs: dict[str, Any] = {**attrs, "openclaw.error": evt.get("error") or ""}
    if evt.get("chatId") is not None:
        span_attrs["openclaw.chatId"] = str(evt["chatId"])
    span = state.tracer.start_span("openclaw.webhook.error", attributes=span_attrs)
    if span:
        try:
            from opentelemetry.trace import StatusCode  # type: ignore[import]
            span.set_status(StatusCode.ERROR, evt.get("error") or "webhook error")
        except Exception:
            pass
        span.end()


def _record_message_queued(state: _OtelState, evt: dict) -> None:
    attrs: dict[str, Any] = {
        "openclaw.channel": evt.get("channel") or "unknown",
        "openclaw.source": evt.get("source") or "unknown",
    }
    c = state.counter("openclaw.message.queued")
    if c:
        c.add(1, attrs)
    h = state.histogram("openclaw.queue.depth")
    if h and evt.get("queueDepth") is not None:
        h.record(int(evt["queueDepth"]), attrs)


def _record_message_processed(state: _OtelState, evt: dict) -> None:
    attrs: dict[str, Any] = {
        "openclaw.channel": evt.get("channel") or "unknown",
        "openclaw.outcome": evt.get("outcome") or "unknown",
    }
    c = state.counter("openclaw.message.processed")
    if c:
        c.add(1, attrs)
    h = state.histogram("openclaw.message.duration_ms")
    if h and evt.get("durationMs") is not None:
        h.record(float(evt["durationMs"]), attrs)
    if not state.traces_enabled:
        return
    span_attrs: dict[str, Any] = {**attrs}
    for key, otel_key in [
        ("sessionKey", "openclaw.sessionKey"),
        ("sessionId", "openclaw.sessionId"),
        ("reason", "openclaw.reason"),
    ]:
        if evt.get(key):
            span_attrs[otel_key] = str(evt[key])
    if evt.get("chatId") is not None:
        span_attrs["openclaw.chatId"] = str(evt["chatId"])
    if evt.get("messageId") is not None:
        span_attrs["openclaw.messageId"] = str(evt["messageId"])
    span = state.span_with_duration("openclaw.message.processed", span_attrs, evt.get("durationMs"))
    if span:
        try:
            if evt.get("outcome") == "error":
                from opentelemetry.trace import StatusCode  # type: ignore[import]
                span.set_status(StatusCode.ERROR, evt.get("error") or "")
        except Exception:
            pass
        span.end()


def _record_lane_enqueue(state: _OtelState, evt: dict) -> None:
    attrs: dict[str, Any] = {"openclaw.lane": evt.get("lane") or ""}
    c = state.counter("openclaw.queue.lane.enqueue")
    if c:
        c.add(1, attrs)
    h = state.histogram("openclaw.queue.depth")
    if h and evt.get("queueSize") is not None:
        h.record(int(evt["queueSize"]), attrs)


def _record_lane_dequeue(state: _OtelState, evt: dict) -> None:
    attrs: dict[str, Any] = {"openclaw.lane": evt.get("lane") or ""}
    c = state.counter("openclaw.queue.lane.dequeue")
    if c:
        c.add(1, attrs)
    h = state.histogram("openclaw.queue.depth")
    if h and evt.get("queueSize") is not None:
        h.record(int(evt["queueSize"]), attrs)
    hw = state.histogram("openclaw.queue.wait_ms")
    if hw and evt.get("waitMs") is not None:
        hw.record(float(evt["waitMs"]), attrs)


def _record_session_state(state: _OtelState, evt: dict) -> None:
    attrs: dict[str, Any] = {"openclaw.state": evt.get("state") or ""}
    if evt.get("reason"):
        attrs["openclaw.reason"] = evt["reason"]
    c = state.counter("openclaw.session.state")
    if c:
        c.add(1, attrs)


def _record_session_stuck(state: _OtelState, evt: dict) -> None:
    attrs: dict[str, Any] = {"openclaw.state": evt.get("state") or ""}
    c = state.counter("openclaw.session.stuck")
    if c:
        c.add(1, attrs)
    h = state.histogram("openclaw.session.stuck_age_ms")
    if h and evt.get("ageMs") is not None:
        h.record(float(evt["ageMs"]), attrs)
    if not state.traces_enabled or not state.tracer:
        return
    span_attrs: dict[str, Any] = {**attrs}
    for key, otel_key in [
        ("sessionKey", "openclaw.sessionKey"),
        ("sessionId", "openclaw.sessionId"),
    ]:
        if evt.get(key):
            span_attrs[otel_key] = str(evt[key])
    span_attrs["openclaw.queueDepth"] = int(evt.get("queueDepth") or 0)
    span_attrs["openclaw.ageMs"] = float(evt.get("ageMs") or 0)
    span = state.tracer.start_span("openclaw.session.stuck", attributes=span_attrs)
    if span:
        try:
            from opentelemetry.trace import StatusCode  # type: ignore[import]
            span.set_status(StatusCode.ERROR, "session stuck")
        except Exception:
            pass
        span.end()


def _record_run_attempt(state: _OtelState, evt: dict) -> None:
    c = state.counter("openclaw.run.attempt")
    if c:
        c.add(1, {"openclaw.attempt": str(evt.get("attempt") or "1")})


def _record_heartbeat(state: _OtelState, evt: dict) -> None:
    h = state.histogram("openclaw.queue.depth")
    if h:
        h.record(int(evt.get("queued") or 0), {"openclaw.channel": "heartbeat"})


# ---------------------------------------------------------------------------
# Service start (builds OTEL SDK and wires event handler)
# ---------------------------------------------------------------------------

def _build_otel_state(cfg: dict, service_name: str) -> _OtelState | None:
    """Initialize OTEL SDK, instruments, and log provider. Returns None if disabled."""
    try:
        from opentelemetry import metrics as otel_metrics  # type: ignore[import]
        from opentelemetry import trace as otel_trace
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
            OTLPMetricExporter,  # type: ignore[import]
        )
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,  # type: ignore[import]
        )
        from opentelemetry.sdk.metrics import MeterProvider  # type: ignore[import]
        from opentelemetry.sdk.metrics.export import (
            PeriodicExportingMetricReader,  # type: ignore[import]
        )
        from opentelemetry.sdk.resources import Resource  # type: ignore[import]
        from opentelemetry.sdk.trace import TracerProvider  # type: ignore[import]
        from opentelemetry.sdk.trace.export import BatchSpanProcessor  # type: ignore[import]
    except ImportError as exc:
        logger.warning(f"diagnostics-otel: missing opentelemetry dependencies: {exc}")
        return None

    endpoint = _normalize_endpoint(cfg.get("endpoint") or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"))
    headers = cfg.get("headers") or {}
    flush_interval_ms = int(cfg.get("flushIntervalMs") or 60_000)
    flush_interval_ms = max(1000, flush_interval_ms)
    sample_rate = _resolve_sample_rate(cfg.get("sampleRate"))
    traces_enabled = cfg.get("traces", True) is not False
    metrics_enabled = cfg.get("metrics", True) is not False
    logs_enabled = cfg.get("logs") is True

    resource = Resource.create({"service.name": service_name})

    tracer_provider: Any = None
    if traces_enabled:
        trace_url = _resolve_otel_url(endpoint, "v1/traces")
        exporter_kwargs: dict[str, Any] = {}
        if trace_url:
            exporter_kwargs["endpoint"] = trace_url
        if headers:
            exporter_kwargs["headers"] = headers
        trace_exporter = OTLPSpanExporter(**exporter_kwargs)
        span_processor = BatchSpanProcessor(trace_exporter)
        tp_kwargs: dict[str, Any] = {"resource": resource}
        if sample_rate is not None:
            try:
                from opentelemetry.sdk.trace.sampling import (  # type: ignore[import]
                    ParentBased,
                    TraceIdRatioBased,
                )
                tp_kwargs["sampler"] = ParentBased(TraceIdRatioBased(sample_rate))
            except ImportError:
                pass
        tracer_provider = TracerProvider(**tp_kwargs)
        tracer_provider.add_span_processor(span_processor)
        otel_trace.set_tracer_provider(tracer_provider)

    tracer = otel_trace.get_tracer("openclaw") if traces_enabled else None

    meter_provider: Any = None
    if metrics_enabled:
        metric_url = _resolve_otel_url(endpoint, "v1/metrics")
        metric_kwargs: dict[str, Any] = {}
        if metric_url:
            metric_kwargs["endpoint"] = metric_url
        if headers:
            metric_kwargs["headers"] = headers
        metric_exporter = OTLPMetricExporter(**metric_kwargs)
        reader = PeriodicExportingMetricReader(
            metric_exporter,
            export_interval_millis=flush_interval_ms,
        )
        meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
        otel_metrics.set_meter_provider(meter_provider)

    meter = otel_metrics.get_meter("openclaw") if metrics_enabled else None

    # Build instruments
    instruments: dict[str, Any] = {}
    if meter:
        def _counter(name: str, unit: str, desc: str) -> Any:
            return meter.create_counter(name, unit=unit, description=desc)

        def _histogram(name: str, unit: str, desc: str) -> Any:
            return meter.create_histogram(name, unit=unit, description=desc)

        instruments["openclaw.tokens"] = _counter("openclaw.tokens", "1", "Token usage by type")
        instruments["openclaw.cost.usd"] = _counter("openclaw.cost.usd", "1", "Estimated model cost (USD)")
        instruments["openclaw.run.duration_ms"] = _histogram("openclaw.run.duration_ms", "ms", "Agent run duration")
        instruments["openclaw.context.tokens"] = _histogram("openclaw.context.tokens", "1", "Context window size and usage")
        instruments["openclaw.webhook.received"] = _counter("openclaw.webhook.received", "1", "Webhook requests received")
        instruments["openclaw.webhook.error"] = _counter("openclaw.webhook.error", "1", "Webhook processing errors")
        instruments["openclaw.webhook.duration_ms"] = _histogram("openclaw.webhook.duration_ms", "ms", "Webhook processing duration")
        instruments["openclaw.message.queued"] = _counter("openclaw.message.queued", "1", "Messages queued for processing")
        instruments["openclaw.message.processed"] = _counter("openclaw.message.processed", "1", "Messages processed by outcome")
        instruments["openclaw.message.duration_ms"] = _histogram("openclaw.message.duration_ms", "ms", "Message processing duration")
        instruments["openclaw.queue.depth"] = _histogram("openclaw.queue.depth", "1", "Queue depth on enqueue/dequeue")
        instruments["openclaw.queue.wait_ms"] = _histogram("openclaw.queue.wait_ms", "ms", "Queue wait time before execution")
        instruments["openclaw.queue.lane.enqueue"] = _counter("openclaw.queue.lane.enqueue", "1", "Command queue lane enqueue events")
        instruments["openclaw.queue.lane.dequeue"] = _counter("openclaw.queue.lane.dequeue", "1", "Command queue lane dequeue events")
        instruments["openclaw.session.state"] = _counter("openclaw.session.state", "1", "Session state transitions")
        instruments["openclaw.session.stuck"] = _counter("openclaw.session.stuck", "1", "Sessions stuck in processing")
        instruments["openclaw.session.stuck_age_ms"] = _histogram("openclaw.session.stuck_age_ms", "ms", "Age of stuck sessions")
        instruments["openclaw.run.attempt"] = _counter("openclaw.run.attempt", "1", "Run attempts")

    # Log exporter
    log_provider: Any = None
    log_handler: Any = None
    if logs_enabled:
        try:
            from opentelemetry.exporter.otlp.proto.http._log_exporter import (
                OTLPLogExporter,  # type: ignore[import]
            )
            from opentelemetry.sdk._logs import (  # type: ignore[import]
                LoggerProvider,
                LoggingHandler,
            )
            from opentelemetry.sdk._logs.export import (
                BatchLogRecordProcessor,  # type: ignore[import]
            )
            log_url = _resolve_otel_url(endpoint, "v1/logs")
            log_exp_kwargs: dict[str, Any] = {}
            if log_url:
                log_exp_kwargs["endpoint"] = log_url
            if headers:
                log_exp_kwargs["headers"] = headers
            log_exporter = OTLPLogExporter(**log_exp_kwargs)
            processor_kwargs: dict[str, Any] = {}
            if flush_interval_ms:
                processor_kwargs["schedule_delay_millis"] = flush_interval_ms
            proc = BatchLogRecordProcessor(log_exporter, **processor_kwargs)
            log_provider = LoggerProvider(resource=resource)
            log_provider.add_log_record_processor(proc)
            otel_otel_logger = log_provider.get_logger("openclaw")
            log_handler = _OtelLogHandler(otel_otel_logger)
            logging.root.addHandler(log_handler)
            logger.info("diagnostics-otel: logs exporter enabled (OTLP/HTTP)")
        except ImportError:
            pass
        except Exception as exc:
            logger.warning(f"diagnostics-otel: log exporter setup failed: {exc}")

    return _OtelState(
        sdk=tracer_provider or meter_provider,
        tracer=tracer,
        meter=meter,
        log_provider=log_provider,
        log_handler=log_handler,
        traces_enabled=traces_enabled,
        instruments=instruments,
    )


def _make_event_handler(state: _OtelState):
    def _handle(evt: dict) -> None:
        event_type = evt.get("type", "")
        try:
            if event_type == "model.usage":
                _record_model_usage(state, evt)
            elif event_type == "webhook.received":
                _record_webhook_received(state, evt)
            elif event_type == "webhook.processed":
                _record_webhook_processed(state, evt)
            elif event_type == "webhook.error":
                _record_webhook_error(state, evt)
            elif event_type == "message.queued":
                _record_message_queued(state, evt)
            elif event_type == "message.processed":
                _record_message_processed(state, evt)
            elif event_type == "queue.lane.enqueue":
                _record_lane_enqueue(state, evt)
            elif event_type == "queue.lane.dequeue":
                _record_lane_dequeue(state, evt)
            elif event_type == "session.state":
                _record_session_state(state, evt)
            elif event_type == "session.stuck":
                _record_session_stuck(state, evt)
            elif event_type == "run.attempt":
                _record_run_attempt(state, evt)
            elif event_type == "diagnostic.heartbeat":
                _record_heartbeat(state, evt)
        except Exception as exc:
            logger.debug(f"diagnostics-otel: handler error for {event_type}: {exc}")
    return _handle


# ---------------------------------------------------------------------------
# Register (using register_service — mirrors TS api.registerService)
# ---------------------------------------------------------------------------

def register(api: Any) -> None:
    from openclaw.plugins.types import OpenClawPluginService

    _state: list[_OtelState | None] = [None]
    _unsubscribe: list[Any] = [None]

    async def _start(ctx) -> None:
        raw_cfg = getattr(api, "config", None) or {}
        diagnostics_cfg = (raw_cfg.get("diagnostics") or {}) if isinstance(raw_cfg, dict) else {}
        otel_cfg = diagnostics_cfg.get("otel") or {}

        if not diagnostics_cfg.get("enabled", True):
            return
        if not otel_cfg.get("enabled", False):
            return

        protocol = otel_cfg.get("protocol") or os.environ.get("OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf")
        if protocol not in ("http/protobuf", "http"):
            logger.warning(f"diagnostics-otel: unsupported protocol {protocol}")
            return

        service_name = (
            (otel_cfg.get("serviceName") or "").strip()
            or os.environ.get("OTEL_SERVICE_NAME", "")
            or DEFAULT_SERVICE_NAME
        )

        state = _build_otel_state(otel_cfg, service_name)
        if state is None:
            return
        _state[0] = state

        try:
            from openclaw.infra.diagnostic_events import on_diagnostic_event
            handler = _make_event_handler(state)
            _unsubscribe[0] = on_diagnostic_event(handler)
        except Exception as exc:
            logger.warning(f"diagnostics-otel: failed to subscribe to events: {exc}")
            return

        logger.info(
            f"diagnostics-otel: started (service={service_name} "
            f"traces={'on' if state.traces_enabled else 'off'} "
            f"metrics={'on' if state.meter else 'off'})"
        )

    async def _stop(_ctx=None) -> None:
        if _unsubscribe[0] is not None:
            try:
                _unsubscribe[0]()
            except Exception:
                pass
            _unsubscribe[0] = None

        state = _state[0]
        _state[0] = None
        if state is None:
            return

        if state.log_handler is not None:
            try:
                logging.root.removeHandler(state.log_handler)
            except Exception:
                pass

        if state.log_provider is not None:
            try:
                state.log_provider.shutdown()
            except Exception:
                pass

        if state.sdk is not None:
            try:
                if hasattr(state.sdk, "shutdown"):
                    state.sdk.shutdown()
            except Exception:
                pass

    api.register_service(OpenClawPluginService(
        id="diagnostics-otel",
        start=_start,
        stop=_stop,
    ))


plugin = {
    "id": "diagnostics-otel",
    "name": "Diagnostics (OpenTelemetry)",
    "description": "Export OpenClaw diagnostics events to OpenTelemetry (traces, metrics, logs).",
    "register": register,
}
