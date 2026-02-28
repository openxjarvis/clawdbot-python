"""Onboarding wizard

First-run onboarding experience for new users.
Matches TypeScript openclaw/src/wizard/onboarding.ts
"""
from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..agents.model_catalog import load_model_catalog, ModelCatalogEntry
from ..agents.agent_paths import resolve_openclaw_agent_dir
from ..config.loader import load_config, save_config
from ..config.schema import ClawdbotConfig, AgentConfig, GatewayConfig, ChannelsConfig, AuthConfig
from .auth import configure_auth, check_env_api_key
from .config import configure_telegram_enhanced, configure_discord_enhanced, configure_agent
from .onboard_hooks import setup_hooks
from .onboard_skills import setup_skills
from .onboard_finalize import finalize_onboarding

logger = logging.getLogger(__name__)


async def check_gateway_health(port: int = 18789, token: Optional[str] = None) -> dict:
    """Check if Gateway is reachable and healthy
    
    Args:
        port: Gateway port
        token: Authentication token (if required)
    
    Returns:
        Dict with 'ok' (bool) and 'detail' (str) keys
    """
    try:
        import httpx
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            
            response = await client.get(
                f"http://127.0.0.1:{port}/health",
                headers=headers
            )
            response.raise_for_status()
            return {"ok": True, "detail": "Gateway reachable"}
    except Exception as e:
        return {"ok": False, "detail": str(e)}


