"""Gateway services manager - hooks, restart sentinel, etc."""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class RestartSentinel:
    """Handles SIGUSR1 restart signals and restart requests"""
    
    def __init__(self, restart_callback: Callable):
        self.restart_callback = restart_callback
        self.restart_requested = False
    
    def setup_signal_handler(self) -> None:
        """Setup SIGUSR1 signal handler"""
        try:
            signal.signal(signal.SIGUSR1, self._handle_sigusr1)
            logger.info("SIGUSR1 restart handler installed")
        except AttributeError:
            # SIGUSR1 not available on Windows
            logger.debug("SIGUSR1 not available on this platform")
    
    def _handle_sigusr1(self, signum, frame) -> None:
        """Handle SIGUSR1 signal"""
        logger.info("Received SIGUSR1, requesting restart...")
        self.request_restart()
    
    def request_restart(self) -> None:
        """Request a restart"""
        self.restart_requested = True
        asyncio.create_task(self.restart_callback())
    
    def check_restart_requested(self) -> bool:
        """Check if restart was requested"""
        return self.restart_requested


class InternalHooksManager:
    """Manages internal hooks"""
    
    def __init__(self, workspace_dir: Optional[Path] = None):
        self.workspace_dir = workspace_dir
        self.hooks: dict[str, list[Callable]] = {}
    
    async def load_hooks(self) -> None:
        """Load internal hooks"""
        logger.info("Loading internal hooks...")
        
        if not self.workspace_dir:
            return
        
        hooks_dir = self.workspace_dir / "hooks"
        if not hooks_dir.exists():
            logger.debug(f"Hooks directory not found: {hooks_dir}")
            return
        
        # TODO: Load hook modules from hooks_dir
        # For now, just log
        logger.info(f"Hooks directory: {hooks_dir}")
    
    def register_hook(self, event: str, callback: Callable) -> None:
        """Register a hook for an event"""
        if event not in self.hooks:
            self.hooks[event] = []
        self.hooks[event].append(callback)
    
    async def trigger_hook(self, event: str, data: Any = None) -> None:
        """Trigger hooks for an event"""
        if event not in self.hooks:
            return
        
        for callback in self.hooks[event]:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
            except Exception as e:
                logger.error(f"Hook error for {event}: {e}")


class ServicesManager:
    """Manages all gateway services"""
    
    def __init__(self, gateway_server):
        self.gateway = gateway_server
        self.restart_sentinel: Optional[RestartSentinel] = None
        self.hooks_manager: Optional[InternalHooksManager] = None
    
    async def start_services(self) -> None:
        """Start all services"""
        logger.info("Starting gateway services...")
        
        # Restart sentinel
        self.restart_sentinel = RestartSentinel(self._handle_restart)
        self.restart_sentinel.setup_signal_handler()
        
        # Internal hooks
        workspace_dir = getattr(self.gateway.config.agent, "workspace", None)
        if workspace_dir:
            self.hooks_manager = InternalHooksManager(Path(workspace_dir))
            await self.hooks_manager.load_hooks()
        
        logger.info("✅ Gateway services started")
    
    async def stop_services(self) -> None:
        """Stop all services"""
        logger.info("Stopping gateway services...")
        # Services cleanup happens in shutdown handler
        logger.info("✅ Gateway services stopped")
    
    async def _handle_restart(self) -> None:
        """Handle restart request — mirrors TS run-loop.ts SIGUSR1 handler.

        Steps:
        1. Mark gateway as draining (reject new enqueues).
        2. Wait for active tasks to finish (30s timeout).
        3. Reset all lanes.
        4. Stop services, then re-exec the process.
        """
        logger.info("Restart requested, initiating graceful restart...")

        # Step 1+2: Drain queues
        try:
            from openclaw.agents.queuing.queue import QueueManager
            from openclaw.gateway.handlers import _queue_manager

            if _queue_manager is not None:
                _queue_manager.mark_gateway_draining()
                drain_result = await _queue_manager.wait_for_active_tasks(timeout_ms=30_000)
                if drain_result.get("drained"):
                    logger.info("All active tasks drained before restart")
                else:
                    logger.warning("Timed out waiting for active tasks — proceeding with restart")
                _queue_manager.reset_all_lanes()
                _queue_manager.unmark_gateway_draining()
        except Exception as exc:
            logger.warning("Queue drain during restart failed: %s", exc)

        # Step 3: Stop services
        await self.stop_services()

        # Step 4: Re-exec process
        logger.info("Re-executing process for in-place restart...")
        try:
            os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception as exc:
            logger.error("Re-exec failed: %s — falling back to in-process restart", exc)


__all__ = ["ServicesManager", "RestartSentinel", "InternalHooksManager"]
