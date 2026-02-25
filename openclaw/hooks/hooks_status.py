"""Hook status and eligibility reporting.

Aligned with TypeScript openclaw/src/hooks/hooks-status.ts
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .config import should_include_hook
from .types import HookEntry


@dataclass
class HookMissingRequirements:
    """Missing requirements for a hook."""
    
    bins: list[str] = field(default_factory=list)
    any_bins: list[str] = field(default_factory=list)
    env: list[str] = field(default_factory=list)
    config: list[str] = field(default_factory=list)
    os: list[str] = field(default_factory=list)


@dataclass
class HookStatusEntry:
    """Status information for a hook."""
    
    name: str
    source: str
    emoji: str | None = None
    events: list[str] = field(default_factory=list)
    eligible: bool = False
    disabled: bool = False
    managed_by_plugin: bool = False
    plugin_id: str | None = None
    missing: HookMissingRequirements = field(default_factory=HookMissingRequirements)


@dataclass
class HookStatusReport:
    """Complete hook status report."""
    
    hooks: list[HookStatusEntry] = field(default_factory=list)
    eligible_count: int = 0
    total_count: int = 0


def build_workspace_hook_status(
    workspace_dir: str,
    config: dict[str, Any] | None = None,
    entries: list[HookEntry] | None = None
) -> HookStatusReport:
    """Build a status report for hooks.
    
    Args:
        workspace_dir: Workspace directory
        config: OpenClaw configuration
        entries: Hook entries to report on
    
    Returns:
        Hook status report
    """
    if entries is None:
        # Load entries if not provided
        from .workspace import load_workspace_hook_entries
        entries = load_workspace_hook_entries(workspace_dir, config=config)
    
    report = HookStatusReport()
    report.total_count = len(entries)
    
    for entry in entries:
        # Check eligibility
        eligible = should_include_hook(entry, config)
        
        # Build status entry
        status = HookStatusEntry(
            name=entry.hook.name,
            source=entry.hook.source,
            emoji=entry.metadata.emoji if entry.metadata else None,
            events=entry.metadata.events if entry.metadata else [],
            eligible=eligible,
            disabled=False,  # Simplified - would check config
            managed_by_plugin=entry.hook.source == "openclaw-plugin",
            plugin_id=entry.hook.plugin_id if entry.hook.source == "openclaw-plugin" else None,
            missing=HookMissingRequirements(),  # Simplified - would check actual requirements
        )
        
        if eligible:
            report.eligible_count += 1
        
        report.hooks.append(status)
    
    return report
