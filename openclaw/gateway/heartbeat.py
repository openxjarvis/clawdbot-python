"""
Periodic heartbeat system for agents.

Executes periodic agent turns in the main session to:
- Keep sessions alive
- Monitor system health
- Provide status updates

Reference: openclaw/docs/gateway/heartbeat.md
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import InitVar, dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Default heartbeat prompt (matches TS)
DEFAULT_HEARTBEAT_PROMPT = (
    "Read HEARTBEAT.md if it exists (workspace context). "
    "Follow it strictly. Do not infer or repeat old tasks from prior chats. "
    "If nothing needs attention, reply HEARTBEAT_OK."
)

# Default ack cutoff (TS: ackMaxChars = 300)
DEFAULT_ACK_MAX_CHARS = 300


@dataclass
class ActiveHoursConfig:
    """Active hours restriction — mirrors TS HeartbeatActiveHours."""

    start: str = "00:00"      # HH:MM inclusive
    end: str = "24:00"        # HH:MM exclusive ("24:00" = end of day)
    timezone: str | None = None  # IANA tz or "user"/"local"; None = host tz

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ActiveHoursConfig):
            return self.start == other.start and self.end == other.end and self.timezone == other.timezone
        if isinstance(other, (tuple, list)) and len(other) == 2:
            # Compare as (start_hour, end_hour) integers
            try:
                s = int(self.start.split(":")[0])
                e = int(self.end.split(":")[0])
                return (s, e) == (int(other[0]), int(other[1]))
            except (ValueError, IndexError):
                pass
        return NotImplemented


@dataclass
class HeartbeatVisibilityConfig:
    """Per-channel heartbeat visibility — mirrors TS HeartbeatChannelConfig."""

    show_ok: bool = False       # Send HEARTBEAT_OK ack messages
    show_alerts: bool = True    # Send alert (non-OK) messages
    use_indicator: bool = True  # Emit indicator events


class HeartbeatConfig:
    """Heartbeat configuration — mirrors TS HeartbeatConfig.

    Fields intentionally mirror the TS config schema to allow 1-to-1 mapping.
    Accepts convenience kwargs ``enabled`` and ``interval_minutes`` in addition
    to the canonical ``every`` interval string.
    """

    def __init__(
        self,
        every: str = "30m",
        interval_minutes: int | None = None,
        enabled: bool | None = None,
        model: str | None = None,
        include_reasoning: bool = False,
        target: str = "last",
        to: str | None = None,
        account_id: str | None = None,
        prompt: str = DEFAULT_HEARTBEAT_PROMPT,
        ack_max_chars: int = DEFAULT_ACK_MAX_CHARS,
        session: str = "main",
        suppress_tool_error_warnings: bool = False,
        active_hours: "ActiveHoursConfig | tuple[int, int] | None" = None,
        visibility: "HeartbeatVisibilityConfig | None" = None,
    ) -> None:
        # Coerce interval_minutes → every
        if interval_minutes is not None:
            self.every = f"{interval_minutes}m"
        else:
            self.every = every
        self.model = model
        self.include_reasoning = include_reasoning
        self.target = target
        self.to = to
        self.account_id = account_id
        self.prompt = prompt
        self.ack_max_chars = ack_max_chars
        self.session = session
        self.suppress_tool_error_warnings = suppress_tool_error_warnings
        self.visibility = visibility if visibility is not None else HeartbeatVisibilityConfig()
        # Coerce tuple active_hours → ActiveHoursConfig
        if isinstance(active_hours, tuple):
            s_val, e_val = active_hours
            def _int_to_hhmm(v: "int | str") -> str:
                return f"{v:02d}:00" if isinstance(v, int) else str(v)
            self.active_hours: "ActiveHoursConfig | None" = ActiveHoursConfig(
                start=_int_to_hhmm(s_val), end=_int_to_hhmm(e_val)
            )
        else:
            self.active_hours = active_hours
        # Explicit enabled overrides computed value
        self._enabled_explicit: bool | None = enabled

    @property
    def enabled(self) -> bool:
        """True unless interval is "0m"/"0" (disabled)."""
        if self._enabled_explicit is not None:
            return self._enabled_explicit
        return not self._is_zero_interval()

    @enabled.setter
    def enabled(self, value: bool | None) -> None:
        self._enabled_explicit = value

    @property
    def interval_minutes(self) -> int:
        """Parsed interval in minutes."""
        return _parse_interval_minutes(self.every)

    def _is_zero_interval(self) -> bool:
        return _parse_interval_minutes(self.every) == 0

    def get_interval_minutes(self) -> int:
        """Parsed interval in minutes (alias for interval_minutes property)."""
        return self.interval_minutes

    def __repr__(self) -> str:
        return (
            f"HeartbeatConfig(enabled={self.enabled!r}, every={self.every!r}, "
            f"model={self.model!r}, include_reasoning={self.include_reasoning!r}, "
            f"target={self.target!r}, to={self.to!r}, account_id={self.account_id!r}, "
            f"prompt={self.prompt!r}, ack_max_chars={self.ack_max_chars!r}, "
            f"session={self.session!r}, suppress_tool_error_warnings={self.suppress_tool_error_warnings!r}, "
            f"active_hours={self.active_hours!r}, visibility={self.visibility!r})"
        )


def _parse_interval_minutes(every: str | int) -> int:
    """Parse a duration string like "30m", "1h", "90s" to minutes."""
    if isinstance(every, int):
        return max(0, every)
    s = str(every).strip().lower()
    if not s or s in ("0", "0m", "never"):
        return 0
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([smhd]?)", s)
    if not m:
        return 30
    val, unit = float(m.group(1)), m.group(2) or "m"
    if unit == "s":
        return max(0, int(val / 60))
    if unit == "m":
        return max(0, int(val))
    if unit == "h":
        return max(0, int(val * 60))
    if unit == "d":
        return max(0, int(val * 1440))
    return max(0, int(val))


def _is_heartbeat_ok(text: str, ack_max_chars: int = DEFAULT_ACK_MAX_CHARS) -> bool:
    """Return True when text is a HEARTBEAT_OK ack with no significant payload.

    Mirrors TS isHeartbeatOk() logic:
    - Strip leading/trailing HEARTBEAT_OK tokens and whitespace.
    - If the remainder is <= ack_max_chars, treat as pure ack.
    - If HEARTBEAT_OK appears in the middle (not at start/end), NOT treated as ack.
    """
    stripped = text.strip()
    upper = stripped.upper()

    starts_with_ok = upper.startswith("HEARTBEAT_OK")
    ends_with_ok = upper.endswith("HEARTBEAT_OK")

    # If HEARTBEAT_OK is neither at start nor end, it's in the middle — not an ack
    if not starts_with_ok and not ends_with_ok:
        # Check if it contains HEARTBEAT_OK at all (in middle)
        if "HEARTBEAT_OK" in upper:
            return False

    # Remove leading HEARTBEAT_OK
    while stripped.upper().startswith("HEARTBEAT_OK"):
        stripped = stripped[len("HEARTBEAT_OK"):].strip()
    # Remove trailing HEARTBEAT_OK
    while stripped.upper().endswith("HEARTBEAT_OK"):
        stripped = stripped[: -len("HEARTBEAT_OK")].strip()

    # If remaining text still has HEARTBEAT_OK in middle, not an ack
    if "HEARTBEAT_OK" in stripped.upper():
        return False

    return len(stripped) <= ack_max_chars


def strip_heartbeat_ok(text: str) -> str:
    """Strip leading/trailing HEARTBEAT_OK from a message body.

    Mirrors TS stripHeartbeatOk().
    """
    stripped = text.strip()
    while stripped.upper().startswith("HEARTBEAT_OK"):
        stripped = stripped[len("HEARTBEAT_OK"):].strip()
    while stripped.upper().endswith("HEARTBEAT_OK"):
        stripped = stripped[: -len("HEARTBEAT_OK")].strip()
    return stripped


def _parse_hhmm(hhmm: str) -> tuple[int, int]:
    """Parse "HH:MM" or "24:00" → (hours, minutes)."""
    parts = hhmm.split(":")
    if len(parts) == 2:
        return int(parts[0]), int(parts[1])
    return int(parts[0]), 0


def _in_active_hours(cfg: ActiveHoursConfig) -> bool:
    """Return True if now is within the configured active hours window."""
    now = datetime.now()
    # TODO: full IANA timezone support; currently uses local time only
    h, m = now.hour, now.minute
    current_mins = h * 60 + m
    start_h, start_m = _parse_hhmm(cfg.start)
    end_h, end_m = _parse_hhmm(cfg.end)
    start_mins = start_h * 60 + start_m
    # "24:00" is handled as 24*60 = 1440
    end_mins = end_h * 60 + end_m

    if start_mins <= end_mins:
        # Normal range
        return start_mins <= current_mins < end_mins
    else:
        # Wraps midnight
        return current_mins >= start_mins or current_mins < end_mins


class HeartbeatManager:
    """Manage periodic heartbeat agent turns.

    The heartbeat system executes periodic agent turns in the main session
    to provide health monitoring and keep connections alive.

    Features:
    - Configurable interval (default 30m)
    - Active hours restriction with HH:MM granularity
    - HEARTBEAT_OK special handling with ack_max_chars cutoff
    - Per-channel visibility settings (show_ok, show_alerts, use_indicator)
    - Custom prompt, model override, session override
    - suppressToolErrorWarnings flag

    Mirrors TS HeartbeatManager in openclaw/src/gateway/heartbeat.ts.
    """

    def __init__(
        self,
        config: HeartbeatConfig,
        agent_runtime: Any,
        session_key: str = "agent:main:main",
    ) -> None:
        self._config = config
        self._agent_runtime = agent_runtime
        self._session_key = session_key
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """Start heartbeat loop."""
        if not self._config.enabled:
            logger.info("Heartbeat disabled (interval=0)")
            return
        if self._running:
            logger.warning("Heartbeat already running")
            return
        self._running = True
        self._task = asyncio.create_task(self._heartbeat_loop())
        logger.info(
            "Heartbeat started: every=%s (%dm), target=%s",
            self._config.every,
            self._config.interval_minutes,
            self._config.target,
        )

    async def stop(self) -> None:
        """Stop heartbeat loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Heartbeat stopped")

    async def _heartbeat_loop(self) -> None:
        """Periodic heartbeat execution loop."""
        while self._running:
            try:
                await asyncio.sleep(self._config.interval_minutes * 60)
                if not self._should_run():
                    logger.debug("Skipping heartbeat: outside active hours or visibility all-off")
                    continue
                await self._execute_heartbeat()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Heartbeat execution error: %s", exc, exc_info=True)

    def _should_run(self) -> bool:
        """Return True if the heartbeat should fire now."""
        # Active hours check
        if self._config.active_hours and not _in_active_hours(self._config.active_hours):
            return False
        # If all visibility flags are off, skip (mirrors TS)
        vis = self._config.visibility
        if not vis.show_ok and not vis.show_alerts and not vis.use_indicator:
            return False
        return True

    async def _execute_heartbeat(self) -> None:
        """Execute heartbeat agent turn and handle HEARTBEAT_OK contract."""
        logger.info("Executing heartbeat turn (session=%s)", self._session_key)
        try:
            content_parts: list[str] = []
            async for event in self._agent_runtime.run_turn(
                session_key=self._session_key,
                messages=[{"role": "user", "content": self._config.prompt}],
                stream=True,
            ):
                etype = getattr(event, "type", None) or (event.get("type") if isinstance(event, dict) else "")
                data = getattr(event, "data", None) or (event.get("data", {}) if isinstance(event, dict) else {})
                if etype == "agent_text":
                    content_parts.append(data.get("text", "") if isinstance(data, dict) else "")
                elif etype == "agent_error":
                    logger.error("Heartbeat agent error: %s", data)
                elif etype == "agent_complete":
                    logger.debug("Heartbeat agent turn complete")

            full_text = "".join(content_parts).strip()
            is_ok = _is_heartbeat_ok(full_text, self._config.ack_max_chars)
            vis = self._config.visibility

            if is_ok:
                if vis.show_ok:
                    logger.info("Heartbeat OK (delivering ack)")
                    await self._deliver(strip_heartbeat_ok(full_text) or "HEARTBEAT_OK")
                else:
                    logger.debug("Heartbeat OK — suppressed (show_ok=False)")
            else:
                if vis.show_alerts:
                    logger.info("Heartbeat alert — delivering")
                    await self._deliver(full_text)
                else:
                    logger.debug("Heartbeat alert suppressed (show_alerts=False)")

            if vis.use_indicator:
                await self._emit_indicator(is_ok)

        except Exception as exc:
            logger.error("Heartbeat execution failed: %s", exc, exc_info=True)

    async def _deliver(self, text: str) -> None:
        """Send heartbeat message via the configured target/to/accountId.

        Currently delegates to agent_runtime if it exposes a send() method.
        If not, logs the message only.
        """
        if not text:
            return
        if hasattr(self._agent_runtime, "send_heartbeat_message"):
            await self._agent_runtime.send_heartbeat_message(
                text=text,
                target=self._config.target,
                to=self._config.to,
                account_id=self._config.account_id,
            )
        else:
            logger.info("Heartbeat message (target=%s): %s", self._config.target, text[:200])

    async def _emit_indicator(self, is_ok: bool) -> None:
        """Emit a heartbeat indicator event."""
        if hasattr(self._agent_runtime, "emit_heartbeat_indicator"):
            await self._agent_runtime.emit_heartbeat_indicator(ok=is_ok)

    async def trigger_now(self) -> None:
        """Trigger an immediate heartbeat (manual wake).

        Mirrors TS triggerHeartbeatNow() / system event --mode now.
        """
        logger.info("Manual heartbeat triggered")
        await self._execute_heartbeat()

    @property
    def is_running(self) -> bool:
        return self._running

    def get_config(self) -> HeartbeatConfig:
        return self._config

    def update_config(self, config: HeartbeatConfig) -> None:
        """Update configuration (requires restart to take effect)."""
        self._config = config


