"""Plugin manifest loading — mirrors src/plugins/manifest.ts"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from .types import PluginConfigUiHint, PluginKind

PLUGIN_MANIFEST_FILENAME = "openclaw.plugin.json"
PLUGIN_MANIFEST_FILENAMES = (PLUGIN_MANIFEST_FILENAME,)


@dataclass
class PluginManifest:
    id: str
    config_schema: dict
    kind: PluginKind | None = None
    channels: list[str] = field(default_factory=list)
    providers: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    name: str | None = None
    description: str | None = None
    version: str | None = None
    ui_hints: dict[str, PluginConfigUiHint] | None = None


@dataclass
class PluginManifestLoadOk:
    ok: bool = True
    manifest: PluginManifest = None  # type: ignore[assignment]
    manifest_path: str = ""


@dataclass
class PluginManifestLoadFail:
    ok: bool = False
    error: str = ""
    manifest_path: str = ""


PluginManifestLoadResult = PluginManifestLoadOk | PluginManifestLoadFail


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [entry.strip() for entry in value if isinstance(entry, str) and entry.strip()]


def resolve_plugin_manifest_path(root_dir: str) -> str:
    for filename in PLUGIN_MANIFEST_FILENAMES:
        candidate = os.path.join(root_dir, filename)
        if os.path.exists(candidate):
            return candidate
    return os.path.join(root_dir, PLUGIN_MANIFEST_FILENAME)


def load_plugin_manifest(root_dir: str) -> PluginManifestLoadResult:
    manifest_path = resolve_plugin_manifest_path(root_dir)
    if not os.path.exists(manifest_path):
        return PluginManifestLoadFail(
            error=f"plugin manifest not found: {manifest_path}",
            manifest_path=manifest_path,
        )
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception as e:
        return PluginManifestLoadFail(
            error=f"failed to parse plugin manifest: {e}",
            manifest_path=manifest_path,
        )

    if not isinstance(raw, dict):
        return PluginManifestLoadFail(
            error="plugin manifest must be an object",
            manifest_path=manifest_path,
        )

    plugin_id = raw.get("id", "")
    if not isinstance(plugin_id, str) or not plugin_id.strip():
        return PluginManifestLoadFail(
            error="plugin manifest requires id",
            manifest_path=manifest_path,
        )
    plugin_id = plugin_id.strip()

    config_schema = raw.get("configSchema")
    if not isinstance(config_schema, dict):
        return PluginManifestLoadFail(
            error="plugin manifest requires configSchema",
            manifest_path=manifest_path,
        )

    kind_raw = raw.get("kind")
    kind: PluginKind | None = kind_raw if isinstance(kind_raw, str) else None  # type: ignore[assignment]

    name = raw.get("name", "").strip() or None
    description = raw.get("description", "").strip() or None
    version = raw.get("version", "").strip() or None
    channels = _normalize_string_list(raw.get("channels"))
    providers = _normalize_string_list(raw.get("providers"))
    skills = _normalize_string_list(raw.get("skills"))

    ui_hints: dict | None = None
    raw_hints = raw.get("uiHints")
    if isinstance(raw_hints, dict):
        ui_hints = raw_hints

    return PluginManifestLoadOk(
        manifest=PluginManifest(
            id=plugin_id,
            config_schema=config_schema,
            kind=kind,
            channels=channels,
            providers=providers,
            skills=skills,
            name=name,
            description=description,
            version=version,
            ui_hints=ui_hints,
        ),
        manifest_path=manifest_path,
    )