async def run_onboarding_wizard(
    config: Optional[dict] = None,
    workspace_dir: Optional[Path] = None,
    install_daemon: Optional[bool] = None,
    skip_health: bool = False,
    skip_ui: bool = False,
    non_interactive: bool = False,
    accept_risk: bool = False,
    flow: Optional[str] = None,
) -> dict:
    """
    Run onboarding wizard
    
    Guides new users through initial setup:
    - Risk confirmation
    - Mode selection (QuickStart/Advanced)
    - API key configuration
    - Model selection
    - Gateway configuration
    - Channel setup
    - Gateway service installation (optional)
    
    Args:
        config: Existing Gateway configuration (optional)
        workspace_dir: Workspace directory (optional)
        install_daemon: Whether to install Gateway service (None=auto-decide based on flow)
        skip_health: Skip health check after installation
        skip_ui: Skip UI selection prompts
        non_interactive: Run without prompts (requires accept_risk=True)
        accept_risk: Accept risk acknowledgement
        flow: Onboarding flow type: "quickstart" or "advanced"
        
    Returns:
        Dict with wizard results
    """
    logger.info("Starting onboarding wizard")
    
    print("\n" + "=" * 80)
    print("🚀 Welcome to OpenClaw Onboarding!")
    print("=" * 80)
    print("\nThis wizard will help you set up OpenClaw for the first time.")
    print("You can exit anytime with Ctrl+C")
    
    # Step 1: Risk confirmation
    if non_interactive:
        if not accept_risk:
            print("[red]Error:[/red] --accept-risk is required for --non-interactive mode")
            return {"completed": False, "skipped": True, "reason": "Risk not accepted"}
    else:
        if not _confirm_risks():
            return {"completed": False, "skipped": True, "reason": "User declined"}
    
    # Step 2: Mode selection
    if flow:
        flow_normalized = flow.lower().strip()
        if flow_normalized in ["quickstart", "advanced"]:
            mode = flow_normalized
            print(f"\n✓ Using {mode} mode")
        else:
            print(f"[yellow]Warning:[/yellow] Invalid --flow value '{flow}'. Using interactive mode selection.")
            mode = _select_mode()
    else:
        mode = _select_mode()
    
    # Step 3: Load or create config
    try:
        existing_config_dict = load_config(as_dict=True)
        print("\n✓ Found existing configuration")
        
        if mode == "quickstart":
            print("QuickStart mode: Using existing configuration as base")
            # Convert dict to ClawdbotConfig object
            claw_config = ClawdbotConfig(**existing_config_dict) if existing_config_dict else ClawdbotConfig()
        else:
            action = _prompt_config_action()
            if action == "reset":
                print("Creating fresh configuration...")
                claw_config = ClawdbotConfig()
            elif action == "modify":
                print("Modifying existing configuration...")
                # Convert dict to ClawdbotConfig object
                claw_config = ClawdbotConfig(**existing_config_dict) if existing_config_dict else ClawdbotConfig()
            else:  # keep
                print("Keeping existing configuration...")
                return {"completed": True, "skipped": False, "kept_existing": True}
    except Exception as e:
        logger.info(f"No existing config: {e}")
        print("\nCreating new configuration...")
        claw_config = ClawdbotConfig()
    
    # Step 4: Provider configuration
    provider_config = await _configure_provider(mode)
    if provider_config:
        model_value = provider_config.get("model", "claude-sonnet-4")
        # Write to agents.defaults.model — the canonical path read by bootstrap.py
        if not claw_config.agents:
            from openclaw.config.schema import AgentsConfig
            claw_config.agents = AgentsConfig()
        if not claw_config.agents.defaults:
            from openclaw.config.schema import AgentDefaults
            claw_config.agents.defaults = AgentDefaults()
        claw_config.agents.defaults.model = model_value
        # Keep legacy agent.model in sync (string only — strip fallbacks wrapper)
        if not claw_config.agent:
            claw_config.agent = AgentConfig()
        primary_str = model_value if isinstance(model_value, str) else (
            model_value.get("primary", "") if isinstance(model_value, dict) else str(model_value)
        )
        claw_config.agent.model = primary_str
        # Store auth in environment variables (handled by configure_auth)
    
    # Step 5: Agent configuration
    if mode == "advanced":
        agent_config = await _configure_agent_settings()
        if agent_config:
            if not claw_config.agents:
                from openclaw.config.schema import AgentsConfig
                claw_config.agents = AgentsConfig()
            if not claw_config.agents.defaults:
                from openclaw.config.schema import AgentDefaults
                claw_config.agents.defaults = AgentDefaults()
            claw_config.agents.defaults.workspace = agent_config.get("workspace", "./workspace")
    
    # Step 6: Gateway configuration
    gateway_config = await _configure_gateway(mode)
    if gateway_config:
        if not claw_config.gateway:
            claw_config.gateway = GatewayConfig()
        claw_config.gateway.port = gateway_config.get("port", 18789)
        claw_config.gateway.bind = gateway_config.get("bind", "loopback")
        
        # Handle authentication properly
        if "auth_token" in gateway_config or "auth_password" in gateway_config:
            if not claw_config.gateway.auth:
                claw_config.gateway.auth = AuthConfig()
            
            if "auth_token" in gateway_config:
                claw_config.gateway.auth.token = gateway_config["auth_token"]
                claw_config.gateway.auth.mode = "token"
            if "auth_password" in gateway_config:
                claw_config.gateway.auth.password = gateway_config["auth_password"]
                claw_config.gateway.auth.mode = "password"
    
    # Step 7: Channels configuration
    channels_config = await _configure_channels(mode)
    if channels_config:
        if not claw_config.channels:
            claw_config.channels = ChannelsConfig()
        if "telegram" in channels_config:
            claw_config.channels.telegram = channels_config["telegram"]
        if "discord" in channels_config:
            claw_config.channels.discord = channels_config["discord"]
    
    # Step 7.5: Collect user information for workspace
    user_info = {}
    if not non_interactive and (mode == "advanced" or mode == "quickstart"):
        print("\n" + "-" * 80)
        print("User Profile Setup")
        print("-" * 80)
        print("\nLet's personalize your experience.")
        
        # User name
        user_name = input("\nWhat's your name? [Optional, press Enter to skip]: ").strip()
        if user_name:
            user_info["name"] = user_name
            user_info["what_to_call_them"] = input(f"How should the agent address you? [{user_name}]: ").strip() or user_name
        
        # Timezone
        import datetime
        try:
            local_tz = datetime.datetime.now().astimezone().tzinfo
            tz_str = str(local_tz)
        except Exception:
            tz_str = "UTC"
        
        user_timezone = input(f"Your timezone? [{tz_str}]: ").strip() or tz_str
        user_info["timezone"] = user_timezone
        
        # Agent personality preference
        print("\nWhat kind of agent personality do you prefer?")
        print("  1. Professional - Formal and focused")
        print("  2. Friendly - Warm and conversational")
        print("  3. Concise - Brief and to the point")
        print("  4. Custom - I'll configure it later")
        
        personality_choice = input("\nSelect [2]: ").strip() or "2"
        personality_map = {
            "1": "professional",
            "2": "friendly",
            "3": "concise",
            "4": "custom"
        }
        user_info["preferred_vibe"] = personality_map.get(personality_choice, "friendly")
    
    # Store user info for later use
    if user_info:
        # Store in a temporary attribute on config
        claw_config._user_info = user_info
    
    # Step 8: Save configuration
    print("\n" + "-" * 80)
    print("Configuration Summary:")
    print("-" * 80)
    print(f"Provider: {provider_config.get('provider', 'Not configured') if provider_config else 'Not configured'}")
    _m = (claw_config.agents.defaults.model if claw_config.agents and claw_config.agents.defaults else None) or (claw_config.agent.model if claw_config.agent else "Default")
    if isinstance(_m, dict):
        print(f"Model: {_m.get('primary', '')}  (fallbacks: {', '.join(_m.get('fallbacks', []))})")
    else:
        print(f"Model: {_m}")
    print(f"Gateway Port: {claw_config.gateway.port if claw_config.gateway else 18789}")
    print(f"Gateway Bind: {claw_config.gateway.bind if claw_config.gateway else 'loopback'}")
    if channels_config:
        if "telegram" in channels_config:
            print("✓ Telegram configured")
        if "discord" in channels_config:
            print("✓ Discord configured")
    print("-" * 80)
    
    save_choice = input("\nSave this configuration? [Y/n]: ").strip().lower()
    if save_choice == "n":
        print("Configuration not saved. Exiting...")
        return {"completed": False, "skipped": True, "reason": "User chose not to save"}
    
    # Add TS-aligned configuration fields (wizard, messages, commands, hooks)
    from datetime import datetime, timezone
    from openclaw.config.schema import WizardConfig, MessagesConfig, CommandsConfig, HooksConfig, InternalHooksConfig
    
    if not claw_config.wizard:
        claw_config.wizard = WizardConfig(
            lastRunAt=datetime.now(timezone.utc).isoformat(),
            lastRunVersion="0.6.0",
            lastRunCommand="onboard",
            lastRunMode=mode
        )
    
    if not claw_config.messages:
        claw_config.messages = MessagesConfig(ackReactionScope="group-mentions")
    
    if not claw_config.commands:
        claw_config.commands = CommandsConfig(native="auto", nativeSkills="auto")
    
    if not claw_config.hooks:
        claw_config.hooks = HooksConfig(
            enabled=True,
            internal=InternalHooksConfig(
                enabled=True,
                entries={
                    "boot-md": {"enabled": True},
                    "bootstrap-extra-files": {"enabled": True},
                    "command-logger": {"enabled": True},
                    "session-memory": {"enabled": True},
                }
            )
        )
    
    try:
        save_config(claw_config)
        print("✓ Configuration saved!")
    except Exception as e:
        logger.error(f"Failed to save config: {e}")
        print(f"✗ Error saving configuration: {e}")
        return {"completed": False, "error": str(e)}
    
    # Step 9: Mark onboarding complete
    if workspace_dir:
        mark_onboarding_complete(workspace_dir)
    else:
        mark_onboarding_complete(Path.home() / ".openclaw" / "workspace")
    
    # Step 9.2: Ensure root directories (identity, delivery-queue, canvas, completions, logs)
    print("\n" + "~" * 60)
    print("Initializing directories...")
    print("~" * 60)
    
    try:
        from ..agents.ensure_root_dirs import ensure_root_directories
        
        # Determine OpenClaw root directory (parent of workspace)
        root_dir = workspace_dir.parent if workspace_dir else (Path.home() / ".openclaw")
        
        # Ensure all root directories
        root_result = ensure_root_directories(root_dir)
        
        if "identity" in root_result and "device_id" in root_result["identity"]:
            print(f"✓ Created device identity: {root_result['identity']['device_id']}")
        if "delivery_queue" in root_result:
            print("✓ Created delivery queue directory")
        if "completions" in root_result:
            print("✓ Created shell completion scripts")
        if "canvas" in root_result:
            print("✓ Created canvas with index.html")
        if "logs" in root_result:
            print("✓ Created log directories")
            
    except Exception as e:
        logger.warning(f"Failed to ensure root directories: {e}")
        print("⚠ Could not create some directories (non-fatal)")
    
    # Step 9.3: Populate workspace with user information
    if hasattr(claw_config, '_user_info') and claw_config._user_info:
        print("\n" + "~" * 60)
        print("Personalizing workspace...")
        print("~" * 60)
        
        try:
            from ..agents.populate_workspace import populate_user_md, populate_soul_md, populate_identity_md
            from ..agents.ensure_workspace import ensure_agent_workspace
            
            # Determine workspace directory
            ws_dir = workspace_dir or (Path.home() / ".openclaw" / "workspace")
            
            # Ensure workspace exists
            ensure_agent_workspace(
                workspace_dir=ws_dir,
                ensure_bootstrap_files=True,
                skip_bootstrap=False
            )
            
            # Write user info
            populate_user_md(ws_dir, claw_config._user_info)
            print("✓ Created USER.md with your information")
            
            # Update SOUL.md with vibe
            if "preferred_vibe" in claw_config._user_info:
                populate_soul_md(ws_dir, claw_config._user_info["preferred_vibe"])
                print("✓ Updated SOUL.md with your preferences")
            
            # Create IDENTITY.md placeholder
            populate_identity_md(ws_dir)
            print("✓ Created IDENTITY.md template")
            
            print(f"\n✓ Workspace files created at: {ws_dir}")
            print("  You can edit these files anytime to customize your agent's behavior.")
            
        except Exception as e:
            logger.warning(f"Failed to populate workspace: {e}")
            print("⚠ Could not auto-populate workspace files")
            print(f"  You can manually edit files in: {ws_dir if 'ws_dir' in locals() else workspace_dir}")
    
    # Step 9.5: Install Gateway service (if requested)
    gateway_installed = False
    gateway_running = False
    
    # Determine if we should install daemon
    should_install_daemon = install_daemon
    if should_install_daemon is None:
        # Auto-decide based on flow: quickstart installs by default
        should_install_daemon = (mode == "quickstart")
    
    if should_install_daemon:
        print("\n" + "~" * 60)
        print("Installing Gateway Service...")
        print("~" * 60)
        
        try:
            from ..cli.daemon_cmd import (
                is_service_installed,
                is_service_running,
                install_service_programmatic,
                start_service_programmatic,
                stop_service_programmatic,
            )
            gateway_port = claw_config.gateway.port if claw_config.gateway else 18789
            
            # Check if already installed
            if is_service_installed():
                if non_interactive or mode == "quickstart":
                    action = "R"  # Auto-restart in non-interactive/quickstart
                    print("Gateway service already installed. Restarting...")
                else:
                    action = input("\nGateway service already installed. [R]estart / Re[i]nstall / [S]kip? [R]: ").strip().upper() or "R"
                
                if action == "S":
                    print("Skipping Gateway service installation")
                    should_install_daemon = False
                    gateway_installed = True
                    gateway_running = is_service_running()
                elif action in ("R", "I"):
                    print("Stopping existing service...")
                    stop_service_programmatic()
                    if action == "I":
                        print("Uninstalling existing service...")
                        from ..cli.daemon_cmd import daemon_uninstall
                        try:
                            daemon_uninstall(json_output=False)
                        except SystemExit:
                            pass
                    print("Installing Gateway service...")
                    ok = install_service_programmatic(port=gateway_port)
                    if ok:
                        print("✓ Gateway service installed and started")
                        gateway_installed = True
                        gateway_running = True
                    else:
                        print("✗ Gateway service install failed")
                        gateway_running = False
            
            if should_install_daemon and not gateway_installed:
                print("Installing Gateway service...")
                ok = install_service_programmatic(port=gateway_port)
                if ok:
                    print("✓ Gateway service installed")
                    gateway_installed = True
                    gateway_running = True
                else:
                    print("✗ Gateway service install failed")
                    print("You can install it manually with:")
                    print("  $ uv run openclaw daemon install")
                    gateway_installed = False
                    gateway_running = False
                    
        except Exception as e:
            logger.error(f"Failed to install/start Gateway: {e}")
            print(f"✗ Gateway service installation failed: {e}")
            print("\nYou can install it manually later with:")
            print("  $ uv run openclaw daemon install")
            print("  $ uv run openclaw gateway start")
            gateway_installed = False
            gateway_running = False
    
    # Step 9.6: Health check
    gateway_port = claw_config.gateway.port if claw_config.gateway else 18789
    gateway_token = None
    if claw_config.gateway and claw_config.gateway.auth:
        gateway_token = claw_config.gateway.auth.token
    
    if not skip_health and gateway_running:
        print("\nRunning health check...")
        
        # Wait a bit for service to start
        import asyncio
        await asyncio.sleep(2)
        
        health = await check_gateway_health(
            port=gateway_port,
            token=gateway_token
        )
        
        if health["ok"]:
            print("✓ Gateway is healthy")
        else:
            print(f"⚠ Gateway health check failed: {health['detail']}")
            print("Troubleshooting: https://docs.openclaw.ai/gateway/troubleshooting")
    
    # Step 9.7: UI selection prompt (optional, for advanced mode)
    if not skip_ui and gateway_running and mode == "advanced" and not non_interactive:
        print("\n" + "~" * 60)
        print("How would you like to start?")
        print("~" * 60)
        print("  1. Open Web UI (recommended)")
        print("  2. Start interactive chat")
        print("  3. Do this later")
        
        choice = input("\nSelect option [1]: ").strip() or "1"
        
        if choice == "1":
            import webbrowser
            url = f"http://localhost:{gateway_port}"
            print(f"\nOpening {url} in your browser...")
            if webbrowser.open(url):
                print("✓ Opened Web UI in your browser")
            else:
                print(f"⚠ Could not open browser automatically. Please visit: {url}")
        elif choice == "2":
            print("\n💬 Interactive chat mode:")
            print("Use the following command to start chatting:")
            print(f"  $ uv run openclaw chat --interactive")
            print("\nOr send a single message:")
            print(f"  $ uv run openclaw chat 'Hello!'")
        else:
            print("\n✓ You can access the Web UI anytime:")
            print(f"  http://localhost:{gateway_port}")
    
    # Step 10: Display comprehensive next steps
    print("\n" + "=" * 80)
    print("🎉 Onboarding Complete!")
    print("=" * 80)
    
    # Gateway information
    gateway_port = claw_config.gateway.port if claw_config.gateway else 18789
    gateway_token = None
    if claw_config.gateway and claw_config.gateway.auth:
        gateway_token = claw_config.gateway.auth.token
    
    print("\n📡 Gateway Information:")
    print(f"  Port: {gateway_port}")
    print(f"  Web UI: http://localhost:{gateway_port}")
    print(f"  WebSocket: ws://localhost:{gateway_port}")
    if gateway_token:
        print(f"  Auth token: {gateway_token[:20]}... (stored in config)")
        print(f"  View full token: uv run openclaw config get gateway.auth.token")
    
    # Service status
    if gateway_installed and gateway_running:
        print("\n✓ Gateway service: Installed and Running")
        print("  Manage with:")
        print("    $ uv run openclaw gateway status")
        print("    $ uv run openclaw gateway stop")
        print("    $ uv run openclaw gateway restart")
    elif gateway_installed:
        print("\n⚠ Gateway service: Installed but not running")
        print("  Start with:")
        print("    $ uv run openclaw gateway start")
    else:
        print("\n⚠ Gateway service: Not installed")
        print("  Install with:")
        print("    $ uv run openclaw gateway install")
        print("    $ uv run openclaw gateway start")
    
    # Channels
    if channels_config:
        print("\n📱 Configured Channels:")
        if "telegram" in channels_config:
            print("  ✓ Telegram - Open Telegram and message your bot")
        if "discord" in channels_config:
            print("  ✓ Discord - Invite your bot to a server")
    
    # Next steps
    print("\n🚀 Next Steps:")
    if not gateway_running:
        print("  1. Start the Gateway:")
        print("     $ uv run openclaw gateway start")
        print()
        print("  2. Open the Control UI:")
        print(f"     http://localhost:{gateway_port}")
        if gateway_token:
            print("     (Paste the auth token if prompted)")
    else:
        print(f"  1. Open the Control UI: http://localhost:{gateway_port}")
        if gateway_token:
            print("     (Paste the auth token if prompted)")
        print()
        print("  2. Or use the CLI:")
        print("     $ uv run openclaw chat 'Hello!'")
        print("     $ uv run openclaw chat --interactive")
    
    print("\n📚 Documentation:")
    print("  Getting started: https://docs.openclaw.ai/getting-started")
    print("  Configuration:   https://docs.openclaw.ai/gateway/configuration")
    print("  Security:        https://docs.openclaw.ai/security")
    print("  Troubleshooting: https://docs.openclaw.ai/gateway/troubleshooting")
    
    print("\n💡 Useful Commands:")
    print("  View config:     uv run openclaw config show")
    print("  Health check:    uv run openclaw doctor")
    print("  List channels:   uv run openclaw channels list")
    print("  List cron jobs:  uv run openclaw cron list")
    print("  View logs:       uv run openclaw logs tail")
    
    # Check if BOOTSTRAP.md exists
    ws_dir = workspace_dir or (Path.home() / ".openclaw" / "workspace")
    bootstrap_path = ws_dir / "BOOTSTRAP.md"
    if bootstrap_path.exists():
        print("\n🎯 First-time Setup:")
        print("  When you first chat with your agent, it will guide you through:")
        print("  - Choosing the agent's name and personality")
        print("  - Refining your preferences")
        print("  - Setting up any additional details")
        print("\n  This is a one-time conversation to help the agent learn about you.")
    
    print("\n⚡ Tips:")
    print("  - Install globally to avoid typing 'uv run':")
    print("    $ uv pip install -e .")
    print("  - Enable shell completion:")
    print("    $ uv run openclaw completion --install")
    print("  - Run in foreground to see logs:")
    print("    $ uv run openclaw start")
    
    print("\n🔒 Security:")
    print("  Run security audit: uv run openclaw security audit")
    print("  Docs: https://docs.openclaw.ai/security")
    
    print("\n" + "=" * 80 + "\n")
    
    # Step 11: staged onboarding modules (TS-style decomposition)
    hooks_result = await setup_hooks(workspace_dir=workspace_dir, mode=mode)
    skills_result = await setup_skills(mode=mode)
    finalize_result = await finalize_onboarding(mode=mode, skip_ui=skip_ui)

    logger.info("Onboarding wizard complete")
    
    return {
        "completed": True,
        "skipped": False,
        "mode": mode,
        "provider": provider_config.get("provider") if provider_config else None,
        "hooks": hooks_result,
        "skills": skills_result,
        "finalize": finalize_result,
    }


