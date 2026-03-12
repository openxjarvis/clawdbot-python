---
summary: "Plugin manifest + JSON schema requirements (strict config validation)"
read_when:
  - You are building an OpenClaw Python plugin
  - You need to ship a plugin config schema or debug plugin validation errors
title: "Plugin Manifest"
---

# Plugin manifest (openclaw.plugin.json)

Every plugin **must** ship an `openclaw.plugin.json` file in the **plugin root**.
OpenClaw uses this manifest to validate configuration **without executing plugin
code**. Missing or invalid manifests are treated as plugin errors and block
config validation.

See the full plugin system guide: [Plugins](../tools/plugin.md).

## Required fields

```json
{
  "id": "voice-call",
  "configSchema": {
    "type": "object",
    "additionalProperties": false,
    "properties": {}
  }
}
```

Required keys:

- `id` (string): canonical plugin id.
- `configSchema` (object): JSON Schema for plugin config (inline).

Optional keys:

- `kind` (string): plugin kind (example: `"memory"`).
- `channels` (array): channel ids registered by this plugin (example: `["matrix"]`).
- `providers` (array): provider ids registered by this plugin.
- `skills` (array): skill directories to load (relative to the plugin root).
- `name` (string): display name for the plugin.
- `description` (string): short plugin summary.
- `uiHints` (object): config field labels/placeholders/sensitive flags for UI rendering.
- `version` (string): plugin version (informational).

## JSON Schema requirements

- **Every plugin must ship a JSON Schema**, even if it accepts no config.
- An empty schema is acceptable (for example, `{ "type": "object", "additionalProperties": false }`).
- Schemas are validated at config read/write time, not at runtime.

## Validation behavior

- Unknown `channels.*` keys are **errors**, unless the channel id is declared by
  a plugin manifest.
- `plugins.entries.<id>`, `plugins.allow`, `plugins.deny`, and `plugins.slots.*`
  must reference **discoverable** plugin ids. Unknown ids are **errors**.
- If a plugin is installed but has a broken or missing manifest or schema,
  validation fails and Doctor reports the plugin error.
- If plugin config exists but the plugin is **disabled**, the config is kept and
  a **warning** is surfaced in Doctor + logs.

## Python plugin module format

In Python, a plugin module (`plugin.py`) must export a `plugin` dict or a
module-level `register()` function. The recommended form matches the TypeScript
object export pattern:

```python
from openclaw.plugin_sdk import empty_plugin_config_schema

def register(api) -> None:
    # register tools, channels, hooks, etc.
    pass

plugin = {
    "id": "my-plugin",
    "name": "My Plugin",
    "description": "What this plugin does.",
    "config_schema": empty_plugin_config_schema(),
    "register": register,
}
```

The loader checks for a module-level `plugin` attribute first, then falls back
to a bare `register()` function for backward compatibility.

## Notes

- The manifest is **required for all plugins**, including local filesystem loads.
- Runtime still loads the plugin module separately; the manifest is only for
  discovery + validation.
- A `plugin.json` fallback is supported for backward compatibility but
  `openclaw.plugin.json` is the canonical name.
- If your plugin requires additional Python packages, list them in the manifest's
  `requires` field (informational only — not auto-installed).
