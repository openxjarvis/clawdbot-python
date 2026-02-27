"""
Duration parsing utilities - mirrors TypeScript cli/parse-duration.ts

Provides functions to parse human-readable duration strings into milliseconds.
"""
from __future__ import annotations

import re


def parse_duration_ms(duration_str: str, default_unit: str = "m") -> int:
    """
    Parse a duration string into milliseconds.
    
    Mirrors TypeScript parseDurationMs() from cli/parse-duration.ts.
    
    Supported formats:
    - "5m" → 5 minutes = 300,000 ms
    - "1h" → 1 hour = 3,600,000 ms
    - "30s" → 30 seconds = 30,000 ms
    - "2d" → 2 days = 172,800,000 ms
    - "100" → 100 minutes (uses default_unit)
    
    Args:
        duration_str: Duration string to parse
        default_unit: Default unit if not specified ("s", "m", "h", "d")
        
    Returns:
        Duration in milliseconds
        
    Raises:
        ValueError: If duration format is invalid
        
    Examples:
        >>> parse_duration_ms("5m")
        300000
        >>> parse_duration_ms("1h")
        3600000
        >>> parse_duration_ms("30s")
        30000
        >>> parse_duration_ms("100", default_unit="s")
        100000
    """
    if not duration_str or not isinstance(duration_str, str):
        raise ValueError(f"Invalid duration: {duration_str}")
    
    duration_str = duration_str.strip()
    if not duration_str:
        raise ValueError("Duration string is empty")
    
    # Parse: number + optional unit (s, m, h, d)
    match = re.match(r'^(\d+)([smhd])?$', duration_str, re.IGNORECASE)
    if not match:
        raise ValueError(f"Invalid duration format: {duration_str}")
    
    value = int(match.group(1))
    unit = (match.group(2) or default_unit).lower()
    
    if unit not in ('s', 'm', 'h', 'd'):
        raise ValueError(f"Invalid duration unit: {unit}")
    
    multipliers = {
        's': 1000,              # seconds
        'm': 60 * 1000,         # minutes
        'h': 60 * 60 * 1000,    # hours
        'd': 24 * 60 * 60 * 1000,  # days
    }
    
    return value * multipliers[unit]


def format_duration_ms(ms: int) -> str:
    """
    Format milliseconds into a human-readable duration string.
    
    Args:
        ms: Duration in milliseconds
        
    Returns:
        Formatted duration string (e.g., "5m", "1h 30m")
        
    Examples:
        >>> format_duration_ms(300000)
        '5m'
        >>> format_duration_ms(5400000)
        '1h 30m'
    """
    if ms < 0:
        return "0s"
    
    seconds = ms // 1000
    
    if seconds < 60:
        return f"{seconds}s"
    
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    
    hours = minutes // 60
    remaining_minutes = minutes % 60
    
    if hours < 24:
        if remaining_minutes > 0:
            return f"{hours}h {remaining_minutes}m"
        return f"{hours}h"
    
    days = hours // 24
    remaining_hours = hours % 24
    
    if remaining_hours > 0:
        return f"{days}d {remaining_hours}h"
    return f"{days}d"
