"""In-memory cache of sent message IDs per chat

Used to identify bot's own messages for reaction filtering ("own" mode).
"""
from __future__ import annotations

import logging
import time
from typing import Dict, Set

logger = logging.getLogger(__name__)

TTL_MS = 24 * 60 * 60 * 1000  # 24 hours
MAX_ENTRIES_PER_CHAT = 100


class CacheEntry:
    """Cache entry for a chat's sent messages"""
    
    def __init__(self):
        self.message_ids: Set[int] = set()
        self.timestamps: Dict[int, float] = {}


class SentMessageCache:
    """In-memory cache of sent messages with TTL and LRU eviction"""
    
    def __init__(self):
        self._cache: Dict[str, CacheEntry] = {}
    
    @staticmethod
    def _get_chat_key(chat_id: int | str) -> str:
        """Get normalized chat key"""
        return str(chat_id)
    
    def _cleanup_expired(self, entry: CacheEntry) -> None:
        """Remove expired entries based on TTL"""
        now_ms = time.time() * 1000
        expired_ids = []
        
        for msg_id, timestamp in entry.timestamps.items():
            if now_ms - timestamp > TTL_MS:
                expired_ids.append(msg_id)
        
        for msg_id in expired_ids:
            entry.message_ids.discard(msg_id)
            entry.timestamps.pop(msg_id, None)
    
    def record_sent_message(self, chat_id: int | str, message_id: int) -> None:
        """Record a message ID as sent by the bot"""
        key = self._get_chat_key(chat_id)
        
        entry = self._cache.get(key)
        if not entry:
            entry = CacheEntry()
            self._cache[key] = entry
        
        entry.message_ids.add(message_id)
        entry.timestamps[message_id] = time.time() * 1000
        
        # Periodic cleanup when cache grows large
        if len(entry.message_ids) > MAX_ENTRIES_PER_CHAT:
            self._cleanup_expired(entry)
            
            # If still too large after cleanup, remove oldest entries (LRU)
            if len(entry.message_ids) > MAX_ENTRIES_PER_CHAT:
                sorted_entries = sorted(entry.timestamps.items(), key=lambda x: x[1])
                to_remove = len(entry.message_ids) - MAX_ENTRIES_PER_CHAT
                
                for msg_id, _ in sorted_entries[:to_remove]:
                    entry.message_ids.discard(msg_id)
                    entry.timestamps.pop(msg_id, None)
    
    def was_sent_by_bot(self, chat_id: int | str, message_id: int) -> bool:
        """Check if a message was sent by the bot"""
        key = self._get_chat_key(chat_id)
        entry = self._cache.get(key)
        
        if not entry:
            return False
        
        # Clean up expired entries on read
        self._cleanup_expired(entry)
        
        return message_id in entry.message_ids
    
    def clear(self) -> None:
        """Clear all cached entries (for testing)"""
        self._cache.clear()
    
    def get_stats(self) -> dict:
        """Get cache statistics"""
        total_messages = sum(len(entry.message_ids) for entry in self._cache.values())
        return {
            "chats": len(self._cache),
            "total_messages": total_messages,
        }


# Global instance
_sent_message_cache = SentMessageCache()


def record_sent_message(chat_id: int | str, message_id: int) -> None:
    """Record a message ID as sent by the bot"""
    _sent_message_cache.record_sent_message(chat_id, message_id)


def was_sent_by_bot(chat_id: int | str, message_id: int) -> bool:
    """Check if a message was sent by the bot"""
    return _sent_message_cache.was_sent_by_bot(chat_id, message_id)


def clear_sent_message_cache() -> None:
    """Clear all cached entries (for testing)"""
    _sent_message_cache.clear()


def get_sent_message_cache_stats() -> dict:
    """Get cache statistics"""
    return _sent_message_cache.get_stats()