def _confirm_risks() -> bool:
    """Confirm user understands risks"""
    print("\n" + "-" * 80)
    print("⚠️  Important: Security & Risks")
    print("-" * 80)
    print("""
OpenClaw is an AI agent that can:
  • Execute commands on your system
  • Read and modify files
  • Make network requests
  • Use your API keys

Please ensure:
  ✓ You trust the codebase
  ✓ You understand the permissions granted
  ✓ You review agent actions carefully
  ✓ You keep your API keys secure

This is experimental software. Use at your own risk.
""")
    
    confirm = input("Do you understand and accept these risks? [y/N]: ").strip().lower()
    return confirm == "y"


def _select_mode() -> str:
    """Select onboarding mode"""
    print("\n" + "-" * 80)
    print("Onboarding Mode")
    print("-" * 80)
    print("\nChoose your setup mode:")
    print("  1. QuickStart  - Fast setup with recommended settings (5 min)")
    print("  2. Advanced    - Customize everything (15 min)")
    
    choice = input("\nSelect mode [1]: ").strip()
    
    if choice == "2":
        print("\n✓ Advanced mode selected")
        return "advanced"
    else:
        print("\n✓ QuickStart mode selected")
        return "quickstart"


def _prompt_config_action() -> str:
    """Prompt for action on existing config"""
    print("\nWhat would you like to do with existing configuration?")
    print("  1. Keep    - Use existing configuration")
    print("  2. Modify  - Update specific settings")
    print("  3. Reset   - Start fresh")
    
    choice = input("\nSelect action [2]: ").strip()
    
    if choice == "1":
        return "keep"
    elif choice == "3":
        return "reset"
    else:
        return "modify"


