"""Hooks system for event-driven extensibility.

Aligned with TypeScript src/hooks/types.ts and src/hooks/internal-hooks.ts
"""

from __future__ import annotations

from .types import (
    Hook,
    HookEntry,
    HookSource,
    HookSnapshot,
    OpenClawHookMetadata,
    HookInstallSpec,
    HookInvocationPolicy,
)
from .loader import load_hooks_from_dir
from .workspace import load_workspace_hook_entries, build_workspace_hook_snapshot
from .registry import HookRegistry, get_hook_registry
from .internal_hooks import (
    InternalHookEvent,
    InternalHookEventType,
    InternalHookHandler,
    AgentBootstrapHookContext,
    AgentBootstrapHookEvent,
    MessageReceivedHookContext,
    MessageReceivedHookEvent,
    MessageSentHookContext,
    MessageSentHookEvent,
    register_internal_hook,
    unregister_internal_hook,
    clear_internal_hooks,
    get_registered_event_keys,
    trigger_internal_hook,
    create_internal_hook_event,
    is_agent_bootstrap_event,
    is_message_received_event,
    is_message_sent_event,
)

# Convenience alias for backward compatibility
trigger_hook = trigger_internal_hook
create_hook_event = create_internal_hook_event

__all__ = [
    # Types
    "Hook",
    "HookEntry",
    "HookSource",
    "HookSnapshot",
    "OpenClawHookMetadata",
    "HookInstallSpec",
    "HookInvocationPolicy",
    # Discovery and loading
    "load_hooks_from_dir",
    "load_workspace_hook_entries",
    "build_workspace_hook_snapshot",
    # Registry (old style)
    "HookRegistry",
    "get_hook_registry",
    # Internal hooks system
    "InternalHookEvent",
    "InternalHookEventType",
    "InternalHookHandler",
    "AgentBootstrapHookContext",
    "AgentBootstrapHookEvent",
    "MessageReceivedHookContext",
    "MessageReceivedHookEvent",
    "MessageSentHookContext",
    "MessageSentHookEvent",
    "register_internal_hook",
    "unregister_internal_hook",
    "clear_internal_hooks",
    "get_registered_event_keys",
    "trigger_internal_hook",
    "create_internal_hook_event",
    "is_agent_bootstrap_event",
    "is_message_received_event",
    "is_message_sent_event",
    # Convenience aliases
    "trigger_hook",
    "create_hook_event",
]
