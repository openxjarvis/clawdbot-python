"""Hooks CLI commands

Port of TypeScript openclaw/src/cli/hooks-cli.ts

Provides CLI commands for managing internal agent hooks:
- list: List all hooks
- info: Show detailed information about a hook
- check: Check hooks eligibility status
- enable: Enable a hook
- disable: Disable a hook
"""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def format_hook_status(hook: dict[str, Any]) -> str:
    """Format hook status with emoji indicator."""
    if hook.get("eligible"):
        return "✓ ready"
    if hook.get("disabled"):
        return "⏸ disabled"
    return "✗ missing"


def format_hook_name(hook: dict[str, Any]) -> str:
    """Format hook name with emoji."""
    emoji = hook.get("emoji", "🔗")
    name = hook.get("name", "unknown")
    return f"{emoji} {name}"


def format_hook_source(hook: dict[str, Any]) -> str:
    """Format hook source string."""
    if hook.get("managedByPlugin"):
        plugin_id = hook.get("pluginId", "unknown")
        return f"plugin:{plugin_id}"
    return hook.get("source", "unknown")


def format_hook_missing_summary(hook: dict[str, Any]) -> str:
    """Format missing requirements summary."""
    missing = hook.get("missing", {})
    parts = []
    
    if missing.get("bins"):
        parts.append(f"bins: {', '.join(missing['bins'])}")
    if missing.get("anyBins"):
        parts.append(f"anyBins: {', '.join(missing['anyBins'])}")
    if missing.get("env"):
        parts.append(f"env: {', '.join(missing['env'])}")
    if missing.get("config"):
        parts.append(f"config: {', '.join(missing['config'])}")
    if missing.get("os"):
        parts.append(f"os: {', '.join(missing['os'])}")
    
    return "; ".join(parts)


def format_hooks_list(report: dict[str, Any], json_output: bool = False, eligible_only: bool = False, verbose: bool = False) -> str:
    """Format the hooks list output."""
    hooks = report.get("hooks", [])
    
    if eligible_only:
        hooks = [h for h in hooks if h.get("eligible")]
    
    if json_output:
        json_report = {
            "workspaceDir": report.get("workspaceDir"),
            "managedHooksDir": report.get("managedHooksDir"),
            "hooks": [
                {
                    "name": h.get("name"),
                    "description": h.get("description"),
                    "emoji": h.get("emoji"),
                    "eligible": h.get("eligible"),
                    "disabled": h.get("disabled"),
                    "source": h.get("source"),
                    "pluginId": h.get("pluginId"),
                    "events": h.get("events", []),
                    "homepage": h.get("homepage"),
                    "missing": h.get("missing", {}),
                    "managedByPlugin": h.get("managedByPlugin", False),
                }
                for h in hooks
            ],
        }
        return json.dumps(json_report, indent=2)
    
    if not hooks:
        if eligible_only:
            return "No eligible hooks found. Run `openclaw hooks list` to see all hooks."
        return "No hooks found."
    
    eligible_count = len([h for h in hooks if h.get("eligible")])
    lines = [f"Hooks ({eligible_count}/{len(hooks)} ready)\n"]
    
    for hook in hooks:
        status = format_hook_status(hook)
        name = format_hook_name(hook)
        desc = hook.get("description", "")
        source = format_hook_source(hook)
        
        lines.append(f"{status}  {name}")
        lines.append(f"   Description: {desc}")
        lines.append(f"   Source: {source}")
        
        if verbose:
            missing = format_hook_missing_summary(hook)
            if missing:
                lines.append(f"   Missing: {missing}")
        
        lines.append("")
    
    return "\n".join(lines)


