"""
Command lanes definitions matching TypeScript openclaw/src/process/lanes.ts
"""
from __future__ import annotations

from enum import Enum


class CommandLane(str, Enum):
    """
    Fixed command lanes for different execution contexts
    
    Aligned with TS: openclaw/src/process/lanes.ts
    """
    MAIN = "main"
    CRON = "cron"
    SUBAGENT = "subagent"
    NESTED = "nested"


# Default concurrency limits per lane (aligned with TS)
# TS references:
# - DEFAULT_AGENT_MAX_CONCURRENT = 4 (for Main)
# - DEFAULT_SUBAGENT_MAX_CONCURRENT = 8 (for Subagent)
LANE_DEFAULTS: dict[CommandLane, int] = {
    CommandLane.MAIN: 4,
    CommandLane.CRON: 1,
    CommandLane.SUBAGENT: 8,
    CommandLane.NESTED: 1,
}
