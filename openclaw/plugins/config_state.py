"""Plugin config state — mirrors src/plugins/config-state.ts"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

BUNDLED_ENABLED_BY_DEFAULT: frozenset[str] = frozenset([
    "device-pair",
    "phone-control",
    "talk-voice",
])


@dataclass
class NormalizedPluginsConfig:
    enabled: bool
    allow: list[str]
    deny: list[str]
    load_paths: list[str]
    slots: dict  # {"memory": str | None}
    entries: dict[str, dict]  # pluginId -> {enabled?, config?}


def _default_slot_id_for_key(key: str) -> str | None:
    """mirrors defaultSlotIdForKey from plugins/slots.ts"""
    if key == "memory":
        return "memory-core"
    return None


def _normalize_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [entry.strip() for entry in value if isinstance(entry, str) and entry.strip()]


def _normalize_slot_value(value: Any) -> str | None:
    """None means 'use default', empty/"none" string means disabled (null)."""
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    if trimmed.lower() == "none":
        return ""  # sentinel: disabled
    return trimmed


_DISABLED_SLOT = ""  # sentinel value meaning memory slot is explicitly disabled


def _normalize_plugin_entries(entries: Any) -> dict[str, dict]:
    if not entries or not isinstance(entries, dict):
        return {}
    normalized: dict[str, dict] = {}
    for key, value in entries.items():
        if not key.strip():
            continue
        if not value or not isinstance(value, dict):
            normalized[key] = {}
            continue
        entry: dict = {}
        if "enabled" in value and isinstance(value["enabled"], bool):
            entry["enabled"] = value["enabled"]
        if "config" in value:
            entry["config"] = value["config"]
        normalized[key] = entry
    return normalized


def normalize_plugins_config(config: Any = None) -> NormalizedPluginsConfig:
    """Normalize raw plugins config — mirrors normalizePluginsConfig()."""
    if config is None:
        plugins = None
    elif isinstance(config, dict):
        plugins = config
    else:
        plugins = getattr(config, "__dict__", {})

    if plugins is None:
        plugins = {}

    def _get(key: str, default: Any = None) -> Any:
        if isinstance(plugins, dict):
            return plugins.get(key, default)
        return getattr(plugins, key, default)

    def _nested(key1: str, key2: str, default: Any = None) -> Any:
        inner = _get(key1)
        if inner is None:
            return default
        if isinstance(inner, dict):
            return inner.get(key2, default)
        return getattr(inner, key2, default)

    memory_raw = _nested("slots", "memory")
    memory_slot = _normalize_slot_value(memory_raw)
    if memory_slot is None:
        memory_slot = _default_slot_id_for_key("memory")

    return NormalizedPluginsConfig(
        enabled=_get("enabled", True) is not False,
        allow=_normalize_list(_get("allow")),
        deny=_normalize_list(_get("deny")),
        load_paths=_normalize_list(_nested("load", "paths")),
        slots={"memory": memory_slot},
        entries=_normalize_plugin_entries(_get("entries")),
    )


def resolve_enable_state(
    plugin_id: str,
    origin: str,
    config: NormalizedPluginsConfig,
) -> dict:
    """Determine whether a plugin is enabled and why.

    Mirrors resolveEnableState() from config-state.ts.
    Returns dict with keys: enabled (bool), reason (str | None).
    """
    if not config.enabled:
        return {"enabled": False, "reason": "plugins disabled"}
    if plugin_id in config.deny:
        return {"enabled": False, "reason": "blocked by denylist"}
    if config.allow and plugin_id not in config.allow:
        return {"enabled": False, "reason": "not in allowlist"}

    memory_slot = config.slots.get("memory")
    if memory_slot == plugin_id:
        return {"enabled": True}

    entry = config.entries.get(plugin_id)
    if entry:
        if entry.get("enabled") is True:
            return {"enabled": True}
        if entry.get("enabled") is False:
            return {"enabled": False, "reason": "disabled in config"}

    if origin == "bundled" and plugin_id in BUNDLED_ENABLED_BY_DEFAULT:
        return {"enabled": True}
    if origin == "bundled":
        return {"enabled": False, "reason": "bundled (disabled by default)"}

    return {"enabled": True}


def resolve_memory_slot_decision(
    plugin_id: str,
    kind: str | None,
    slot: str | None,
    selected_id: str | None,
) -> dict:
    """Determine memory-slot enable decision for a plugin.

    Mirrors resolveMemorySlotDecision() from config-state.ts.
    """
    if kind != "memory":
        return {"enabled": True}
    if slot == _DISABLED_SLOT:  # explicitly "none"
        return {"enabled": False, "reason": "memory slot disabled"}
    if isinstance(slot, str) and slot:
        if slot == plugin_id:
            return {"enabled": True, "selected": True}
        return {"enabled": False, "reason": f'memory slot set to "{slot}"'}
    if selected_id and selected_id != plugin_id:
        return {"enabled": False, "reason": f'memory slot already filled by "{selected_id}"'}
    return {"enabled": True, "selected": True}