def format_hook_info(report: dict[str, Any], hook_name: str, json_output: bool = False) -> str:
    """Format detailed info for a single hook."""
    hooks = report.get("hooks", [])
    hook = None
    
    for h in hooks:
        if h.get("name") == hook_name or h.get("hookKey") == hook_name:
            hook = h
            break
    
    if not hook:
        if json_output:
            return json.dumps({"error": "not found", "hook": hook_name}, indent=2)
        return f'Hook "{hook_name}" not found. Run `openclaw hooks list` to see available hooks.'
    
    if json_output:
        return json.dumps(hook, indent=2)
    
    emoji = hook.get("emoji", "🔗")
    name = hook.get("name", "unknown")
    eligible = hook.get("eligible", False)
    disabled = hook.get("disabled", False)
    
    if eligible:
        status = "✓ Ready"
    elif disabled:
        status = "⏸ Disabled"
    else:
        status = "✗ Missing requirements"
    
    lines = [
        f"{emoji} {name} {status}",
        "",
        hook.get("description", ""),
        "",
        "Details:",
    ]
    
    if hook.get("managedByPlugin"):
        plugin_id = hook.get("pluginId", "unknown")
        source = hook.get("source", "unknown")
        lines.append(f"  Source: {source} ({plugin_id})")
    else:
        lines.append(f"  Source: {hook.get('source', 'unknown')}")
    
    lines.append(f"  Path: {hook.get('filePath', 'unknown')}")
    lines.append(f"  Handler: {hook.get('handlerPath', 'unknown')}")
    
    if hook.get("homepage"):
        lines.append(f"  Homepage: {hook['homepage']}")
    
    events = hook.get("events", [])
    if events:
        lines.append(f"  Events: {', '.join(events)}")
    
    if hook.get("managedByPlugin"):
        lines.append("  Managed by plugin; enable/disable via hooks CLI not available.")
    
    requirements = hook.get("requirements", {})
    has_requirements = any([
        requirements.get("bins"),
        requirements.get("anyBins"),
        requirements.get("env"),
        requirements.get("config"),
        requirements.get("os"),
    ])
    
    if has_requirements:
        lines.extend(["", "Requirements:"])
        missing = hook.get("missing", {})
        
        if requirements.get("bins"):
            bins_status = []
            for bin_name in requirements["bins"]:
                if bin_name in missing.get("bins", []):
                    bins_status.append(f"✗ {bin_name}")
                else:
                    bins_status.append(f"✓ {bin_name}")
            lines.append(f"  Binaries: {', '.join(bins_status)}")
        
        if requirements.get("anyBins"):
            if missing.get("anyBins"):
                any_bins_str = f"✗ (any of: {', '.join(requirements['anyBins'])})"
            else:
                any_bins_str = f"✓ (any of: {', '.join(requirements['anyBins'])})"
            lines.append(f"  Any binary: {any_bins_str}")
        
        if requirements.get("env"):
            env_status = []
            for env_var in requirements["env"]:
                if env_var in missing.get("env", []):
                    env_status.append(f"✗ {env_var}")
                else:
                    env_status.append(f"✓ {env_var}")
            lines.append(f"  Environment: {', '.join(env_status)}")
        
        if requirements.get("config"):
            config_checks = hook.get("configChecks", [])
            config_status = []
            for check in config_checks:
                if check.get("satisfied"):
                    config_status.append(f"✓ {check['path']}")
                else:
                    config_status.append(f"✗ {check['path']}")
            if config_status:
                lines.append(f"  Config: {', '.join(config_status)}")
        
        if requirements.get("os"):
            if missing.get("os"):
                os_str = f"✗ ({', '.join(requirements['os'])})"
            else:
                os_str = f"✓ ({', '.join(requirements['os'])})"
            lines.append(f"  OS: {os_str}")
    
    return "\n".join(lines)


def format_hooks_check(report: dict[str, Any], json_output: bool = False) -> str:
    """Format check output."""
    hooks = report.get("hooks", [])
    eligible = [h for h in hooks if h.get("eligible")]
    not_eligible = [h for h in hooks if not h.get("eligible")]
    
    if json_output:
        return json.dumps(
            {
                "total": len(hooks),
                "eligible": len(eligible),
                "notEligible": len(not_eligible),
                "hooks": {
                    "eligible": [h.get("name") for h in eligible],
                    "notEligible": [
                        {
                            "name": h.get("name"),
                            "missing": h.get("missing", {}),
                        }
                        for h in not_eligible
                    ],
                },
            },
            indent=2,
        )
    
    lines = [
        "Hooks Status",
        "",
        f"Total hooks: {len(hooks)}",
        f"Ready: {len(eligible)}",
        f"Not ready: {len(not_eligible)}",
    ]
    
    if not_eligible:
        lines.extend(["", "Hooks not ready:"])
        for hook in not_eligible:
            reasons = []
            if hook.get("disabled"):
                reasons.append("disabled")
            
            missing = hook.get("missing", {})
            if missing.get("bins"):
                reasons.append(f"bins: {', '.join(missing['bins'])}")
            if missing.get("anyBins"):
                reasons.append(f"anyBins: {', '.join(missing['anyBins'])}")
            if missing.get("env"):
                reasons.append(f"env: {', '.join(missing['env'])}")
            if missing.get("config"):
                reasons.append(f"config: {', '.join(missing['config'])}")
            if missing.get("os"):
                reasons.append(f"os: {', '.join(missing['os'])}")
            
            emoji = hook.get("emoji", "🔗")
            name = hook.get("name", "unknown")
            lines.append(f"  {emoji} {name} - {'; '.join(reasons)}")
    
    return "\n".join(lines)


