"""Config I/O utilities

Provides simplified access to config loading and writing functions.
Re-exports from config/loader.py for consistency with TypeScript naming.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Union

from .loader import load_config as _load_config, write_config_file as _write_config_file


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load OpenClaw configuration as dictionary.
    
    Args:
        config_path: Optional path to config file
        
    Returns:
        Configuration dictionary
    """
    return _load_config(config_path=config_path, as_dict=True)


def write_config_file(config: dict[str, Any], config_path: str | Path | None = None) -> None:
    """Write configuration to file.
    
    Args:
        config: Configuration dictionary
        config_path: Optional path to config file
    """
    _write_config_file(config, config_path=config_path)


__all__ = ["load_config", "write_config_file"]
