"""Bundled hook handlers.

These hooks ship with OpenClaw and are automatically discovered.
"""

from __future__ import annotations

from pathlib import Path


def get_bundled_hooks_dir() -> Path:
    """Get the directory containing bundled hooks.
    
    Returns:
        Path to bundled hooks directory
    """
    return Path(__file__).parent


__all__ = [
    "get_bundled_hooks_dir",
]
