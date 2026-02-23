"""
Agent date/time utilities — fully aligned with TypeScript
openclaw/src/agents/date-time.ts.

Provides timezone resolution, time-format detection, timestamp
normalisation, and formatted user-time strings.
"""
from __future__ import annotations

import platform
import subprocess
from datetime import datetime, timezone, tzinfo
from typing import Any, Literal

TimeFormatPreference = Literal["auto", "12", "24"]
ResolvedTimeFormat = Literal["12", "24"]

_cached_time_format: ResolvedTimeFormat | None = None


# ---------------------------------------------------------------------------
# Timezone
# ---------------------------------------------------------------------------

def resolve_user_timezone(configured: str | None = None) -> str:
    """Return a valid IANA timezone string.

    Mirrors TS resolveUserTimezone().
    Validates the configured value; falls back to the system timezone or UTC.
    """
    if configured:
        trimmed = configured.strip()
        if trimmed:
            try:
                import zoneinfo
                zoneinfo.ZoneInfo(trimmed)
                return trimmed
            except Exception:
                pass

    try:
        import zoneinfo
        host = datetime.now(timezone.utc).astimezone().tzinfo
        if host is not None:
            name = getattr(host, "key", None) or str(host)
            if name and name.strip() and name != "UTC":
                try:
                    zoneinfo.ZoneInfo(name)
                    return name.strip()
                except Exception:
                    pass
    except Exception:
        pass

    return "UTC"


# ---------------------------------------------------------------------------
# Time format detection
# ---------------------------------------------------------------------------

def _detect_system_time_format() -> bool:
    """Return True if the system uses 24-hour format.

    Mirrors TS detectSystemTimeFormat().
    """
    if platform.system() == "Darwin":
        try:
            result = subprocess.run(
                ["defaults", "read", "-g", "AppleICUForce24HourTime"],
                capture_output=True,
                text=True,
                timeout=1,
            )
            val = result.stdout.strip()
            if val == "1":
                return True
            if val == "0":
                return False
        except Exception:
            pass

    if platform.system() == "Windows":
        try:
            result = subprocess.run(
                ["powershell", "-Command", "(Get-Culture).DateTimeFormat.ShortTimePattern"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            pattern = result.stdout.strip()
            if pattern.startswith("H"):
                return True
            if pattern.startswith("h"):
                return False
        except Exception:
            pass

    # Fall back: format 13:00 and see if "13" appears.
    try:
        from babel.dates import format_time  # type: ignore[import]
        sample = datetime(2000, 1, 1, 13, 0, 0)
        formatted = format_time(sample, format="short")
        return "13" in formatted
    except Exception:
        pass

    try:
        import locale
        sample = datetime(2000, 1, 1, 13, 0, 0)
        formatted = sample.strftime("%X")
        return "13" in formatted
    except Exception:
        pass

    return False


def resolve_user_time_format(preference: TimeFormatPreference = "auto") -> ResolvedTimeFormat:
    """Return the effective time format ("12" or "24").

    Mirrors TS resolveUserTimeFormat().
    """
    global _cached_time_format
    if preference in ("12", "24"):
        return preference  # type: ignore[return-value]
    if _cached_time_format is not None:
        return _cached_time_format
    _cached_time_format = "24" if _detect_system_time_format() else "12"
    return _cached_time_format


# ---------------------------------------------------------------------------
# Timestamp normalisation
# ---------------------------------------------------------------------------

def normalize_timestamp(
    raw: Any,
) -> dict[str, Any] | None:
    """Normalise a raw timestamp value to {timestampMs, timestampUtc}.

    Mirrors TS normalizeTimestamp().
    Accepts int/float (seconds or ms), ISO-8601 strings, or datetime objects.
    """
    if raw is None:
        return None

    timestamp_ms: int | None = None

    if isinstance(raw, datetime):
        timestamp_ms = int(raw.timestamp() * 1000)
    elif isinstance(raw, (int, float)):
        if not (raw == raw and abs(raw) != float("inf")):
            return None
        if raw < 1_000_000_000_000:
            timestamp_ms = round(raw * 1000)
        else:
            timestamp_ms = round(raw)
    elif isinstance(raw, str):
        trimmed = raw.strip()
        if not trimmed:
            return None
        import re
        if re.match(r"^\d+(\.\d+)?$", trimmed):
            num = float(trimmed)
            if not (num == num and abs(num) != float("inf")):
                return None
            if "." in trimmed:
                timestamp_ms = round(num * 1000)
            elif len(trimmed) >= 13:
                timestamp_ms = round(num)
            else:
                timestamp_ms = round(num * 1000)
        else:
            try:
                from dateutil import parser as dateutil_parser  # type: ignore[import]
                dt = dateutil_parser.parse(trimmed)
                timestamp_ms = int(dt.timestamp() * 1000)
            except Exception:
                try:
                    # ISO 8601 via stdlib
                    dt = datetime.fromisoformat(trimmed.replace("Z", "+00:00"))
                    timestamp_ms = int(dt.timestamp() * 1000)
                except Exception:
                    return None
    else:
        return None

    if timestamp_ms is None or not (
        timestamp_ms == timestamp_ms and abs(timestamp_ms) != float("inf")
    ):
        return None

    utc_str = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )
    return {"timestampMs": timestamp_ms, "timestampUtc": utc_str}


def with_normalized_timestamp(
    value: dict[str, Any],
    raw_timestamp: Any,
) -> dict[str, Any]:
    """Merge normalised timestamp fields into *value*, preserving existing values.

    Mirrors TS withNormalizedTimestamp().
    """
    normalized = normalize_timestamp(raw_timestamp)
    if not normalized:
        return value
    result = dict(value)
    if not (isinstance(result.get("timestampMs"), (int, float)) and result["timestampMs"] == result["timestampMs"]):  # noqa: E501
        result["timestampMs"] = normalized["timestampMs"]
    existing_utc = result.get("timestampUtc")
    if not (isinstance(existing_utc, str) and existing_utc.strip()):
        result["timestampUtc"] = normalized["timestampUtc"]
    return result


# ---------------------------------------------------------------------------
# User-friendly time formatting
# ---------------------------------------------------------------------------

def _ordinal_suffix(day: int) -> str:
    """Return the English ordinal suffix for a day number."""
    if 11 <= day <= 13:
        return "th"
    remainder = day % 10
    if remainder == 1:
        return "st"
    if remainder == 2:
        return "nd"
    if remainder == 3:
        return "rd"
    return "th"


def format_user_time(
    date: datetime,
    time_zone: str,
    fmt: ResolvedTimeFormat,
) -> str | None:
    """Format a datetime to a human-friendly string in the given timezone.

    Mirrors TS formatUserTime().

    Example output (24h): "Monday, January 1st, 2026 — 13:00"
    Example output (12h): "Monday, January 1st, 2026 — 1:00 PM"
    """
    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo(time_zone)
        local_dt = date.astimezone(tz)
    except Exception:
        local_dt = date.astimezone(timezone.utc)

    try:
        weekday = local_dt.strftime("%A")
        month = local_dt.strftime("%B")
        year = local_dt.year
        day = local_dt.day
        suffix = _ordinal_suffix(day)

        if fmt == "24":
            time_str = local_dt.strftime("%H:%M")
        else:
            hour = local_dt.hour % 12 or 12
            minute = local_dt.strftime("%M")
            period = "AM" if local_dt.hour < 12 else "PM"
            time_str = f"{hour}:{minute} {period}"

        return f"{weekday}, {month} {day}{suffix}, {year} \u2014 {time_str}"
    except Exception:
        return None
