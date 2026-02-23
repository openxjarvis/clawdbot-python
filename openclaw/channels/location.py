"""Location utilities — mirrors src/channels/location.ts"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

LocationSource = Literal["pin", "place", "live"]


@dataclass
class NormalizedLocation:
    latitude: float
    longitude: float
    accuracy: float | None = None
    name: str | None = None
    address: str | None = None
    is_live: bool | None = None
    source: LocationSource | None = None
    caption: str | None = None


def _resolve_location(loc: NormalizedLocation) -> dict:
    if loc.source:
        source: LocationSource = loc.source
    elif loc.is_live:
        source = "live"
    elif loc.name or loc.address:
        source = "place"
    else:
        source = "pin"
    is_live = bool(loc.is_live if loc.is_live is not None else source == "live")
    return {**loc.__dict__, "source": source, "is_live": is_live}


def _format_accuracy(accuracy: float | None) -> str:
    if accuracy is None or not (accuracy == accuracy):  # NaN check
        return ""
    return f" ±{round(accuracy)}m"


def _format_coords(lat: float, lon: float) -> str:
    return f"{lat:.6f}, {lon:.6f}"


def format_location_text(location: NormalizedLocation) -> str:
    resolved = _resolve_location(location)
    coords = _format_coords(resolved["latitude"], resolved["longitude"])
    accuracy = _format_accuracy(resolved.get("accuracy"))
    caption = (resolved.get("caption") or "").strip()

    if resolved["source"] == "live" or resolved["is_live"]:
        header = f"🛰 Live location: {coords}{accuracy}"
    elif resolved.get("name") or resolved.get("address"):
        label_parts = [p for p in [resolved.get("name"), resolved.get("address")] if p]
        label = " — ".join(label_parts)
        header = f"📍 {label} ({coords}{accuracy})"
    else:
        header = f"📍 {coords}{accuracy}"

    return f"{header}\n{caption}" if caption else header


def to_location_context(location: NormalizedLocation) -> dict:
    resolved = _resolve_location(location)
    ctx: dict = {
        "LocationLat": resolved["latitude"],
        "LocationLon": resolved["longitude"],
        "LocationSource": resolved["source"],
        "LocationIsLive": resolved["is_live"],
    }
    if resolved.get("accuracy") is not None:
        ctx["LocationAccuracy"] = resolved["accuracy"]
    if resolved.get("name"):
        ctx["LocationName"] = resolved["name"]
    if resolved.get("address"):
        ctx["LocationAddress"] = resolved["address"]
    return ctx
