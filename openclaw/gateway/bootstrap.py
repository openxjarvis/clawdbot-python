"""Gateway bootstrap sequence (matches TypeScript gateway/server.impl.ts startGatewayServer)

Implements the full 40-step TypeScript gateway initialization in Python.
"""
from __future__ import annotations


import asyncio
import logging
import os
import platform
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class GatewayBootstrap:
    """
    Complete gateway bootstrap sequence matching TypeScript.
    
    Steps:
    1. Set environment variables
    2. Load and validate config
    3. Migrate legacy config if needed
    4. Start diagnostic heartbeat
    5. Initialize subagent registry
    6. Resolve default agent and workspace
    7. Load gateway plugins
    8. Create channel logs and runtime envs
    9. Resolve runtime config (bind, TLS, auth)
    10. Create default deps
    11. Create runtime state
    12. Build cron service
    13. Create channel manager
    14. Start discovery service
    15. Register skills change listener
    16. Start maintenance timers
    17. Register agent event handler
    18. Start heartbeat runner
    19. Start cron service
    20. Create exec approval manager
    21. Attach WebSocket handlers
    22. Log startup
    23. Start config reloader
    24. Create close handler
    """
    
    def __init__(self):
        self.config = None
        self.runtime = None
        self.session_manager = None
        self.server = None
        self.tool_registry = None
        self.channel_manager = None
        self.skill_loader = None
        self.cron_service = None
        self.discovery = None
        self.config_reloader = None
        self.heartbeat_stop = None
        self._maintenance_tasks: list[asyncio.Task] = []
        self._close_handlers: list[Any] = []
    
    async def bootstrap(self, config_path: Path | None = None, allow_unconfigured: bool = False) -> dict[str, Any]:
        """
        Run the full bootstrap sequence.
        
        Args:
            config_path: Optional path to configuration file
            allow_unconfigured: If True, continue even without config (for testing/dev)
        
        Returns:
            Dict with all initialized components
        """
        results = {"steps_completed": 0, "errors": []}
        
        # Pre-Step: Validate configuration exists (matches TS behavior)
        # Note: config_path is passed from CLI, defaults to openclaw.json not config.json
        if config_path:
            config_path_resolved = config_path
        else:
            # Check both possible config locations
            config_path_resolved = Path.home() / ".openclaw" / "openclaw.json"
            if not config_path_resolved.exists():
                config_path_resolved = Path.home() / ".openclaw" / "config.json"
        
        if not config_path_resolved.exists() and not allow_unconfigured:
            error_msg = (
                "Configuration not found. Please run onboarding first:\n"
                "  $ uv run openclaw onboard\n"
                "or use setup command:\n"
                "  $ uv run openclaw setup --wizard"
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        # Step 1: Set environment variables
        logger.info("Step 1: Setting environment variables")
        self._set_env_vars()
        results["steps_completed"] += 1
        
        # Step 2: Load and validate config
        logger.info("Step 2: Loading configuration")
        try:
            from ..config.loader import load_config
            self.config = load_config(config_path)
            results["steps_completed"] += 1
        except Exception as e:
            logger.error(f"Config load failed: {e}")
            results["errors"].append(f"config: {e}")
            return results
        
        # Step 3: Migrate legacy config
        logger.info("Step 3: Checking legacy config")
        try:
            from ..config.legacy import detect_legacy_config, migrate_legacy_config
            legacy = detect_legacy_config()
            if legacy:
                migrate_legacy_config(legacy)
                logger.info(f"Migrated legacy config from {legacy}")
        except Exception as e:
            logger.warning(f"Legacy migration skipped: {e}")
        results["steps_completed"] += 1
        
        # Step 3.5: Run gateway update check (writes ~/.openclaw/update-check.json)
        try:
            from ..infra.update_startup import run_gateway_update_check
            asyncio.ensure_future(run_gateway_update_check(self.config or {}))
        except Exception as exc:
            logger.debug("update-check: skipped: %s", exc)

        # Step 4: Start diagnostic heartbeat
        logger.info("Step 4: Starting diagnostic heartbeat")
        try:
            from ..infra.diagnostic_events import start_diagnostic_heartbeat
            start_diagnostic_heartbeat()
        except Exception as e:
            logger.warning(f"Diagnostic heartbeat failed: {e}")
        results["steps_completed"] += 1
        
        # Step 5: Initialize subagent registry
        logger.info("Step 5: Initializing subagent registry")
        # Subagent registry is lightweight - just a dict
        self._subagent_registry: dict[str, Any] = {}
        results["steps_completed"] += 1
        
        # Step 6: Resolve default agent and workspace
        logger.info("Step 6: Resolving default agent and workspace directory")
        
        # Use new agent scope functions (aligned with TS)
        try:
            from openclaw.agents.agent_scope import (
                resolve_default_agent_id,
                resolve_agent_workspace_dir,
            )
            
            default_agent_id = resolve_default_agent_id(self.config or {})
            workspace_dir = resolve_agent_workspace_dir(self.config or {}, default_agent_id)
            logger.info(f"Default agent: {default_agent_id}, workspace: {workspace_dir}")
        except Exception as e:
            logger.warning(f"Failed to use agent scope functions: {e}, falling back to default")
            # Fallback to legacy behavior
            if self.config and hasattr(self.config, 'agent') and hasattr(self.config.agent, 'workspace'):
                workspace_dir = Path(self.config.agent.workspace).expanduser().resolve()
            else:
                workspace_dir = Path.home() / ".openclaw" / "workspace"
        
        # Ensure workspace exists with bootstrap files (matching TypeScript behavior)
        try:
            from ..agents.ensure_workspace import ensure_agent_workspace
            skip_bootstrap = False
            if self.config and hasattr(self.config, 'agent'):
                skip_bootstrap = getattr(self.config.agent, 'skip_bootstrap', False)
            
            workspace_paths = ensure_agent_workspace(
                workspace_dir=workspace_dir,
                ensure_bootstrap_files=True,
                skip_bootstrap=skip_bootstrap,
            )
            logger.info(f"Workspace initialized: {workspace_dir}")
        except Exception as e:
            logger.warning(f"Failed to initialize workspace bootstrap files: {e}")
            workspace_dir.mkdir(parents=True, exist_ok=True)
        
        results["workspace_dir"] = str(workspace_dir)
        results["steps_completed"] += 1
        
        # Step 7: Load gateway plugins
        logger.info("Step 7: Loading gateway plugins")
        try:
            from ..plugins.plugin_manager import PluginManager
            plugin_manager = PluginManager()
            discovered = plugin_manager.discover_plugins()
            logger.info(f"Discovered {len(discovered)} plugins")
            self.plugin_registry = discovered  # Store for sidecar services
        except Exception as e:
            logger.warning(f"Plugin loading skipped: {e}")
            self.plugin_registry = {}
        results["steps_completed"] += 1
        
        # Step 7.5: Start gateway sidecar services (TS alignment)
        logger.info("Step 7.5: Starting gateway sidecar services")
        try:
            from .server_startup import start_gateway_sidecars
            
            sidecar_params = {
                "cfg": self.config.model_dump() if self.config else {},
                "plugin_registry": self.plugin_registry,
                "workspace_dir": workspace_dir,
                "default_workspace_dir": str(workspace_dir),
                "log_browser": logger,
                "log_hooks": logger,
                "deps": None,  # Will be set up later
            }
            
            sidecar_results = await start_gateway_sidecars(sidecar_params)
            results["sidecar_services"] = sidecar_results
            logger.info(f"Sidecar services initialized: {list(sidecar_results.keys())}")
        except Exception as e:
            logger.error(f"Failed to start sidecar services: {e}", exc_info=True)
            results["errors"].append(f"sidecar_services: {e}")
        results["steps_completed"] += 0.5
        
        # Step 8: Create agent runtime — uses pi_coding_agent.AgentSession
        logger.info("Step 8: Creating agent runtime (pi_coding_agent)")
        try:
            # Resolve model + fallbacks from config (mirrors TS agents.defaults.model)
            from openclaw.config.schema import ModelConfig as _ModelConfig
            primary_model = "google/gemini-2.0-flash"
            fallback_models: list[str] = []
            if self.config.agents and self.config.agents.defaults:
                raw_model = self.config.agents.defaults.model
                if isinstance(raw_model, _ModelConfig):
                    primary_model = raw_model.primary
                    fallback_models = list(raw_model.fallbacks or [])
                elif isinstance(raw_model, dict):
                    primary_model = raw_model.get("primary", primary_model)
                    fallback_models = list(raw_model.get("fallbacks", []))
                else:
                    primary_model = str(raw_model)

            logger.info(
                f"Creating PiAgentRuntime with model: {primary_model}"
                + (f" (fallbacks: {fallback_models})" if fallback_models else "")
            )

            from ..gateway.pi_runtime import PiAgentRuntime
            self.runtime = PiAgentRuntime(
                model=primary_model,
                fallback_models=fallback_models,
                cwd=workspace_dir,
                config=self.config.model_dump() if self.config else {},
            )

            # Also keep a legacy reference for any code that checks type
            self.provider = self.runtime

            # Extensions (non-critical, best-effort)
            try:
                from ..extensions.runtime import ExtensionRuntime
                from ..extensions.memory_extension import create_memory_extension
                from ..extensions.api import ExtensionAPI
                from ..extensions.types import ExtensionContext

                extension_runtime = ExtensionRuntime()
                extension_context = ExtensionContext(
                    agent_id="main",
                    session_id=None,
                    workspace_dir=workspace_dir,
                    logger=logger,
                )
                extension_runtime.set_context(extension_context)

                memory_enabled = getattr(self.config, "memory_enabled", True)
                if memory_enabled:
                    memory_config = {
                        "auto_recall": getattr(self.config, "memory_auto_recall", True),
                        "auto_capture": getattr(self.config, "memory_auto_capture", False),
                        "min_score": getattr(self.config, "memory_min_score", 0.3),
                        "max_results": getattr(self.config, "memory_max_results", 3),
                    }
                    memory_ext = create_memory_extension(workspace_dir, memory_config)
                    ext_api = ExtensionAPI(
                        extension_id="memory-extension",
                        context=extension_context,
                    )
                    memory_ext.register(ext_api)
                    extension_runtime.register_handlers(ext_api._handlers)
                    logger.info(f"Memory extension registered (auto_recall={memory_config['auto_recall']})")

                self.runtime.extension_runtime = extension_runtime  # type: ignore[attr-defined]
                logger.info("Extensions runtime initialized")
            except Exception as ext_err:
                logger.warning(f"Failed to initialize extensions: {ext_err}")

            logger.info("PiAgentRuntime created")
        except Exception as e:
            logger.error(f"Runtime creation failed: {e}")
            results["errors"].append(f"runtime: {e}")
        results["steps_completed"] += 1

        # Step 9: Create session manager
        logger.info("Step 9: Creating session manager")
        try:
            from ..agents.session import SessionManager
            self.session_manager = SessionManager(workspace_dir=workspace_dir)
        except Exception as e:
            logger.error(f"Session manager creation failed: {e}")
            results["errors"].append(f"session_manager: {e}")
        results["steps_completed"] += 1
        
        # Step 10: Create tool registry
        logger.info("Step 10: Creating tool registry")
        try:
            from ..agents.tools.registry import ToolRegistry
            self.tool_registry = ToolRegistry(
                session_manager=self.session_manager,
                auto_register=True,
            )
            
            # Register new tools
            from ..agents.tools.gateway import GatewayTool
            self.tool_registry.register(GatewayTool())
            
            # TODO: Add AgentsListTool and SessionStatusTool when available
            # from ..agents.tools.gateway import AgentsListTool, SessionStatusTool
            # self.tool_registry.register(AgentsListTool(config=self.config))
            # self.tool_registry.register(SessionStatusTool(session_manager=self.session_manager))
            
            tool_count = len(self.tool_registry.list_tools())
            logger.info(f"Registered {tool_count} tools")
        except Exception as e:
            logger.error(f"Tool registry creation failed: {e}")
            results["errors"].append(f"tool_registry: {e}")
        results["steps_completed"] += 1
        
        # Step 11: Load skills
        logger.info("Step 11: Loading skills")
        try:
            from ..skills.loader import SkillLoader
            
            # Get project root (where skills/ directory is)
            project_root = Path(__file__).parent.parent.parent
            bundled_skills_dir = project_root / "skills"
            
            # SkillLoader expects config dict
            skill_config = {}
            if self.config and hasattr(self.config, 'skills'):
                skill_config = self.config.skills.model_dump() if hasattr(self.config.skills, 'model_dump') else {}
            
            self.skill_loader = SkillLoader(config=skill_config)
            loaded_skills = self.skill_loader.load_from_directory(bundled_skills_dir, source="bundled")
            skill_count = len(loaded_skills)
            logger.info(f"Loaded {skill_count} skills from {bundled_skills_dir}")
        except Exception as e:
            logger.warning(f"Skills loading failed: {e}")
        results["steps_completed"] += 1
        
        # Step 11.5: Create broadcast function for events
        logger.info("Step 11.5: Creating broadcast function")
        
        # Event queue for events before WebSocket server is ready
        self._event_queue: list[tuple[str, Any, dict | None]] = []
        
        def broadcast(event: str, payload: Any, opts: dict | None = None) -> None:
            """Broadcast event to WebSocket clients"""
            if hasattr(self, 'server') and self.server:
                # WebSocket server is ready, broadcast immediately via async task
                try:
                    asyncio.ensure_future(self.server.broadcast_event(event, payload))
                except Exception as e:
                    logger.warning(f"Broadcast failed: {e}")
            else:
                # Queue event for later (server not yet ready)
                self._event_queue.append((event, payload, opts))
        
        self.broadcast = broadcast
        results["steps_completed"] += 0.5
        
        # Step 12: Build cron service (NOT started yet)
        logger.info("Step 12: Building cron service")
        try:
            from .cron_bootstrap import build_gateway_cron_service
            from .types import GatewayDeps
            
            # Build cron service with dependency container
            self.cron_service_state = await build_gateway_cron_service(
                config=self.config,
                deps=GatewayDeps(
                    provider=self.provider,
                    tools=self.tool_registry.list_tools() if self.tool_registry else [],
                    session_manager=self.session_manager,
                    get_channel_manager=lambda: getattr(self, 'channel_manager', None),  # Lazy access
                ),
                broadcast=broadcast,
            )
            self.cron_service = self.cron_service_state.cron

            # Register in global registry so handlers can find it via get_cron_service()
            from openclaw.cron.service import set_cron_service
            set_cron_service(self.cron_service)

            logger.info(f"Cron service initialized with {len(self.cron_service.jobs)} jobs (start deferred)")
        except Exception as e:
            logger.warning(f"Cron service initialization failed: {e}")
        results["steps_completed"] += 1
        
        # Step 13: Create channel manager and start channels
        logger.info("Step 13: Creating channel manager")
        try:
            from .channel_manager import ChannelManager
            self.channel_manager = ChannelManager(
                default_runtime=self.runtime,
                session_manager=self.session_manager,
                tools=self.tool_registry.list_tools() if self.tool_registry else [],
                workspace_dir=workspace_dir,
            )
            
            # Register and start enabled channels from config
            if self.config and self.config.channels:
                started_count = 0
                # Telegram
                if self.config.channels.telegram and self.config.channels.telegram.enabled:
                    try:
                        from ..channels.telegram import TelegramChannel
                        
                        # Step 1: Register channel class
                        self.channel_manager.register("telegram", TelegramChannel)
                        
                        # Step 2: Configure with botToken
                        channel_config = {
                            "botToken": self.config.channels.telegram.botToken,
                            "enabled": True,
                        }
                        self.channel_manager.configure("telegram", channel_config)
                        
                        # Step 3: Start channel (will use config from RuntimeEnv)
                        success = await self.channel_manager.start_channel("telegram")
                        if success:
                            started_count += 1
                            logger.info("✅ Telegram channel started")
                        else:
                            logger.warning("⚠️  Telegram channel start returned False")
                    except Exception as e:
                        logger.warning(f"❌ Failed to start Telegram channel: {e}")
                
                # Discord
                if self.config.channels.discord and self.config.channels.discord.enabled:
                    try:
                        from ..channels.discord import DiscordChannel
                        
                        # Step 1: Register
                        self.channel_manager.register("discord", DiscordChannel)
                        
                        # Step 2: Configure
                        channel_config = {
                            "token": self.config.channels.discord.token,
                            "enabled": True,
                        }
                        self.channel_manager.configure("discord", channel_config)
                        
                        # Step 3: Start
                        success = await self.channel_manager.start_channel("discord")
                        if success:
                            started_count += 1
                            logger.info("✅ Discord channel started")
                    except Exception as e:
                        logger.warning(f"❌ Failed to start Discord channel: {e}")
                
                logger.info(f"📊 Started {started_count} channels")
        except Exception as e:
            logger.error(f"Channel manager creation failed: {e}")
            results["errors"].append(f"channel_manager: {e}")
        results["steps_completed"] += 1
        
        # Step 13b: Start cron service (deferred until channel_manager is ready)
        if self.cron_service:
            try:
                await self.cron_service.start()
                logger.info("Cron service started")
            except Exception as e:
                logger.warning(f"Cron service start failed: {e}")

        # Step 14: Start discovery service
        logger.info("Step 14: Starting discovery service")
        # mDNS/Bonjour discovery is optional
        results["steps_completed"] += 1
        
        # Step 15: Register skills change listener
        logger.info("Step 15: Registering skills change listener")
        try:
            from ..agents.skills.refresh import register_skills_change_listener, ensure_skills_watcher
            
            def on_skills_change():
                logger.info("Skills changed, reloading...")
                if self.skill_loader:
                    self.skill_loader.load_all_skills()
            
            register_skills_change_listener(on_skills_change)
            
            # Watch skill directories
            skill_dirs = [
                Path(__file__).parent.parent / "skills",
                Path.home() / ".openclaw" / "skills",
                workspace_dir / "skills",
            ]
            for d in skill_dirs:
                if d.exists():
                    ensure_skills_watcher(d)
        except Exception as e:
            logger.warning(f"Skills watcher failed: {e}")
        results["steps_completed"] += 1
        
        # Step 16: Start maintenance timers
        logger.info("Step 16: Starting maintenance timers")
        self._start_maintenance_timers()
        results["steps_completed"] += 1
        
        # Step 17: Register event handlers
        logger.info("Step 17: Registering event handlers")
        # Event handlers are registered within the gateway server
        results["steps_completed"] += 1
        
        # Step 18: Start heartbeat runner
        logger.info("Step 18: Starting heartbeat runner")
        try:
            from ..infra.heartbeat_runner import start_heartbeat_runner
            agents_config = {}
            if self.config.agents and self.config.agents.agents:
                for agent in self.config.agents.agents:
                    agents_config[agent.id] = {"heartbeat": {"enabled": False}}
            
            if agents_config:
                self.heartbeat_stop = start_heartbeat_runner(
                    agents_config,
                    execute_fn=self._execute_heartbeat,
                )
        except Exception as e:
            logger.warning(f"Heartbeat runner failed: {e}")
        results["steps_completed"] += 1
        
        # Step 19: Set global handler instances
        logger.info("Step 19: Setting global handler instances")
        try:
            from .handlers import set_global_instances
            # gateway is created later in Step 22, so pass None here
            set_global_instances(
                self.session_manager,
                self.tool_registry,
                self.channel_manager,
                self.runtime,
                None  # wizard_handler will be set after server creation
            )
        except Exception as e:
            logger.debug(f"Handler globals setup (optional): {e}")
        results["steps_completed"] += 1
        
        # Step 20: Start config reloader
        logger.info("Step 20: Starting config reloader")
        try:
            from ..config.reloader import ConfigReloader
            from ..config.loader import get_config_path
            
            config_file = get_config_path()
            self.config_reloader = ConfigReloader(
                config_path=config_file,
                reload_fn=load_config,
            )
            self.config_reloader.start()
        except Exception as e:
            logger.warning(f"Config reloader failed: {e}")
        results["steps_completed"] += 1
        
        # Step 21: Log startup
        logger.info("Step 21: Logging startup")
        self._log_startup()
        results["steps_completed"] += 1
        
        # Step 22: Start WebSocket server
        logger.info("Step 22: Starting WebSocket server")
        try:
            from .server import GatewayServer
            port = self.config.gateway.port if self.config and self.config.gateway else 18789
            
            # Get tools list from registry
            tools = self.tool_registry.list_tools() if self.tool_registry else []
            
            self.server = GatewayServer(
                config=self.config,
                agent_runtime=self.runtime,
                session_manager=self.session_manager,
                tools=tools,
                system_prompt=None,  # Will be built from skills
                auto_discover_channels=False,  # We already created ChannelManager
            )
            
            # Pass bootstrap reference to server for accessing skill_loader
            self.server._bootstrap = self
            
            # Override the ChannelManager that GatewayServer created with our own
            # (since we already configured it in Step 13)
            self.server.channel_manager = self.channel_manager
            
            # Start server: launch as background task but wait briefly then
            # verify the port is actually bound before declaring success.
            # We must use create_task (not await) because server.start() runs
            # the aiohttp runner loop indefinitely. Instead we rely on the
            # server setting self.running = True once the site is up.
            import socket as _socket

            server_task = asyncio.create_task(self.server.start(start_channels=False))

            # Poll up to 3 s for the server to bind its port
            deadline = asyncio.get_event_loop().time() + 3.0
            bound = False
            while asyncio.get_event_loop().time() < deadline:
                await asyncio.sleep(0.1)
                # If the task already finished it must have failed
                if server_task.done():
                    exc = server_task.exception() if not server_task.cancelled() else None
                    if exc:
                        raise exc
                    break
                # Try a quick connect to see if the port is listening
                try:
                    with _socket.create_connection(("127.0.0.1", port), timeout=0.1):
                        bound = True
                        break
                except OSError:
                    continue

            if not bound and not server_task.done():
                # One final check — maybe loopback probe failed but server is up
                bound = getattr(self.server, "running", False)

            if not bound:
                server_task.cancel()
                raise OSError(f"Server failed to bind on port {port} within 3 s")

            logger.info(f"WebSocket server started on port {port}")
            results["gateway_port"] = port
            results["steps_completed"] += 1
        except Exception as e:
            logger.error(f"Server start failed: {e}")
            results["errors"].append(f"server_start: {e}")

        # Step 23: Initialize chat run state + dedupe tracker (m3)
        logger.info("Step 23: Initializing chat run state and deduplication tracker")
        try:
            from .chat_state import ChatRunRegistry
            self.chat_registry = ChatRunRegistry()
            if self.server:
                self.server.chat_registry = self.chat_registry
            logger.info("Chat run registry initialized")
        except Exception as e:
            logger.warning(f"Chat run state init failed: {e}")
        results["steps_completed"] += 1

        # Step 24: Initialize exec approval system (m5)
        logger.info("Step 24: Initializing exec approval system")
        try:
            from ..exec.approval_manager import ExecApprovalManager
            self.approval_manager = ExecApprovalManager()
            if self.server:
                self.server.approval_manager = self.approval_manager
            logger.info("Exec approval manager initialized")
        except Exception as e:
            logger.warning(f"Exec approval init failed: {e}")
        results["steps_completed"] += 1

        # Step 25: Run BOOT.md runner (m10)
        logger.info("Step 25: Running BOOT.md runner")
        try:
            await self._run_boot_once(workspace_dir)
        except Exception as e:
            logger.warning(f"BOOT.md runner failed: {e}")
        results["steps_completed"] += 1

        # Step 26: Write workspace-state.json (onboarding tracking)
        logger.info("Step 26: Updating workspace-state.json")
        try:
            import time as _time
            from ..wizard.onboarding import write_workspace_state
            write_workspace_state(
                workspace_dir,
                bootstrap_seeded_at=str(int(_time.time() * 1000)),
            )
        except Exception as e:
            logger.debug(f"workspace-state.json update skipped: {e}")
        results["steps_completed"] += 1

        logger.info(
            f"Bootstrap complete: {results['steps_completed']} steps, "
            f"{len(results['errors'])} errors"
        )

        return results

    async def _run_boot_once(self, workspace_dir: Path) -> None:
        """Delegate to gateway.boot.run_boot_once() via agent command.

        Mirrors TypeScript runBootOnce() — runs BOOT.md through the agent
        runtime (not shell code blocks).  The runtime may not be ready yet
        at this point in the bootstrap sequence, so failures are logged as
        debug and the boot-md hook will retry on gateway:startup.
        """
        from openclaw.gateway.boot import run_boot_once

        cfg = self.config or {}
        result = await run_boot_once(cfg=cfg, workspace_dir=workspace_dir)
        if result.status == "ran":
            logger.info("BOOT.md executed via agent command")
        elif result.status == "skipped":
            logger.debug("BOOT.md skipped: %s", result.reason)
        else:
            logger.debug("BOOT.md run result: %s — %s", result.status, result.reason)
    
    def _set_env_vars(self) -> None:
        """Set required environment variables.

        TS-aligned priority chain (highest → lowest):
          1. Process environment (already set — never overridden)
          2. CWD .env                      (developer convenience, via dotenv.py)
          3. ~/.openclaw/.env              (global user .env, via dotenv.py)
          4. openclaw.json ``env`` block   (applyConfigEnvVars)
          5. auth-profiles.json API keys   (set as GOOGLE_API_KEY etc.)
          6. Fallback: ~/.pi/agent/auth.json (pi_coding_agent legacy)

        Also ensures OPENCLAW_AGENT_DIR / PI_CODING_AGENT_DIR are set so that
        pi_coding_agent finds auth-profiles.json in the correct location.

        TS references:
          src/infra/dotenv.ts         → load_dot_env()
          src/config/env-vars.ts      → apply_config_env_vars()
          src/agents/agent-paths.ts   → ensure_agent_env()
          src/agents/model-auth.ts    → resolve_api_key()
        """
        if self.config and self.config.gateway:
            os.environ["OPENCLAW_GATEWAY_PORT"] = str(self.config.gateway.port)

        # ── Step 1-3: Load .env files (CWD + ~/.openclaw/.env) ───────────────
        try:
            from openclaw.infra.dotenv import load_dot_env
            load_dot_env(quiet=True)
        except Exception as exc:
            logger.debug("dotenv load skipped: %s", exc)

        # ── Step 4: Apply openclaw.json ``env`` block ─────────────────────────
        # Mirrors TS applyConfigEnvVars() — only sets vars not already present
        try:
            from openclaw.config.schema import EnvConfig
            env_block = self.config.env if self.config else None
            if env_block is not None:
                if isinstance(env_block, EnvConfig):
                    env_vars = env_block.get_all_vars()
                elif isinstance(env_block, dict):
                    env_vars = {
                        k: v for k, v in env_block.items()
                        if isinstance(v, str) and k not in ("shellEnv", "vars")
                    }
                    env_vars.update((env_block.get("vars") or {}))
                else:
                    env_vars = {}
                for key, value in env_vars.items():
                    if not os.environ.get(key):
                        os.environ[key] = value
                        logger.debug("Set %s from config env block", key)
        except Exception as exc:
            logger.debug("Config env block apply failed: %s", exc)

        # ── Step 5: Ensure OPENCLAW_AGENT_DIR / PI_CODING_AGENT_DIR are set ──
        # Mirrors TS ensureOpenClawAgentEnv() — pi_coding_agent uses this to
        # locate auth-profiles.json.
        try:
            from openclaw.config.auth_profiles import ensure_agent_env
            agent_dir = ensure_agent_env()
            logger.debug("OPENCLAW_AGENT_DIR=%s", agent_dir)
        except Exception as exc:
            logger.debug("ensure_agent_env failed: %s", exc)

        # ── Step 6: Load API keys from auth-profiles.json → env vars ─────────
        # Mirrors TS: gateway startup reads auth-profiles.json and makes API
        # keys available to the runtime (which checks env vars first).
        _PROVIDER_ENV: dict[str, list[str]] = {
            "google":    ["GOOGLE_API_KEY", "GEMINI_API_KEY"],
            "anthropic": ["ANTHROPIC_API_KEY"],
            "openai":    ["OPENAI_API_KEY"],
        }
        try:
            from openclaw.config.auth_profiles import get_api_key as _get_key
            for provider, env_names in _PROVIDER_ENV.items():
                if os.environ.get(env_names[0]):
                    continue  # already set from .env or shell
                key = _get_key(provider)
                if key:
                    for name in env_names:
                        os.environ[name] = key
                    logger.info("Loaded %s API key from auth-profiles.json → %s",
                                provider, env_names[0])
        except Exception as exc:
            logger.debug("auth-profiles.json key loading failed: %s", exc)

        # ── Step 7: Fallback — pi_coding_agent legacy ~/.pi/agent/auth.json ──
        _PROVIDER_ENV_LEGACY: dict[str, list[str]] = {
            "google":    ["GOOGLE_API_KEY", "GEMINI_API_KEY"],
            "anthropic": ["ANTHROPIC_API_KEY"],
            "openai":    ["OPENAI_API_KEY"],
        }
        try:
            from pi_coding_agent.core.auth_storage import AuthStorage
            storage = AuthStorage()
            for provider, env_names in _PROVIDER_ENV_LEGACY.items():
                if os.environ.get(env_names[0]):
                    continue
                key = storage.get_api_key(provider)
                if key:
                    for name in env_names:
                        os.environ[name] = key
                    logger.debug("Loaded %s from legacy ~/.pi/agent/auth.json", provider)
        except Exception:
            pass
    
    def _start_maintenance_timers(self) -> None:
        """Start maintenance timer tasks"""
        
        async def session_cleanup():
            """Periodic session cleanup"""
            while True:
                try:
                    await asyncio.sleep(3600)  # Every hour
                    logger.debug("Running session cleanup")
                    # Cleanup old sessions
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Session cleanup error: {e}")
        
        async def health_check():
            """Periodic health check"""
            while True:
                try:
                    await asyncio.sleep(60)  # Every minute
                    # Check component health
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Health check error: {e}")
        
        self._maintenance_tasks.append(asyncio.create_task(session_cleanup()))
        self._maintenance_tasks.append(asyncio.create_task(health_check()))
    
    async def _execute_heartbeat(self, agent_id: str, prompt: str) -> str | None:
        """Execute heartbeat for an agent"""
        if not self.runtime or not self.session_manager:
            return None
        
        session = self.session_manager.get_session(f"heartbeat-{agent_id}")
        tools = self.tool_registry.list_tools() if self.tool_registry else []
        
        response = ""
        async for event in self.runtime.run_turn(session, prompt, tools):
            if hasattr(event, 'text') and event.text:
                response += event.text
        
        return response if response else None
    
    def _log_startup(self) -> None:
        """Log gateway startup information"""
        port = self.config.gateway.port if self.config and self.config.gateway else 18789
        
        logger.info("=" * 60)
        logger.info(f"OpenClaw Gateway Started")
        logger.info(f"  Platform: {platform.system()} {platform.machine()}")
        logger.info(f"  Python: {platform.python_version()}")
        logger.info(f"  Port: {port}")
        if self.config and self.config.agents and self.config.agents.defaults:
            logger.info(f"  Model: {self.config.agents.defaults.model}")
        if self.tool_registry:
            logger.info(f"  Tools: {len(self.tool_registry.list_tools())}")
        if self.skill_loader:
            logger.info(f"  Skills: {len(self.skill_loader.skills)}")
        logger.info("=" * 60)
    
    async def shutdown(self) -> None:
        """Graceful shutdown"""
        logger.info("Gateway shutting down...")
        
        # Stop Gateway server first (this stops WebSocket connections)
        if hasattr(self, 'server') and self.server:
            try:
                await self.server.stop()
            except Exception as e:
                logger.error(f"Gateway server stop error: {e}")
        
        # Stop heartbeat
        if self.heartbeat_stop:
            self.heartbeat_stop()
        
        # Stop maintenance timers
        for task in self._maintenance_tasks:
            try:
                task.cancel()
                # Give tasks a moment to cancel
                await asyncio.sleep(0.1)
            except Exception:
                pass
        
        # Stop config reloader
        if self.config_reloader:
            try:
                self.config_reloader.stop()
            except Exception:
                pass
        
        # Stop skills watchers
        try:
            from ..agents.skills.refresh import stop_all_watchers
            stop_all_watchers()
        except Exception:
            pass
        
        # Stop diagnostic heartbeat
        try:
            from ..infra.diagnostic_events import stop_diagnostic_heartbeat
            stop_diagnostic_heartbeat()
        except Exception:
            pass
        
        logger.info("Gateway shutdown complete")
