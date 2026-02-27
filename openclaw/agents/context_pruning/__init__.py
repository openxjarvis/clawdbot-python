"""
Context pruning module for OpenClaw Python.

Aligned with TypeScript openclaw/src/agents/pi-extensions/context-pruning/
"""
from .pruner import prune_context_messages, soft_trim_tool_result_message
from .cache_ttl import is_cache_ttl_eligible_provider, read_last_cache_ttl_timestamp

__all__ = [
    "prune_context_messages",
    "soft_trim_tool_result_message",
    "is_cache_ttl_eligible_provider",
    "read_last_cache_ttl_timestamp",
]
