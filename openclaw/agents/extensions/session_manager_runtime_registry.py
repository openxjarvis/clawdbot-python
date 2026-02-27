"""
Session Manager Runtime Registry - mirrors TypeScript session-manager-runtime-registry.ts

Provides a type-safe way to store runtime data associated with SessionManager
instances using WeakMap-like behavior (WeakKeyDictionary in Python).
"""
from __future__ import annotations

import weakref
from typing import Any, Generic, TypeVar

T = TypeVar('T')


class SessionManagerRuntimeRegistry(Generic[T]):
    """
    Runtime registry for SessionManager instances.
    
    Mirrors TypeScript SessionManagerRuntimeRegistry using WeakMap.
    Uses Python's WeakKeyDictionary for automatic garbage collection.
    
    Features:
    - Type-safe runtime value storage
    - Multiple extensions can share same SessionManager
    - Automatic cleanup when SessionManager is GC'd
    
    Example:
        registry = SessionManagerRuntimeRegistry[dict]()
        registry.set(session_manager, {"lastTouch": 123456})
        data = registry.get(session_manager)
    """
    
    def __init__(self) -> None:
        """Initialize with WeakKeyDictionary for automatic GC."""
        self._registry: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
    
    def set(self, session_manager: Any, value: T) -> None:
        """
        Store runtime value for a SessionManager.
        
        Args:
            session_manager: SessionManager instance (key)
            value: Runtime value to store
        """
        if session_manager is None:
            return
        
        self._registry[session_manager] = value
    
    def get(self, session_manager: Any) -> T | None:
        """
        Retrieve runtime value for a SessionManager.
        
        Args:
            session_manager: SessionManager instance (key)
            
        Returns:
            Stored value or None if not found
        """
        if session_manager is None:
            return None
        
        return self._registry.get(session_manager)
    
    def has(self, session_manager: Any) -> bool:
        """
        Check if SessionManager has stored value.
        
        Args:
            session_manager: SessionManager instance
            
        Returns:
            True if value exists
        """
        if session_manager is None:
            return False
        
        return session_manager in self._registry
    
    def delete(self, session_manager: Any) -> bool:
        """
        Delete stored value for SessionManager.
        
        Args:
            session_manager: SessionManager instance
            
        Returns:
            True if value was deleted, False if not found
        """
        if session_manager is None:
            return False
        
        if session_manager in self._registry:
            del self._registry[session_manager]
            return True
        
        return False
    
    def clear(self) -> None:
        """Clear all stored values."""
        self._registry.clear()


def create_session_manager_runtime_registry() -> SessionManagerRuntimeRegistry[Any]:
    """
    Create a new SessionManagerRuntimeRegistry instance.
    
    Mirrors TypeScript createSessionManagerRuntimeRegistry().
    
    Returns:
        New registry instance
    """
    return SessionManagerRuntimeRegistry[Any]()