# Per-provider model menus (curated short-list, mirrors TS model catalog).
# Format: (model_id, display_hint)
_PROVIDER_MODELS: dict[str, list[tuple[str, str]]] = {
    "anthropic": [
        ("anthropic/claude-sonnet-4",           "Claude Sonnet 4         (recommended)"),
        ("anthropic/claude-opus-4-5",           "Claude Opus 4.5         (most capable)"),
        ("anthropic/claude-3-7-sonnet-20250219", "Claude 3.7 Sonnet       (new reasoning)"),
        ("anthropic/claude-3-5-haiku-20241022", "Claude 3.5 Haiku        (fast / cheap)"),
        ("anthropic/claude-opus-4-0",           "Claude Opus 4.0         (reasoning)"),
        ("anthropic/claude-haiku-4-5",          "Claude Haiku 4.5        (reasoning)"),
    ],
    "openai": [
        ("openai/gpt-4o",       "GPT-4o           (recommended)"),
        ("openai/gpt-5.2",      "GPT-5.2          (reasoning)"),
        ("openai/gpt-5-mini",   "GPT-5 Mini       (reasoning)"),
        ("openai/gpt-4o-mini",  "GPT-4o Mini      (fast / cheap)"),
        ("openai/o3-mini",      "o3-mini          (reasoning)"),
        ("openai/gpt-5.3-codex", "GPT-5.3 Codex   (code specialist)"),
    ],
    "gemini": [
        ("google/gemini-3-pro-preview",  "Gemini 3 Pro        (recommended)"),
        ("google/gemini-2.5-pro",        "Gemini 2.5 Pro      (reasoning)"),
        ("google/gemini-3-flash-preview", "Gemini 3 Flash      (reasoning)"),
        ("google/gemini-2.5-flash",      "Gemini 2.5 Flash    (reasoning)"),
        ("google/gemini-2.0-flash",      "Gemini 2.0 Flash    (fast)"),
        ("google/gemini-2.0-flash-lite", "Gemini 2.0 Flash Lite (cheap)"),
    ],
    "ollama": [
        ("ollama/llama3",    "Llama 3"),
        ("ollama/mistral",   "Mistral"),
        ("ollama/codellama", "CodeLlama"),
    ],
}