def resolve_heartbeat_config(
    agent_cfg: dict[str, Any],
    defaults_cfg: dict[str, Any] | None = None,
) -> HeartbeatConfig | None:
    """Build a HeartbeatConfig from agent config dict.

    Merges agents.defaults.heartbeat on top and then agent-specific heartbeat
    on top of that, mirroring TS config merging.

    Returns None if heartbeat is not configured or interval is 0.
    """
    base: dict[str, Any] = {}
    if defaults_cfg:
        base.update(defaults_cfg.get("heartbeat") or {})
    base.update(agent_cfg.get("heartbeat") or {})

    if not base:
        return None

    every = base.get("every", "30m")
    if _parse_interval_minutes(str(every)) == 0:
        return None

    active_hours_raw = base.get("activeHours") or base.get("active_hours")
    active_hours: ActiveHoursConfig | None = None
    if active_hours_raw and isinstance(active_hours_raw, dict):
        active_hours = ActiveHoursConfig(
            start=active_hours_raw.get("start", "00:00"),
            end=active_hours_raw.get("end", "24:00"),
            timezone=active_hours_raw.get("timezone"),
        )

    vis_raw = base.get("visibility") or {}
    visibility = HeartbeatVisibilityConfig(
        show_ok=vis_raw.get("showOk", vis_raw.get("show_ok", False)),
        show_alerts=vis_raw.get("showAlerts", vis_raw.get("show_alerts", True)),
        use_indicator=vis_raw.get("useIndicator", vis_raw.get("use_indicator", True)),
    )

    return HeartbeatConfig(
        every=str(every),
        model=base.get("model"),
        include_reasoning=base.get("includeReasoning", base.get("include_reasoning", False)),
        target=base.get("target", "last"),
        to=base.get("to"),
        account_id=base.get("accountId") or base.get("account_id"),
        prompt=base.get("prompt", DEFAULT_HEARTBEAT_PROMPT),
        ack_max_chars=int(base.get("ackMaxChars", base.get("ack_max_chars", DEFAULT_ACK_MAX_CHARS))),
        session=base.get("session", "main"),
        suppress_tool_error_warnings=bool(
            base.get("suppressToolErrorWarnings", base.get("suppress_tool_error_warnings", False))
        ),
        active_hours=active_hours,
        visibility=visibility,
    )


__all__ = [
    "ActiveHoursConfig",
    "HeartbeatConfig",
    "HeartbeatManager",
    "HeartbeatVisibilityConfig",
    "DEFAULT_HEARTBEAT_PROMPT",
    "DEFAULT_ACK_MAX_CHARS",
    "resolve_heartbeat_config",
    "strip_heartbeat_ok",
    "_is_heartbeat_ok",
    "_parse_interval_minutes",
]
