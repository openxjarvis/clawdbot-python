"""Telegram sticker cache system with search and vision integration"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from openclaw.config.paths import STATE_DIR

logger = logging.getLogger(__name__)

CACHE_FILE = Path(STATE_DIR) / "telegram" / "sticker-cache.json"
CACHE_VERSION = 1

STICKER_DESCRIPTION_PROMPT = (
    "Describe this sticker image in 1-2 sentences. "
    "Focus on what the sticker depicts (character, object, action, emotion). "
    "Be concise and objective."
)


@dataclass
class CachedSticker:
    """Cached sticker metadata"""
    file_id: str
    file_unique_id: str
    emoji: str | None
    set_name: str | None
    description: str
    cached_at: str
    received_from: str | None = None


@dataclass
class StickerCache:
    """Sticker cache structure"""
    version: int
    stickers: dict[str, CachedSticker]


def load_cache() -> StickerCache:
    """Load sticker cache from disk"""
    try:
        if not CACHE_FILE.exists():
            return StickerCache(version=CACHE_VERSION, stickers={})
        
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if not isinstance(data, dict):
            return StickerCache(version=CACHE_VERSION, stickers={})
        
        version = data.get("version", 0)
        if version != CACHE_VERSION:
            logger.info("Sticker cache version mismatch, starting fresh")
            return StickerCache(version=CACHE_VERSION, stickers={})
        
        # Convert dict entries back to CachedSticker objects
        stickers = {}
        for unique_id, sticker_data in data.get("stickers", {}).items():
            stickers[unique_id] = CachedSticker(**sticker_data)
        
        return StickerCache(version=CACHE_VERSION, stickers=stickers)
    
    except Exception as exc:
        logger.warning("Failed to load sticker cache: %s", exc)
        return StickerCache(version=CACHE_VERSION, stickers={})


def save_cache(cache: StickerCache) -> None:
    """Save sticker cache to disk"""
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to JSON-serializable format
        data = {
            "version": cache.version,
            "stickers": {
                unique_id: asdict(sticker)
                for unique_id, sticker in cache.stickers.items()
            },
        }
        
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    except Exception as exc:
        logger.error("Failed to save sticker cache: %s", exc)


def get_cached_sticker(file_unique_id: str) -> CachedSticker | None:
    """Get a cached sticker by its unique ID"""
    cache = load_cache()
    return cache.stickers.get(file_unique_id)


def cache_sticker(sticker: CachedSticker) -> None:
    """Add or update a sticker in the cache"""
    cache = load_cache()
    cache.stickers[sticker.file_unique_id] = sticker
    save_cache(cache)


def search_stickers(query: str, limit: int = 10) -> list[CachedSticker]:
    """
    Search cached stickers by text query.
    
    Fuzzy match on description + emoji + setName.
    Returns top results sorted by relevance score.
    """
    cache = load_cache()
    query_lower = query.lower()
    results: list[tuple[CachedSticker, int]] = []
    
    for sticker in cache.stickers.values():
        score = 0
        desc_lower = sticker.description.lower()
        
        # Exact substring match in description
        if query_lower in desc_lower:
            score += 10
        
        # Word-level matching
        query_words = [w for w in query_lower.split() if w]
        desc_words = desc_lower.split()
        for q_word in query_words:
            if any(q_word in d_word for d_word in desc_words):
                score += 5
        
        # Emoji match
        if sticker.emoji and sticker.emoji in query:
            score += 8
        
        # Set name match
        if sticker.set_name and query_lower in sticker.set_name.lower():
            score += 3
        
        if score > 0:
            results.append((sticker, score))
    
    # Sort by score descending
    results.sort(key=lambda x: x[1], reverse=True)
    
    return [sticker for sticker, _ in results[:limit]]


def get_all_cached_stickers() -> list[CachedSticker]:
    """Get all cached stickers (for debugging/listing)"""
    cache = load_cache()
    return list(cache.stickers.values())


def get_cache_stats() -> dict[str, Any]:
    """Get cache statistics"""
    cache = load_cache()
    stickers = list(cache.stickers.values())
    
    if not stickers:
        return {"count": 0}
    
    sorted_stickers = sorted(stickers, key=lambda s: s.cached_at)
    
    return {
        "count": len(stickers),
        "oldest_at": sorted_stickers[0].cached_at if sorted_stickers else None,
        "newest_at": sorted_stickers[-1].cached_at if sorted_stickers else None,
    }


async def describe_sticker_image(
    image_path: str | Path,
    config: Any,
    agent_id: str | None = None,
) -> str | None:
    """
    Describe a sticker image using vision API.
    
    Auto-detects an available vision provider based on configured API keys.
    Returns None if no vision provider is available.
    """
    from openclaw.media_understanding.runner import MediaUnderstandingRunner
    from openclaw.media_understanding.types import MediaType, Provider
    
    # Build config for media understanding
    media_config = {}
    if hasattr(config, "google_api_key"):
        media_config["google_api_key"] = config.google_api_key
    elif hasattr(config, "model") and hasattr(config.model, "google_api_key"):
        media_config["google_api_key"] = config.model.google_api_key
    
    if hasattr(config, "anthropic_api_key"):
        media_config["anthropic_api_key"] = config.anthropic_api_key
    elif hasattr(config, "model") and hasattr(config.model, "anthropic_api_key"):
        media_config["anthropic_api_key"] = config.model.anthropic_api_key
    
    if hasattr(config, "openai_api_key"):
        media_config["openai_api_key"] = config.openai_api_key
    elif hasattr(config, "model") and hasattr(config.model, "openai_api_key"):
        media_config["openai_api_key"] = config.model.openai_api_key
    
    runner = MediaUnderstandingRunner(config=media_config)
    
    try:
        result = await runner.analyze(
            path=image_path,
            media_type=MediaType.IMAGE,
            prompt=STICKER_DESCRIPTION_PROMPT,
            max_tokens=150,
        )
        
        if result.success and result.text:
            logger.info("Sticker described successfully")
            return result.text
        else:
            logger.warning("Failed to describe sticker: %s", result.error)
            return None
    
    except Exception as exc:
        logger.warning("Failed to describe sticker: %s", exc)
        return None
