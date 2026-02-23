"""Unified browser automation module

Consolidates browser functionality from:
- openclaw/agents/tools/browser.py
- openclaw/agents/tools/browser_control.py

Provides:
- Browser controller (Playwright-based)
- Sandbox bridge for isolated execution
- Chrome extension relay
- Profile management
"""

from .controller import BrowserController
from .profiles import BrowserProfile

__all__ = [
    "BrowserController",
    "BrowserProfile",
    "UnifiedBrowserTool",
]


def __getattr__(name: str):
    if name == "UnifiedBrowserTool":
        from .tools.browser_tool import UnifiedBrowserTool
        return UnifiedBrowserTool
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
