"""Onboarding finalization - TUI/UI launch"""
from __future__ import annotations

import asyncio
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


async def launch_tui(gateway_url: str = "ws://localhost:18789") -> None:
    """Launch TUI application"""
    print("\n🚀 Launching Terminal UI...")

    try:
        from openclaw.tui import run_tui, TUIOptions
        from urllib.parse import urlparse

        parsed = urlparse(gateway_url)
        port = parsed.port or 18789
        options = TUIOptions(gateway_port=port)
        await run_tui(options)
    except Exception as e:
        logger.error(f"Failed to launch TUI: {e}")
        print(f"  ❌ Failed to launch TUI: {e}")


async def open_web_ui(port: int = 8080) -> None:
    """Open Web UI in browser"""
    print(f"\n🌐 Opening Web UI at http://localhost:{port}/...")
    
    url = f"http://localhost:{port}/"
    
    # Try to open in browser
    import webbrowser
    try:
        webbrowser.open(url)
        print(f"  ✅ Web UI opened in browser")
        print(f"  🔗 URL: {url}")
    except Exception as e:
        logger.error(f"Failed to open browser: {e}")
        print(f"  ℹ️  Manually open: {url}")


async def finalize_onboarding(mode: str = "quickstart", skip_ui: bool = False) -> dict:
    """Finalize onboarding and optionally launch UI
    
    Args:
        mode: "quickstart" or "advanced"
        skip_ui: Skip UI launch prompt
        
    Returns:
        Dict with finalization result
    """
    print("\n" + "=" * 60)
    print("🎉 ONBOARDING COMPLETE!")
    print("=" * 60)
    
    if skip_ui:
        print("\n⏭️  Skipping UI launch")
        return {"ui_launched": False, "skipped": True}
    
    print("\n🎯 How do you want to interact with OpenClaw?")
    print("  1. Terminal UI (TUI) - Recommended")
    print("  2. Web UI (browser-based)")
    print("  3. CLI only (no UI)")
    print("  4. Later")
    
    if mode == "quickstart":
        choice = "1"  # Auto-select TUI in quickstart
        print(f"\n⚡ QuickStart: Launching Terminal UI (option 1)")
    else:
        choice = input("\nSelect option [1-4]: ").strip()
    
    if choice == "1":
        # Launch TUI
        print("\n🚀 Starting Terminal UI...")
        print("  💡 Use Ctrl+D to exit TUI")
        print("  💡 Use /help for commands")
        
        # Note: TUI will block until user exits
        try:
            await launch_tui()
        except KeyboardInterrupt:
            print("\n👋 TUI closed")
        
        return {"ui_launched": True, "ui_type": "tui"}
    
    elif choice == "2":
        # Open Web UI
        print("\n✅ Gateway must be running to use Web UI")
        print("   Start gateway with: openclaw gateway run")
        print("   Or: openclaw start")
        
        # Try to open browser
        try:
            await open_web_ui()
        except Exception as e:
            logger.error(f"Failed to open Web UI: {e}")
        
        return {"ui_launched": True, "ui_type": "web"}
    
    elif choice == "3":
        print("\n✅ CLI-only mode selected")
        print("   Use 'openclaw' commands to interact")
        print("   Examples:")
        print("     openclaw status")
        print("     openclaw agent run -m 'Hello!'")
        print("     openclaw gateway run")
        
        return {"ui_launched": False, "mode": "cli"}
    
    else:
        print("\n⏭️  You can launch UI later with:")
        print("     openclaw tui         # Terminal UI")
        print("     openclaw dashboard   # Web UI")
        
        return {"ui_launched": False, "mode": "later"}


__all__ = ["finalize_onboarding", "launch_tui", "open_web_ui"]
