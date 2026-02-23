"""Plugin manifest registry — mirrors src/plugins/manifest-registry.ts"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any

from .config_state import NormalizedPluginsConfig, normalize_plugins_config
from .manifest import PluginManifest, load_plugin_manifest
from .types import PluginConfigUiHint, PluginDiagnostic, PluginKind, PluginOrigin

# Precedence: config > workspace > global > bundled
PLUGIN_ORIGIN_RANK: dict[str, int] = {
    "config": 0,
    "workspace": 1,
    "global": 2,
    "bundled": 3,
}

DEFAULT_MANIFEST_CACHE_MS = 200


@dataclass
class PluginManifestRecord:
    id: str
    origin: PluginOrigin
    root_dir: str
    source: str
    manifest_path: str
    channels: list[str] = field(default_factory=list)
    providers: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    name: str | None = None
    description: str | None = None
    version: str | None = None
    kind: PluginKind | None = None
    workspace_dir: str | None = None
    schema_cache_key: str | None = None
    config_schema: dict | None = None
    config_ui_hints: dict[str, PluginConfigUiHint] | None = None


@dataclass
class PluginManifestRegistry:
    plugins: list[PluginManifestRecord] = field(default_factory=list)
    diagnostics: list[PluginDiagnostic] = field(default_factory=list)


# In-process cache: cacheKey -> (expires_at, registry)
_registry_cache: dict[str, tuple[float, PluginManifestRegistry]] = {}


def clear_plugin_manifest_registry_cache() -> None:
    _registry_cache.clear()


def _resolve_manifest_cache_ms() -> int:
    raw = os.environ.get("OPENCLAW_PLUGIN_MANIFEST_CACHE_MS", "").strip()
    if raw == "" or raw == "0":
        return 0
    try:
        parsed = int(raw)
        return max(0, parsed)
    except ValueError:
        return DEFAULT_MANIFEST_CACHE_MS


def _should_use_manifest_cache() -> bool:
    if os.environ.get("OPENCLAW_DISABLE_PLUGIN_MANIFEST_CACHE", "").strip():
        return False
    return _resolve_manifest_cache_ms() > 0


def _build_cache_key(workspace_dir: str | None, plugins: NormalizedPluginsConfig) -> str:
    workspace_key = os.path.expanduser(workspace_dir) if workspace_dir else ""
    load_paths = sorted(
        os.path.expanduser(p) for p in plugins.load_paths if p.strip()
    )
    import json
    return f"{workspace_key}::{json.dumps(load_paths)}"


def _safe_stat_mtime_ms(file_path: str) -> float | None:
    try:
        return os.stat(file_path).st_mtime * 1000
    except OSError:
        return None


def _safe_realpath(root_dir: str, cache: dict[str, str]) -> str | None:
    if root_dir in cache:
        return cache[root_dir]
    try:
        resolved = os.path.realpath(root_dir)
        cache[root_dir] = resolved
        return resolved
    except OSError:
        return None


def _normalize_label(raw: str | None) -> str | None:
    if not raw:
        return None
    stripped = raw.strip()
    return stripped if stripped else None


def _build_record(
    manifest: PluginManifest,
    candidate: Any,  # PluginCandidate
    manifest_path: str,
    schema_cache_key: str | None = None,
    config_schema: dict | None = None,
) -> PluginManifestRecord:
    return PluginManifestRecord(
        id=manifest.id,
        name=_normalize_label(manifest.name) or getattr(candidate, "package_name", None),
        description=_normalize_label(manifest.description) or getattr(candidate, "package_description", None),
        version=_normalize_label(manifest.version) or getattr(candidate, "package_version", None),
        kind=manifest.kind,
        channels=manifest.channels or [],
        providers=manifest.providers or [],
        skills=manifest.skills or [],
        origin=candidate.origin,
        workspace_dir=getattr(candidate, "workspace_dir", None),
        root_dir=candidate.root_dir,
        source=candidate.source,
        manifest_path=manifest_path,
        schema_cache_key=schema_cache_key,
        config_schema=config_schema,
        config_ui_hints=manifest.ui_hints,
    )


def load_plugin_manifest_registry(
    config: Any = None,
    workspace_dir: str | None = None,
    cache: bool = True,
    candidates: list[Any] | None = None,
    diagnostics_in: list[PluginDiagnostic] | None = None,
) -> PluginManifestRegistry:
    """Load plugin manifest registry from discovered candidates.

    Mirrors loadPluginManifestRegistry() from manifest-registry.ts.
    """
    from .config_state import normalize_plugins_config

    plugins_cfg = getattr(config, "plugins", None) if config else None
    normalized = normalize_plugins_config(plugins_cfg)
    cache_key = _build_cache_key(workspace_dir, normalized)
    cache_enabled = cache and _should_use_manifest_cache()

    if cache_enabled and cache_key in _registry_cache:
        expires_at, cached_registry = _registry_cache[cache_key]
        if expires_at > time.time() * 1000:
            return cached_registry

    if candidates is not None:
        discovery_candidates = candidates
        discovery_diagnostics: list[PluginDiagnostic] = list(diagnostics_in or [])
    else:
        from .discovery import discover_openclaw_plugins
        discovery = discover_openclaw_plugins(
            workspace_dir=workspace_dir,
            extra_paths=normalized.load_paths,
        )
        discovery_candidates = discovery.candidates
        discovery_diagnostics = list(discovery.diagnostics)

    all_diagnostics: list[PluginDiagnostic] = list(discovery_diagnostics)
    records: list[PluginManifestRecord] = []
    seen_ids: dict[str, tuple[Any, int]] = {}  # id -> (candidate, record_index)
    realpath_cache: dict[str, str] = {}

    for candidate in discovery_candidates:
        manifest_res = load_plugin_manifest(candidate.root_dir)
        if not manifest_res.ok:
            all_diagnostics.append(PluginDiagnostic(
                level="error",
                message=manifest_res.error,  # type: ignore[union-attr]
                source=manifest_res.manifest_path,
            ))
            continue

        manifest = manifest_res.manifest  # type: ignore[union-attr]
        id_hint = getattr(candidate, "id_hint", None)
        if id_hint and id_hint != manifest.id:
            all_diagnostics.append(PluginDiagnostic(
                level="warn",
                plugin_id=manifest.id,
                source=candidate.source,
                message=f'plugin id mismatch (manifest uses "{manifest.id}", entry hints "{id_hint}")',
            ))

        config_schema = manifest.config_schema
        manifest_mtime = _safe_stat_mtime_ms(manifest_res.manifest_path)  # type: ignore[union-attr]
        schema_cache_key = (
            f"{manifest_res.manifest_path}:{manifest_mtime}"  # type: ignore[union-attr]
            if manifest_mtime
            else manifest_res.manifest_path  # type: ignore[union-attr]
        )

        if manifest.id in seen_ids:
            existing_candidate, existing_idx = seen_ids[manifest.id]
            existing_real = _safe_realpath(existing_candidate.root_dir, realpath_cache)
            candidate_real = _safe_realpath(candidate.root_dir, realpath_cache)
            same_plugin = bool(existing_real and candidate_real and existing_real == candidate_real)
            if same_plugin:
                if PLUGIN_ORIGIN_RANK.get(candidate.origin, 99) < PLUGIN_ORIGIN_RANK.get(existing_candidate.origin, 99):
                    records[existing_idx] = _build_record(
                        manifest, candidate, manifest_res.manifest_path, schema_cache_key, config_schema  # type: ignore[union-attr]
                    )
                    seen_ids[manifest.id] = (candidate, existing_idx)
                continue
            all_diagnostics.append(PluginDiagnostic(
                level="warn",
                plugin_id=manifest.id,
                source=candidate.source,
                message=f"duplicate plugin id detected; later plugin may be overridden ({candidate.source})",
            ))
        else:
            seen_ids[manifest.id] = (candidate, len(records))

        records.append(_build_record(
            manifest, candidate, manifest_res.manifest_path, schema_cache_key, config_schema  # type: ignore[union-attr]
        ))

    registry = PluginManifestRegistry(plugins=records, diagnostics=all_diagnostics)

    if cache_enabled:
        ttl = _resolve_manifest_cache_ms()
        if ttl > 0:
            _registry_cache[cache_key] = (time.time() * 1000 + ttl, registry)

    return registry