def build_hooks_report(config: dict[str, Any]) -> dict[str, Any]:
    """Build hooks status report."""
    from openclaw.agents.agent_scope import resolve_agent_workspace_dir, resolve_default_agent_id
    from openclaw.hooks.workspace import load_workspace_hook_entries
    from openclaw.hooks.hooks_status import build_workspace_hook_status
    
    agent_id = resolve_default_agent_id(config)
    workspace_dir = resolve_agent_workspace_dir(config, agent_id)
    
    entries = load_workspace_hook_entries(workspace_dir, config=config)
    
    return build_workspace_hook_status(workspace_dir, config=config, entries=entries)


def resolve_hook_for_toggle(
    report: dict[str, Any],
    hook_name: str,
    require_eligible: bool = False,
) -> dict[str, Any]:
    """Resolve hook for enable/disable operations."""
    hooks = report.get("hooks", [])
    hook = None
    
    for h in hooks:
        if h.get("name") == hook_name:
            hook = h
            break
    
    if not hook:
        raise ValueError(f'Hook "{hook_name}" not found')
    
    if hook.get("managedByPlugin"):
        plugin_id = hook.get("pluginId", "unknown")
        raise ValueError(
            f'Hook "{hook_name}" is managed by plugin "{plugin_id}" and cannot be enabled/disabled.'
        )
    
    if require_eligible and not hook.get("eligible"):
        raise ValueError(f'Hook "{hook_name}" is not eligible (missing requirements)')
    
    return hook


def build_config_with_hook_enabled(
    config: dict[str, Any],
    hook_name: str,
    enabled: bool,
    ensure_hooks_enabled: bool = False,
) -> dict[str, Any]:
    """Build updated config with hook enabled/disabled."""
    hooks_config = config.get("hooks", {})
    internal_config = hooks_config.get("internal", {})
    entries = dict(internal_config.get("entries", {}))
    
    entries[hook_name] = {**entries.get(hook_name, {}), "enabled": enabled}
    
    internal_config = {
        **internal_config,
        "entries": entries,
    }
    
    if ensure_hooks_enabled:
        internal_config["enabled"] = True
    
    return {
        **config,
        "hooks": {
            **hooks_config,
            "internal": internal_config,
        },
    }


def enable_hook(hook_name: str) -> str:
    """Enable a hook."""
    from openclaw.config.io import load_config, write_config_file
    
    config = load_config()
    report = build_hooks_report(config)
    hook = resolve_hook_for_toggle(report, hook_name, require_eligible=True)
    
    next_config = build_config_with_hook_enabled(
        config,
        hook_name,
        enabled=True,
        ensure_hooks_enabled=True,
    )
    
    write_config_file(next_config)
    
    emoji = hook.get("emoji", "🔗")
    return f"✓ Enabled hook: {emoji} {hook_name}"


def disable_hook(hook_name: str) -> str:
    """Disable a hook."""
    from openclaw.config.io import load_config, write_config_file
    
    config = load_config()
    report = build_hooks_report(config)
    hook = resolve_hook_for_toggle(report, hook_name)
    
    next_config = build_config_with_hook_enabled(config, hook_name, enabled=False)
    
    write_config_file(next_config)
    
    emoji = hook.get("emoji", "🔗")
    return f"⏸ Disabled hook: {emoji} {hook_name}"