async def _get_provider_models_dynamic(provider: str) -> list[tuple[str, str]]:
    """Load models for a provider dynamically from model catalog.
    
    Returns list of (model_id, display_label) tuples.
    Falls back to hardcoded _PROVIDER_MODELS if dynamic loading fails.
    
    Aligns with TS model-picker.ts which uses loadModelCatalog().
    """
    try:
        catalog = await load_model_catalog(use_cache=False)
        
        # Normalize provider name (gemini -> google)
        catalog_provider = "google" if provider == "gemini" else provider
        
        # Filter models for this provider
        provider_models = [
            entry for entry in catalog
            if entry.provider.lower() == catalog_provider.lower()
        ]
        
        if not provider_models:
            # Fallback to hardcoded
            return _PROVIDER_MODELS.get(provider, [])
        
        # Build display options with metadata
        options: list[tuple[str, str]] = []
        for entry in provider_models:
            # Format: "provider/model-id"
            full_id = f"{provider}/{entry.id}"
            
            # Build display label with metadata
            label_parts = [entry.name]
            if entry.context_window:
                ctx_display = f"{entry.context_window // 1000}k"
                label_parts.append(f"({ctx_display})")
            if entry.reasoning:
                label_parts.append("[reasoning]")
            
            label = " ".join(label_parts)
            options.append((full_id, label))
        
        return options if options else _PROVIDER_MODELS.get(provider, [])
        
    except Exception as e:
        logger.debug(f"Dynamic model loading failed for {provider}: {e}")
        # Fallback to hardcoded
        return _PROVIDER_MODELS.get(provider, [])


