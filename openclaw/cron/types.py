"""Cron type definitions matching TypeScript openclaw/src/cron/types.ts"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, TypedDict


# ---------------------------------------------------------------------------
# Schedule types
# ---------------------------------------------------------------------------

@dataclass
class AtSchedule:
    """One-time absolute timestamp schedule (TS: kind="at")"""
    at: str  # ISO-8601 or ms-since-epoch string
    type: Literal["at"] = "at"

    @property
    def timestamp(self) -> str:  # backwards-compat alias
        return self.at


@dataclass
class EverySchedule:
    """Interval-based schedule (TS: kind="every")"""
    every_ms: int  # TS: everyMs
    type: Literal["every"] = "every"
    anchor_ms: int | None = None  # TS: anchorMs (epoch ms, not ISO string)

    @property
    def interval_ms(self) -> int:  # backwards-compat alias
        return self.every_ms


@dataclass
class CronSchedule:
    """Cron expression schedule (TS: kind="cron")"""
    expr: str       # TS: expr (was "expression")
    type: Literal["cron"] = "cron"
    tz: str | None = "UTC"   # TS: tz
    stagger_ms: int | None = None  # TS: staggerMs

    @property
    def expression(self) -> str:  # backwards-compat alias
        return self.expr

    @property
    def timezone(self) -> str | None:  # backwards-compat alias
        return self.tz


# Union type for all schedule types
CronScheduleType = AtSchedule | EverySchedule | CronSchedule


# ---------------------------------------------------------------------------
# Payload types
# ---------------------------------------------------------------------------

@dataclass
class SystemEventPayload:
    """System event payload for main session (TS: kind="systemEvent")"""
    text: str
    kind: Literal["systemEvent"] = "systemEvent"


@dataclass
class AgentTurnPayload:
    """Agent turn payload for isolated sessions (TS: kind="agentTurn")"""
    message: str  # TS uses "message" (not "prompt")
    kind: Literal["agentTurn"] = "agentTurn"
    model: str | None = None
    thinking: str | None = None
    timeout_seconds: int | None = None   # TS: timeoutSeconds
    allow_unsafe_external_content: bool = False  # TS: allowUnsafeExternalContent
    fallbacks: list[str] | None = None   # TS: fallbacks — model fallback chain
    light_context: bool = False          # TS: lightContext — skip heavy context loading
    # Legacy delivery hint fields (migrated to top-level delivery on normalize)
    deliver: bool | None = None
    channel: str | None = None
    to: str | None = None
    best_effort_deliver: bool | None = None  # TS: bestEffortDeliver

    @property
    def prompt(self) -> str:  # backwards-compat alias
        return self.message


# Union type for payloads
CronPayload = SystemEventPayload | AgentTurnPayload


# ---------------------------------------------------------------------------
# Delivery configuration
# ---------------------------------------------------------------------------

@dataclass
class CronFailureDestination:
    """Failure-specific delivery destination (TS: failureDestination sub-object).

    When set on a CronDelivery, failure alerts are routed here instead of the
    main delivery target.
    """
    channel: str | None = None
    to: str | None = None        # recipient id / chat id


@dataclass
class CronFailureAlert:
    """Failure alert configuration (TS: CronFailureAlert).

    After `after_n_errors` consecutive errors the service sends an alert
    message via the failure_destination (or main delivery) channel,
    rate-limited by `cooldown_ms`.
    """
    after_n_errors: int = 3              # TS: afterNErrors
    cooldown_ms: int = 3_600_000         # TS: cooldownMs  (1 hour default)
    message: str | None = None           # Optional custom alert message template


@dataclass
class CronDelivery:
    """Delivery configuration for isolated agent jobs (TS: CronDelivery)"""
    mode: Literal["none", "announce", "webhook"] = "announce"
    channel: str | None = None           # ChannelId or "last"
    to: str | None = None                # TS: to (was "target")
    best_effort: bool = False            # TS: bestEffort
    account_id: str | None = None        # TS: accountId — preferred account for sending
    failure_destination: CronFailureDestination | None = None  # TS: failureDestination


# ---------------------------------------------------------------------------
# Job state
# ---------------------------------------------------------------------------

@dataclass
class CronJobState:
    """Runtime state for cron job (TS: CronJobState)"""
    next_run_ms: int | None = None        # TS: nextRunAtMs
    running_at_ms: int | None = None      # TS: runningAtMs
    last_run_at_ms: int | None = None     # TS: lastRunAtMs
    last_status: Literal["ok", "error", "skipped"] | None = None
    last_error: str | None = None
    last_duration_ms: int | None = None   # TS: lastDurationMs
    consecutive_errors: int = 0           # TS: consecutiveErrors
    schedule_error_count: int | None = None  # TS: scheduleErrorCount
    # Delivery tracking fields (TS: lastDeliveryStatus / lastDeliveryError / lastDelivered)
    last_delivery_status: Literal["ok", "error", "skipped"] | None = None
    last_delivery_error: str | None = None
    last_delivered: int | None = None     # TS: lastDelivered (epoch ms of last successful delivery)
    last_failure_alert_at_ms: int | None = None  # TS: lastFailureAlertAtMs — cooldown gate


# ---------------------------------------------------------------------------
# Run telemetry / outcome
# ---------------------------------------------------------------------------

@dataclass
class CronUsageSummary:
    """LLM token usage summary"""
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_write_tokens: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
        }.items() if v is not None}


# ---------------------------------------------------------------------------
# Run telemetry and outcome (TS: CronRunTelemetry, CronRunOutcome)
# ---------------------------------------------------------------------------

@dataclass
class CronRunTelemetry:
    """Telemetry for a single cron job run (TS: CronRunTelemetry)."""
    model: str | None = None
    provider: str | None = None
    usage: CronUsageSummary | None = None


@dataclass
class CronRunOutcome:
    """Outcome of a cron job run (TS: CronRunOutcome)."""
    status: Literal["ok", "error", "skipped"] = "ok"
    error: str | None = None
    summary: str | None = None
    session_id: str | None = None
    session_key: str | None = None


# ---------------------------------------------------------------------------
# Input shapes for service methods (TS: CronJobCreate, CronJobPatch)
# ---------------------------------------------------------------------------

class CronJobCreate(TypedDict, total=False):
    """Input shape for creating a new cron job (TS: CronJobCreate)."""
    name: str
    description: str
    enabled: bool
    agent_id: str
    session_key: str
    schedule: dict[str, Any]
    session_target: Literal["main", "isolated"]
    wake_mode: Literal["next-heartbeat", "now"]
    payload: dict[str, Any]
    delivery: dict[str, Any]
    delete_after_run: bool


class CronJobPatch(TypedDict, total=False):
    """Input shape for updating an existing cron job (TS: CronJobPatch)."""
    name: str
    description: str
    enabled: bool
    agent_id: str
    session_key: str
    schedule: dict[str, Any]
    session_target: Literal["main", "isolated"]
    wake_mode: Literal["next-heartbeat", "now"]
    payload: dict[str, Any]
    delivery: dict[str, Any]
    delete_after_run: bool


# ---------------------------------------------------------------------------
# Main cron job definition
# ---------------------------------------------------------------------------

@dataclass
class CronJob:
    """
    Cron job definition (TS: CronJob in openclaw/src/cron/types.ts).
    """

    # Identity
    id: str
    agent_id: str | None = None  # TS: agentId
    session_key: str | None = None  # TS: sessionKey — origin session namespace

    # Metadata
    name: str = ""
    description: str | None = None
    enabled: bool = True
    delete_after_run: bool = False  # TS: deleteAfterRun

    # Scheduling
    schedule: CronScheduleType = field(default_factory=lambda: AtSchedule(at="", type="at"))

    # Execution
    session_target: Literal["main", "isolated"] = "main"   # TS: sessionTarget
    wake_mode: Literal["next-heartbeat", "now"] = "next-heartbeat"  # TS: wakeMode

    # Payload
    payload: CronPayload = field(default_factory=lambda: SystemEventPayload(text="", kind="systemEvent"))

    # Delivery (for isolated jobs)
    delivery: CronDelivery | None = None

    # Failure alert (TS: failureAlert)
    failure_alert: CronFailureAlert | None = None

    # State
    state: CronJobState = field(default_factory=CronJobState)

    # Timestamps
    created_at_ms: int = field(default_factory=lambda: int(datetime.now().timestamp() * 1000))
    updated_at_ms: int = field(default_factory=lambda: int(datetime.now().timestamp() * 1000))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization (snake_case keys for store)."""
        result: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "enabled": self.enabled,
            "session_target": self.session_target,
            "wake_mode": self.wake_mode,
            "created_at_ms": self.created_at_ms,
            "updated_at_ms": self.updated_at_ms,
        }

        if self.agent_id:
            result["agent_id"] = self.agent_id
        if self.session_key:
            result["session_key"] = self.session_key
        if self.description:
            result["description"] = self.description
        if self.delete_after_run:
            result["delete_after_run"] = self.delete_after_run

        # Schedule
        if isinstance(self.schedule, AtSchedule):
            result["schedule"] = {"type": "at", "at": self.schedule.at}
        elif isinstance(self.schedule, EverySchedule):
            s: dict[str, Any] = {"type": "every", "every_ms": self.schedule.every_ms}
            if self.schedule.anchor_ms is not None:
                s["anchor_ms"] = self.schedule.anchor_ms
            result["schedule"] = s
        elif isinstance(self.schedule, CronSchedule):
            s = {"type": "cron", "expr": self.schedule.expr}
            if self.schedule.tz:
                s["tz"] = self.schedule.tz
            if self.schedule.stagger_ms is not None:
                s["stagger_ms"] = self.schedule.stagger_ms
            result["schedule"] = s

        # Payload (use TS wire-format field names for agentTurn: "message")
        if isinstance(self.payload, SystemEventPayload):
            result["payload"] = {"kind": "systemEvent", "text": self.payload.text}
        elif isinstance(self.payload, AgentTurnPayload):
            p: dict[str, Any] = {"kind": "agentTurn", "message": self.payload.message}
            if self.payload.model:
                p["model"] = self.payload.model
            if self.payload.thinking:
                p["thinking"] = self.payload.thinking
            if self.payload.timeout_seconds is not None:
                p["timeout_seconds"] = self.payload.timeout_seconds
            if self.payload.allow_unsafe_external_content:
                p["allow_unsafe_external_content"] = self.payload.allow_unsafe_external_content
            if self.payload.fallbacks:
                p["fallbacks"] = list(self.payload.fallbacks)
            if self.payload.light_context:
                p["light_context"] = self.payload.light_context
            result["payload"] = p

        # Delivery
        if self.delivery:
            d: dict[str, Any] = {"mode": self.delivery.mode}
            if self.delivery.channel:
                d["channel"] = self.delivery.channel
            if self.delivery.to:
                d["to"] = self.delivery.to
            if self.delivery.best_effort:
                d["best_effort"] = self.delivery.best_effort
            if self.delivery.account_id:
                d["account_id"] = self.delivery.account_id
            if self.delivery.failure_destination:
                fd: dict[str, Any] = {}
                if self.delivery.failure_destination.channel:
                    fd["channel"] = self.delivery.failure_destination.channel
                if self.delivery.failure_destination.to:
                    fd["to"] = self.delivery.failure_destination.to
                if fd:
                    d["failure_destination"] = fd
            result["delivery"] = d

        # Failure alert
        if self.failure_alert:
            fa: dict[str, Any] = {"after_n_errors": self.failure_alert.after_n_errors}
            if self.failure_alert.cooldown_ms != 3_600_000:
                fa["cooldown_ms"] = self.failure_alert.cooldown_ms
            if self.failure_alert.message:
                fa["message"] = self.failure_alert.message
            result["failure_alert"] = fa

        # State
        state_dict: dict[str, Any] = {}
        if self.state.next_run_ms is not None:
            state_dict["next_run_ms"] = self.state.next_run_ms
        if self.state.running_at_ms is not None:
            state_dict["running_at_ms"] = self.state.running_at_ms
        if self.state.last_run_at_ms is not None:
            state_dict["last_run_at_ms"] = self.state.last_run_at_ms
        if self.state.last_status is not None:
            state_dict["last_status"] = self.state.last_status
        if self.state.last_error is not None:
            state_dict["last_error"] = self.state.last_error
        if self.state.last_duration_ms is not None:
            state_dict["last_duration_ms"] = self.state.last_duration_ms
        if self.state.consecutive_errors:
            state_dict["consecutive_errors"] = self.state.consecutive_errors
        if self.state.schedule_error_count is not None:
            state_dict["schedule_error_count"] = self.state.schedule_error_count
        if self.state.last_delivery_status is not None:
            state_dict["last_delivery_status"] = self.state.last_delivery_status
        if self.state.last_delivery_error is not None:
            state_dict["last_delivery_error"] = self.state.last_delivery_error
        if self.state.last_delivered is not None:
            state_dict["last_delivered"] = self.state.last_delivered
        if self.state.last_failure_alert_at_ms is not None:
            state_dict["last_failure_alert_at_ms"] = self.state.last_failure_alert_at_ms
        result["state"] = state_dict

        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CronJob:
        """Create from dictionary (handles both old and new field names)."""
        # Parse schedule
        schedule_data = data.get("schedule", {})
        schedule_type = schedule_data.get("type", schedule_data.get("kind", "at"))

        schedule: CronScheduleType
        if schedule_type == "at":
            at_val = (
                schedule_data.get("at")
                or schedule_data.get("timestamp")
                or schedule_data.get("atMs", "")
            )
            schedule = AtSchedule(at=str(at_val), type="at")
        elif schedule_type == "every":
            every_ms = (
                schedule_data.get("every_ms")
                or schedule_data.get("everyMs")
                or schedule_data.get("interval_ms")
                or schedule_data.get("intervalMs")
                or 0
            )
            anchor_ms = (
                schedule_data.get("anchor_ms")
                or schedule_data.get("anchorMs")
            )
            schedule = EverySchedule(
                every_ms=int(every_ms),
                type="every",
                anchor_ms=int(anchor_ms) if anchor_ms is not None else None,
            )
        elif schedule_type == "cron":
            expr = (
                schedule_data.get("expr")
                or schedule_data.get("expression")
                or ""
            )
            tz = schedule_data.get("tz") or schedule_data.get("timezone") or "UTC"
            stagger_ms = (
                schedule_data.get("stagger_ms")
                or schedule_data.get("staggerMs")
            )
            schedule = CronSchedule(
                expr=expr,
                type="cron",
                tz=tz,
                stagger_ms=int(stagger_ms) if stagger_ms is not None else None,
            )
        else:
            schedule = AtSchedule(at="", type="at")

        # Parse payload — TS uses "message" for agentTurn
        payload_data = data.get("payload", {})
        payload_kind = payload_data.get("kind", "systemEvent")

        payload: CronPayload
        if payload_kind == "systemEvent":
            payload = SystemEventPayload(
                text=payload_data.get("text", ""),
                kind="systemEvent",
            )
        elif payload_kind == "agentTurn":
            msg = (
                payload_data.get("message")
                or payload_data.get("prompt")
                or ""
            )
            raw_fallbacks = payload_data.get("fallbacks") or payload_data.get("modelFallbacks")
            fallbacks: list[str] | None = None
            if isinstance(raw_fallbacks, list) and raw_fallbacks:
                fallbacks = [str(f) for f in raw_fallbacks if f]
            payload = AgentTurnPayload(
                message=msg,
                kind="agentTurn",
                model=payload_data.get("model"),
                thinking=payload_data.get("thinking"),
                timeout_seconds=payload_data.get("timeout_seconds") or payload_data.get("timeoutSeconds"),
                allow_unsafe_external_content=bool(
                    payload_data.get("allow_unsafe_external_content")
                    or payload_data.get("allowUnsafeExternalContent")
                ),
                fallbacks=fallbacks,
                light_context=bool(
                    payload_data.get("light_context")
                    or payload_data.get("lightContext")
                ),
            )
        else:
            payload = SystemEventPayload(text="", kind="systemEvent")

        # Parse delivery
        delivery: CronDelivery | None = None
        if "delivery" in data and isinstance(data["delivery"], dict):
            dd = data["delivery"]
            fd_raw = dd.get("failure_destination") or dd.get("failureDestination")
            failure_dest: CronFailureDestination | None = None
            if isinstance(fd_raw, dict):
                failure_dest = CronFailureDestination(
                    channel=fd_raw.get("channel"),
                    to=fd_raw.get("to"),
                )
            delivery = CronDelivery(
                mode=dd.get("mode", "announce"),
                channel=dd.get("channel"),
                to=dd.get("to") or dd.get("target"),
                best_effort=bool(dd.get("best_effort") or dd.get("bestEffort")),
                account_id=dd.get("account_id") or dd.get("accountId"),
                failure_destination=failure_dest,
            )

        # Parse failure_alert
        failure_alert: CronFailureAlert | None = None
        fa_raw = data.get("failure_alert") or data.get("failureAlert")
        if isinstance(fa_raw, dict):
            failure_alert = CronFailureAlert(
                after_n_errors=int(
                    fa_raw.get("after_n_errors")
                    or fa_raw.get("afterNErrors")
                    or 3
                ),
                cooldown_ms=int(
                    fa_raw.get("cooldown_ms")
                    or fa_raw.get("cooldownMs")
                    or 3_600_000
                ),
                message=fa_raw.get("message"),
            )

        # Parse state
        state_data = data.get("state", {})
        state = CronJobState(
            next_run_ms=state_data.get("next_run_ms") or state_data.get("nextRunAtMs"),
            running_at_ms=state_data.get("running_at_ms") or state_data.get("runningAtMs"),
            last_run_at_ms=state_data.get("last_run_at_ms") or state_data.get("lastRunAtMs"),
            last_status=state_data.get("last_status") or state_data.get("lastStatus"),
            last_error=state_data.get("last_error") or state_data.get("lastError"),
            last_duration_ms=state_data.get("last_duration_ms") or state_data.get("lastDurationMs"),
            consecutive_errors=int(
                state_data.get("consecutive_errors")
                or state_data.get("consecutiveErrors")
                or 0
            ),
            schedule_error_count=(
                state_data.get("schedule_error_count")
                or state_data.get("scheduleErrorCount")
            ),
            last_delivery_status=state_data.get("last_delivery_status") or state_data.get("lastDeliveryStatus"),
            last_delivery_error=state_data.get("last_delivery_error") or state_data.get("lastDeliveryError"),
            last_delivered=state_data.get("last_delivered") or state_data.get("lastDelivered"),
            last_failure_alert_at_ms=(
                state_data.get("last_failure_alert_at_ms")
                or state_data.get("lastFailureAlertAtMs")
            ),
        )

        now_ms = int(datetime.now().timestamp() * 1000)
        return cls(
            id=data.get("id", ""),
            agent_id=data.get("agent_id") or data.get("agentId"),
            session_key=data.get("session_key") or data.get("sessionKey"),
            name=data.get("name", ""),
            description=data.get("description"),
            enabled=bool(data.get("enabled", True)),
            delete_after_run=bool(data.get("delete_after_run") or data.get("deleteAfterRun")),
            schedule=schedule,
            session_target=data.get("session_target") or data.get("sessionTarget") or "main",
            wake_mode=data.get("wake_mode") or data.get("wakeMode") or "next-heartbeat",
            payload=payload,
            delivery=delivery,
            failure_alert=failure_alert,
            state=state,
            created_at_ms=int(data.get("created_at_ms") or data.get("createdAtMs") or now_ms),
            updated_at_ms=int(data.get("updated_at_ms") or data.get("updatedAtMs") or now_ms),
        )
