"""
Cache TTL utilities for context pruning - mirrors TypeScript cache-ttl.ts

Provides functions to check cache eligibility and read cache touch timestamps.
"""
from __future__ import annotations

from typing import Any


def is_cache_ttl_eligible_provider(provider: str) -> bool:
    """
    Check if a provider supports prompt caching.
    
    Mirrors TypeScript isCacheTtlEligibleProvider().
    
    Args:
        provider: Model provider name
        
    Returns:
        True if provider supports caching
    """
    if not provider or not isinstance(provider, str):
        return False
    
    provider_lower = provider.lower()
    
    # Anthropic and Google/Gemini support prompt caching
    return provider_lower in ("anthropic", "google", "gemini")


def read_last_cache_ttl_timestamp(session_manager: Any) -> int | None:
    """
    Read the last cache touch timestamp from SessionManager.
    
    Mirrors TypeScript readLastCacheTtlTimestamp().
    
    Args:
        session_manager: SessionManager instance
        
    Returns:
        Last cache touch timestamp (Unix ms) or None
    """
    if not session_manager:
        return None
    
    try:
        # Try to get entries from SessionManager
        if hasattr(session_manager, 'get_entries'):
            entries = session_manager.get_entries()
            if not entries:
                return None
            
            # Look for lastCacheTouchAt in entries
            for entry in entries:
                if isinstance(entry, dict):
                    timestamp = entry.get('lastCacheTouchAt')
                    if isinstance(timestamp, (int, float)) and timestamp > 0:
                        return int(timestamp)
                elif hasattr(entry, 'lastCacheTouchAt'):
                    timestamp = entry.lastCacheTouchAt
                    if isinstance(timestamp, (int, float)) and timestamp > 0:
                        return int(timestamp)
        
        # Try alternative accessor
        if hasattr(session_manager, 'store'):
            store = session_manager.store
            if isinstance(store, dict):
                # Find any entry with lastCacheTouchAt
                for entry in store.values():
                    if isinstance(entry, dict):
                        timestamp = entry.get('lastCacheTouchAt')
                        if isinstance(timestamp, (int, float)) and timestamp > 0:
                            return int(timestamp)
                    elif hasattr(entry, 'lastCacheTouchAt'):
                        timestamp = entry.lastCacheTouchAt
                        if isinstance(timestamp, (int, float)) and timestamp > 0:
                            return int(timestamp)
    
    except Exception:
        pass
    
    return None