async def _pick_model(provider: str, exclude: list[str] | None = None) -> str | None:
    """Show numbered model menu for *provider* and return the chosen model id.

    Returns None if the user presses Enter with no input (accept default) or
    chooses an invalid option (falls back to first entry).
    
    Now supports dynamic model loading from model catalog (aligns with TS).
    """
    # Try dynamic loading first, fallback to hardcoded
    options = await _get_provider_models_dynamic(provider)
    
    # Filter excluded
    if exclude:
        options = [(mid, hint) for mid, hint in options if mid not in exclude]
    
    if not options:
        return None

    print()
    for i, (mid, hint) in enumerate(options, 1):
        default_tag = "  ← default" if i == 1 else ""
        print(f"  {i}. {hint}{default_tag}")

    raw = input(f"\nSelect model [1]: ").strip()
    if not raw:
        return options[0][0]
    try:
        idx = int(raw) - 1
        if 0 <= idx < len(options):
            return options[idx][0]
    except ValueError:
        pass
    return options[0][0]


async def _configure_provider(mode: str) -> Optional[dict]:
    """Configure LLM provider"""
    print("\n" + "-" * 80)
    print("Provider Configuration")
    print("-" * 80)

    if mode == "quickstart":
        # QuickStart: Check environment variables first
        providers = ["anthropic", "openai", "gemini"]
        for provider in providers:
            if check_env_api_key(provider):
                print(f"\n✓ Found {provider.title()} API key in environment")
                use_it = input(f"Use {provider.title()}? [Y/n]: ").strip().lower()
                if use_it != "n":
                    # Still let the user pick a specific model
                    print(f"\nSelect {provider.title()} model:")
                    primary = await _pick_model(provider) or _PROVIDER_MODELS[provider][0][0]
                    model_value = await _ask_fallbacks(provider, primary)
                    return {"provider": provider, "model": model_value}

    # Prompt for provider
    print("\nSelect your LLM provider:")
    print("  1. Anthropic (Claude)  - Recommended")
    print("  2. OpenAI (GPT-4)")
    print("  3. Google (Gemini)")
    print("  4. Ollama (Local)")

    choice = input("\nSelect provider [1]: ").strip()

    provider_map = {
        "1": "anthropic",
        "2": "openai",
        "3": "gemini",
        "4": "ollama",
    }
    provider = provider_map.get(choice, "anthropic")

    # Configure auth (skips if Ollama)
    if provider != "ollama":
        try:
            auth_result = configure_auth(provider)
            print(f"\n✓ {provider.title()} configured")
        except Exception as e:
            print(f"\n✗ Failed to configure {provider}: {e}")
            return None

    # Select primary model
    print(f"\nSelect primary model for {provider.title()}:")
    primary = await _pick_model(provider) or _PROVIDER_MODELS.get(provider, [("",)])[0][0]

    model_value = await _ask_fallbacks(provider, primary)
    return {"provider": provider, "model": model_value}


