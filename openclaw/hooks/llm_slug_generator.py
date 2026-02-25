"""LLM slug generator for session memory hook.

Generates descriptive filename slugs from conversation content using LLM.

Aligned with TypeScript openclaw/src/hooks/llm-slug-generator.ts
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


async def generate_slug_via_llm(
    session_content: str,
    cfg: dict[str, Any],
    max_length: int = 40
) -> str | None:
    """Generate a descriptive slug from session content using LLM.
    
    Args:
        session_content: Recent conversation content
        cfg: OpenClaw configuration
        max_length: Maximum slug length
    
    Returns:
        Generated slug or None if generation fails
    """
    try:
        # Build prompt for slug generation
        prompt = f"""Based on this conversation, generate a short descriptive slug (2-4 words, kebab-case) suitable for a filename:

{session_content[:1000]}

Requirements:
- Use kebab-case (lowercase with hyphens)
- 2-4 words maximum
- Descriptive of the main topic
- No special characters except hyphens
- Examples: "vendor-pitch", "api-design", "bug-fix"

Respond with just the slug, nothing else."""
        
        # Try to use the configured LLM provider
        # This is a simplified version - in production, use the full agent runner
        try:
            # Attempt to use OpenAI/Anthropic via environment or config
            model_key = cfg.get("agents", {}).get("defaults", {}).get("models", {}).get("primary")
            if not model_key:
                # Try common env vars
                import os
                if os.getenv("ANTHROPIC_API_KEY"):
                    # Use Anthropic
                    import anthropic
                    client = anthropic.Anthropic()
                    response = client.messages.create(
                        model="claude-3-haiku-20240307",
                        max_tokens=50,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    slug_text = response.content[0].text.strip()
                elif os.getenv("OPENAI_API_KEY"):
                    # Use OpenAI
                    import openai
                    client = openai.OpenAI()
                    response = client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        max_tokens=50,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    slug_text = response.choices[0].message.content.strip()
                else:
                    logger.debug("No LLM API key available for slug generation")
                    return None
            else:
                # Use configured model (would require full agent runner integration)
                logger.debug("Using configured model for slug generation (simplified)")
                return None
            
            # Clean and validate slug
            slug = clean_slug(slug_text, max_length)
            return slug if slug else None
            
        except ImportError as err:
            logger.debug(f"LLM library not available: {err}")
            return None
        except Exception as err:
            logger.debug(f"LLM slug generation failed: {err}")
            return None
            
    except Exception as err:
        logger.error(f"Slug generation error: {err}")
        return None


def clean_slug(text: str, max_length: int = 40) -> str | None:
    """Clean and validate a slug.
    
    Args:
        text: Raw slug text
        max_length: Maximum slug length
    
    Returns:
        Cleaned slug or None if invalid
    """
    # Remove quotes, newlines, etc.
    text = text.strip().strip('"').strip("'").strip()
    
    # Convert to lowercase
    text = text.lower()
    
    # Replace spaces and underscores with hyphens
    text = re.sub(r'[\s_]+', '-', text)
    
    # Remove any characters that aren't alphanumeric or hyphens
    text = re.sub(r'[^a-z0-9-]+', '', text)
    
    # Remove multiple consecutive hyphens
    text = re.sub(r'-+', '-', text)
    
    # Remove leading/trailing hyphens
    text = text.strip('-')
    
    # Truncate to max length
    if len(text) > max_length:
        text = text[:max_length].rstrip('-')
    
    # Validate: must be 2+ characters, contain at least one letter
    if len(text) < 2 or not re.search(r'[a-z]', text):
        return None
    
    return text