async def _ask_fallbacks(provider: str, primary: str) -> str | dict:
    """Ask if the user wants fallback models. Returns a string (no fallbacks)
    or a dict {primary, fallbacks} suitable for agents.defaults.model."""
    add_fb = input("\nAdd fallback models? [y/N]: ").strip().lower()
    if add_fb != "y":
        return primary

    fallbacks: list[str] = []
    print("\nSelect fallback models (shown in priority order). Enter 'done' to finish.")
    while len(fallbacks) < 3:
        print(f"\nFallback #{len(fallbacks) + 1} for {provider.title()}:")
        chosen = await _pick_model(provider, exclude=[primary] + fallbacks)
        if chosen is None:
            break
        fallbacks.append(chosen)
        another = input("Add another fallback? [y/N]: ").strip().lower()
        if another != "y":
            break

    if not fallbacks:
        return primary
    return {"primary": primary, "fallbacks": fallbacks}


async def _configure_agent_settings() -> Optional[dict]:
    """Configure agent settings"""
    print("\n" + "-" * 80)
    print("Agent Settings")
    print("-" * 80)
    
    return await configure_agent()


async def _configure_gateway(mode: str) -> Optional[dict]:
    """Configure Gateway settings"""
    print("\n" + "-" * 80)
    print("Gateway Configuration")
    print("-" * 80)
    
    config = {}
    
    # Port
    if mode == "quickstart":
        config["port"] = 18789
        print(f"\nUsing default port: {config['port']}")
    else:
        port_input = input("\nGateway port [18789]: ").strip()
        config["port"] = int(port_input) if port_input else 18789
    
    # Bind mode
    if mode == "quickstart":
        config["bind"] = "loopback"
        print("Using loopback mode (local access only)")
    else:
        print("\nBind mode:")
        print("  1. loopback  - Local access only (recommended)")
        print("  2. lan       - LAN access")
        print("  3. auto      - Auto-detect")
        
        bind_choice = input("\nSelect bind mode [1]: ").strip()
        bind_map = {"1": "loopback", "2": "lan", "3": "auto"}
        config["bind"] = bind_map.get(bind_choice, "loopback")
    
    # Authentication
    if mode == "quickstart":
        # Generate token
        config["auth_token"] = secrets.token_urlsafe(32)
        print("\n✓ Generated authentication token")
    else:
        print("\nAuthentication:")
        print("  1. Token     - Random token (recommended)")
        print("  2. Password  - Custom password")
        print("  3. None      - No authentication (local only)")
        
        auth_choice = input("\nSelect auth mode [1]: ").strip()
        
        if auth_choice == "2":
            password = input("Enter password: ").strip()
            if password:
                config["auth_password"] = password
        elif auth_choice == "3":
            print("⚠️  Warning: No authentication - use only for local development")
        else:
            config["auth_token"] = secrets.token_urlsafe(32)
            print("✓ Generated authentication token")
    
    return config


async def _configure_channels(mode: str) -> Optional[dict]:
    """Configure channels"""
    print("\n" + "-" * 80)
    print("Channels Configuration")
    print("-" * 80)
    
    if mode == "quickstart":
        setup_channels = input("\nConfigure channels now? [y/N]: ").strip().lower()
        if setup_channels != "y":
            print("Skipping channels. You can configure them later with:")
            print("  $ openclaw configure channels")
            return None
    
    channels_config = {}
    
    print("\nWhich channels would you like to configure?")
    print("  1. Telegram")
    print("  2. Discord")
    print("  3. Skip")
    
    choice = input("\nSelect channel [3]: ").strip()
    
    if choice == "1":
        print("\n" + "~" * 60)
        print("Configuring Telegram")
        print("~" * 60)
        telegram_config = configure_telegram_enhanced()
        if telegram_config:
            channels_config["telegram"] = telegram_config
    elif choice == "2":
        print("\n" + "~" * 60)
        print("Configuring Discord")
        print("~" * 60)
        discord_config = configure_discord_enhanced()
        if discord_config:
            channels_config["discord"] = discord_config
    
    return channels_config if channels_config else None


def mark_onboarding_complete(workspace_dir: Path) -> None:
    """Mark onboarding as complete by writing workspace-state.json.

    Matches TypeScript behavior: only writes onboardingCompletedAt into
    workspace-state.json. Does NOT write a separate onboarding-complete
    marker file (that was a Python-only addition not present in TS).
    """
    now_iso = datetime.now().isoformat()
    write_workspace_state(workspace_dir, onboarding_completed_at=now_iso)
    logger.info("Onboarding marked complete in workspace-state.json: %s", workspace_dir)


def write_workspace_state(
    workspace_dir: Path,
    bootstrap_seeded_at: Optional[str] = None,
    onboarding_completed_at: Optional[str] = None,
) -> None:
    """Write or update workspace-state.json.

    Delegates to ensure_workspace.write_workspace_state() which uses the
    correct path: {workspaceDir}/.openclaw/workspace-state.json — matching
    TypeScript workspace.ts WORKSPACE_STATE_DIRNAME = ".openclaw".
    """
    from openclaw.agents.ensure_workspace import write_workspace_state as _ws_write
    _ws_write(
        workspace_dir,
        bootstrap_seeded_at=bootstrap_seeded_at,
        onboarding_completed_at=onboarding_completed_at,
    )


def is_first_run(workspace_dir: Path) -> bool:
    """Check if this is the first run (onboarding not yet completed).

    Matches TypeScript: checks onboardingCompletedAt in workspace-state.json.
    """
    from openclaw.agents.ensure_workspace import is_workspace_onboarding_completed
    return not is_workspace_onboarding_completed(workspace_dir)


# Alias matching TS runInteractiveOnboarding — used by bootstrap and tests
run_interactive_onboarding = run_onboarding_wizard
