"""
Channel Manager - Manages channel plugins within Gateway

This implements the TypeScript OpenClaw architecture where:
- Gateway contains ChannelManager
- ChannelManager manages all channel plugins
- Each channel can have its own RuntimeEnv (Agent configuration)
- Channels connect to Agent Runtime via function calls (not HTTP/WebSocket)

Architecture:
    Gateway Server
        └── ChannelManager
                ├── Telegram Channel (plugin)
                ├── Discord Channel (plugin)
                └── ... other channels
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from ..agents.runtime import AgentRuntime
from ..channels.base import ChannelPlugin, InboundMessage, MessageHandler
from ..events import Event, EventType

# =============================================================================
# Channel Restart Policy — mirrors TS CHANNEL_RESTART_POLICY
# =============================================================================

MAX_RESTART_ATTEMPTS = 10

CHANNEL_RESTART_POLICY = {
    "initial_delay_ms": 5_000,    # 5 s initial backoff
    "max_delay_ms": 300_000,       # 5 min max backoff
    "backoff_factor": 2.0,
}


def _compute_backoff_ms(attempt: int) -> float:
    """Compute backoff delay in ms for a given restart attempt (1-indexed)."""
    initial = CHANNEL_RESTART_POLICY["initial_delay_ms"]
    factor = CHANNEL_RESTART_POLICY["backoff_factor"]
    max_delay = CHANNEL_RESTART_POLICY["max_delay_ms"]
    delay = initial * (factor ** (attempt - 1))
    return min(delay, max_delay)


# Channel event type constants
class ChannelEventType:
    """Channel-specific event types"""
    REGISTERED = "registered"
    UNREGISTERED = "unregistered"
    STARTING = "starting"
    STARTED = "started"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"

logger = logging.getLogger(__name__)


async def _transcribe_audio_attachment(
    content: str,
    mime: str,
    filename: str,
    config: dict,
) -> str | None:
    """Decode a base64 audio attachment and transcribe it using the configured STT provider.

    Mirrors TS media-understanding/audio-preflight.ts transcribeFirstAudio().
    Returns the transcript text or None if unavailable/disabled.

    Provider priority:
    1. config.tools.media.audio (explicit configuration)
    2. OpenAI Whisper (if OPENAI_API_KEY or config.providers.openai.apiKey present)
    3. Groq Whisper (if GROQ_API_KEY present)
    """
    import base64
    import os
    import tempfile

    # Check explicit audio config
    audio_cfg = ((config.get("tools") or {}).get("media") or {}).get("audio") or {}
    if audio_cfg.get("enabled") is False:
        return None

    explicit_provider = (audio_cfg.get("provider") or "").lower()
    explicit_api_key = audio_cfg.get("apiKey") or ""

    # Resolve provider + api key
    api_key: str | None = None
    provider_name: str | None = None

    if explicit_provider and explicit_api_key:
        provider_name = explicit_provider
        api_key = explicit_api_key
    else:
        # Auto-detect from env / global provider config
        openai_key = (
            explicit_api_key
            or ((config.get("providers") or {}).get("openai") or {}).get("apiKey")
            or os.environ.get("OPENAI_API_KEY")
        )
        if openai_key:
            provider_name = "openai"
            api_key = openai_key
        else:
            groq_key = (
                ((config.get("providers") or {}).get("groq") or {}).get("apiKey")
                or os.environ.get("GROQ_API_KEY")
            )
            if groq_key:
                provider_name = "groq"
                api_key = groq_key

    if not provider_name or not api_key:
        # Last resort: check env vars and model provider config
        openai_key = os.environ.get("OPENAI_API_KEY", "")
        if not openai_key:
            # Try to get from model providers config (e.g. models.openai.apiKey)
            for section in ("models", "providers"):
                openai_key = (
                    (config.get(section) or {}).get("openai", {}).get("apiKey")
                    or (config.get(section) or {}).get("openai", {}).get("api_key")
                    or ""
                )
                if openai_key:
                    break
        if openai_key:
            provider_name = "openai"
            api_key = openai_key
        else:
            logger.debug(
                "_transcribe_audio_attachment: no STT provider configured "
                "(set OPENAI_API_KEY or add tools.media.audio to openclaw.json)"
            )
            return None

    # Decode base64 content
    try:
        audio_bytes = base64.b64decode(content)
    except Exception as exc:
        logger.warning(f"_transcribe_audio_attachment: base64 decode failed: {exc}")
        return None

    # Determine file extension from MIME or filename
    if filename and "." in filename:
        ext = "." + filename.rsplit(".", 1)[-1]
    else:
        _mime_to_ext: dict[str, str] = {
            "audio/ogg": ".ogg",
            "audio/mpeg": ".mp3",
            "audio/mp4": ".m4a",
            "audio/wav": ".wav",
            "audio/webm": ".webm",
            "audio/flac": ".flac",
        }
        ext = _mime_to_ext.get((mime or "").split(";")[0].strip(), ".ogg")

    # Write to temp file and transcribe
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        if provider_name == "openai":
            from openclaw.media_understanding.providers.openai_provider import OpenAIAudioProvider
            stt = OpenAIAudioProvider(api_key=api_key)
        elif provider_name == "groq":
            from openclaw.media_understanding.providers.groq_provider import (
                GroqAudioProvider,  # type: ignore[import]
            )
            stt = GroqAudioProvider(api_key=api_key)
        elif provider_name == "deepgram":
            from openclaw.media_understanding.providers.deepgram_provider import (
                DeepgramProvider,  # type: ignore[import]
            )
            stt = DeepgramProvider(api_key=api_key)
        else:
            return None

        result = await stt.transcribe(tmp_path)
        transcript = (result.get("text") or "").strip()
        return transcript or None

    except Exception as exc:
        logger.warning(f"_transcribe_audio_attachment: transcription error: {exc}")
        return None
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


class ChannelState(str, Enum):
    """Channel lifecycle state"""

    REGISTERED = "registered"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class ChannelRuntimeEnv:
    """
    Runtime environment for a channel

    Each channel can have its own:
    - Agent Runtime (or share a default)
    - Configuration
    - Message handler

    This mirrors TypeScript's channelRuntimeEnvs concept.
    """

    channel_id: str
    agent_runtime: AgentRuntime | None = None
    config: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True

    # Optional custom message handler
    custom_message_handler: MessageHandler | None = None

    # Runtime state
    state: ChannelState = ChannelState.REGISTERED
    error: str | None = None
    started_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "channel_id": self.channel_id,
            "enabled": self.enabled,
            "state": self.state.value,
            "error": self.error,
            "started_at": self.started_at,
            "has_custom_runtime": self.agent_runtime is not None,
            "has_custom_handler": self.custom_message_handler is not None,
        }


# Type for event listener callbacks
ChannelEventListener = Callable[[str, str, dict[str, Any]], Awaitable[None]]


class ChannelManager:
    """
    Manages channel plugins within Gateway

    This is the central component for channel lifecycle management,
    matching the TypeScript OpenClaw architecture.

    Features:
    - Register channel plugin classes or instances
    - Start/stop channels individually or all at once
    - Each channel can have independent configuration (RuntimeEnv)
    - Automatic message routing to Agent Runtime
    - Event emission for channel state changes

    Example:
        # Create manager with default agent runtime
        manager = ChannelManager(default_runtime=agent_runtime)

        # Register channel classes
        manager.register("telegram", EnhancedTelegramChannel)
        manager.register("discord", EnhancedDiscordChannel)

        # Configure channels
        manager.configure("telegram", {
            "bot_token": "...",
            "enabled": True
        })

        # Start specific channel
        await manager.start_channel("telegram")

        # Or start all enabled channels
        await manager.start_all()

        # Stop all
        await manager.stop_all()
    """

    def __init__(
        self,
        default_runtime: AgentRuntime | None = None,
        session_manager: Any = None,
        tools: list | None = None,
        system_prompt: str | None = None,
        workspace_dir: Path | None = None,
    ):
        """
        Initialize ChannelManager

        Args:
            default_runtime: Default AgentRuntime for channels that don't have their own
            session_manager: Session manager for creating/retrieving sessions
            tools: List of tools available to the agent
            system_prompt: Optional system prompt (skills, capabilities, etc.)
            workspace_dir: Workspace directory for bootstrap files
        """
        self.default_runtime = default_runtime
        self.session_manager = session_manager
        # Normalise: accept either a ToolRegistry object or a plain list of tools
        # (TS ChannelManager receives a plain array — we mirror that internally)
        if tools is None:
            self.tools = []
        elif hasattr(tools, "list_tools"):
            self.tools = tools.list_tools()
        else:
            self.tools = list(tools)
        self.workspace_dir = workspace_dir or Path.home() / ".openclaw" / "workspace"

        # Load bootstrap files and build complete system prompt
        self.system_prompt = self._build_system_prompt_with_bootstrap(system_prompt)

        # Channel plugin classes (for lazy instantiation)
        self._channel_classes: dict[str, type[ChannelPlugin]] = {}

        # Channel plugin instances
        self._channels: dict[str, ChannelPlugin] = {}

        # Runtime environments per channel
        self._runtime_envs: dict[str, ChannelRuntimeEnv] = {}

        # Event listeners
        self._event_listeners: list[ChannelEventListener] = []

        # Restart tracking — mirrors TS restartAttempts Map
        # Key: channel_id (or "channel_id:account_id" for multi-account)
        self._restart_attempts: dict[str, int] = {}

        # Channels that were manually stopped — suppress auto-restart
        # Mirrors TS manuallyStopped Set
        self._manually_stopped: set[str] = set()

        # Per-channel background tasks (for abort on stop)
        self._channel_tasks: dict[str, asyncio.Task] = {}

        # Running state
        self._running = False

        logger.info("ChannelManager initialized")

    def _build_system_prompt_with_bootstrap(self, base_prompt: str | None = None) -> str:
        """
        Build complete system prompt with bootstrap files injected.
        
        Matches TypeScript behavior: loads SOUL.md, IDENTITY.md, BOOTSTRAP.md, etc.
        and injects them into the system prompt.
        
        Args:
            base_prompt: Base system prompt (if any)
            
        Returns:
            Complete system prompt with bootstrap files
        """
        try:
            from ..agents.system_prompt import build_agent_system_prompt
            from ..agents.system_prompt_bootstrap import (
                format_bootstrap_context,
                format_bootstrap_context_string,
                load_bootstrap_files,
            )
            from ..agents.system_prompt_params import build_system_prompt_params

            # Load bootstrap files from workspace
            bootstrap_files = load_bootstrap_files(self.workspace_dir)
            logger.info(f"Loaded {len(bootstrap_files)} bootstrap files from {self.workspace_dir}")

            # Format as string for injection
            bootstrap_context = format_bootstrap_context_string(bootstrap_files)

            # If there's a base prompt, append bootstrap context
            if base_prompt:
                if bootstrap_context:
                    return f"{base_prompt}\n\n{bootstrap_context}"
                return base_prompt

            # Otherwise, build complete system prompt with bootstrap files
            tool_names = [tool.name for tool in self.tools] if self.tools else []

            # Get model name from default_runtime if available
            model_name = "unknown"
            if self.default_runtime and hasattr(self.default_runtime, 'model_str'):
                model_name = self.default_runtime.model_str

            # Get complete runtime parameters (includes timezone, runtime_info, etc.)
            # Load config so the configured timezone (agents.defaults.timezone) is used.
            try:
                from openclaw.config.loader import load_config
                _cfg = load_config()
            except Exception:
                _cfg = None
            prompt_params = build_system_prompt_params(
                config=_cfg,
                workspace_dir=self.workspace_dir,
                runtime={
                    "agent_id": "main",
                    "channel": "gateway",
                    "model": model_name,
                    "default_model": model_name,
                }
            )

            # Build complete system prompt with resolved parameters
            system_prompt = build_agent_system_prompt(
                workspace_dir=self.workspace_dir,
                tool_names=tool_names,
                prompt_mode="full",
                runtime_info=prompt_params["runtime_info"],  # Complete runtime info
                user_timezone=prompt_params["user_timezone"],  # Resolved timezone
                context_files=format_bootstrap_context([
                    bf for bf in bootstrap_files
                    if "(File" not in bf.content
                ]) if bootstrap_files else None,
            )

            logger.info(f"Built system prompt with bootstrap files ({len(system_prompt)} chars)")
            logger.info(f"Using timezone: {prompt_params['user_timezone']}")
            return system_prompt

        except Exception as e:
            logger.error(f"Failed to build system prompt with bootstrap: {e}", exc_info=True)
            # Fallback to base prompt or default
            return base_prompt or "You are a personal assistant running inside OpenClaw."

    # =========================================================================
    # Registration
    # =========================================================================

    def register(
        self,
        channel_id: str,
        channel_class: type[ChannelPlugin],
        config: dict[str, Any] | None = None,
        runtime: AgentRuntime | None = None,
    ) -> None:
        """
        Register a channel plugin class

        The channel will be instantiated lazily when needed.

        Args:
            channel_id: Unique identifier for the channel
            channel_class: Channel plugin class
            config: Optional initial configuration
            runtime: Optional custom AgentRuntime for this channel
        """
        self._channel_classes[channel_id] = channel_class

        # Create runtime environment
        self._runtime_envs[channel_id] = ChannelRuntimeEnv(
            channel_id=channel_id,
            agent_runtime=runtime,
            config=config or {},
            enabled=True,
        )

        logger.info(f"Registered channel class: {channel_id}")
        asyncio.create_task(self._emit_event(ChannelEventType.REGISTERED, channel_id, {}))

    def register_instance(
        self,
        channel: ChannelPlugin,
        config: dict[str, Any] | None = None,
        runtime: AgentRuntime | None = None,
    ) -> None:
        """
        Register a channel plugin instance directly

        Args:
            channel: Channel plugin instance
            config: Optional initial configuration
            runtime: Optional custom AgentRuntime for this channel
        """
        if not channel.id:
            raise ValueError("Channel must have an ID")

        self._channels[channel.id] = channel

        # Create runtime environment
        self._runtime_envs[channel.id] = ChannelRuntimeEnv(
            channel_id=channel.id,
            agent_runtime=runtime,
            config=config or {},
            enabled=True,
        )

        logger.info(f"Registered channel instance: {channel.id}")
        asyncio.create_task(self._emit_event("registered", channel.id, {}))

    def unregister(self, channel_id: str) -> bool:
        """
        Unregister a channel

        The channel will be stopped if running.

        Args:
            channel_id: Channel to unregister

        Returns:
            True if unregistered, False if not found
        """
        if channel_id not in self._channel_classes and channel_id not in self._channels:
            return False

        # Remove from all registries
        self._channel_classes.pop(channel_id, None)
        self._channels.pop(channel_id, None)
        self._runtime_envs.pop(channel_id, None)

        logger.info(f"Unregistered channel: {channel_id}")
        asyncio.create_task(self._emit_event(ChannelEventType.UNREGISTERED, channel_id, {}))
        return True

    # =========================================================================
    # Configuration
    # =========================================================================

    def configure(
        self,
        channel_id: str,
        config: dict[str, Any],
        merge: bool = True,
    ) -> None:
        """
        Configure a channel

        Args:
            channel_id: Channel to configure
            config: Configuration dictionary
            merge: If True, merge with existing config; otherwise replace
        """
        if channel_id not in self._runtime_envs:
            # Auto-create runtime env if channel class exists
            if channel_id in self._channel_classes:
                self._runtime_envs[channel_id] = ChannelRuntimeEnv(channel_id=channel_id)
            else:
                raise ValueError(f"Channel not registered: {channel_id}")

        env = self._runtime_envs[channel_id]

        if merge:
            env.config.update(config)
        else:
            env.config = config

        # Handle special config keys
        if "enabled" in config:
            env.enabled = config["enabled"]

        logger.debug(f"Configured channel {channel_id}: {config}")

    def set_default_runtime(self, runtime: AgentRuntime) -> None:
        """
        Replace the default AgentRuntime used for all channels without an explicit
        per-channel runtime.  Mirrors TS ChannelManager.setDefaultRuntime().

        Args:
            runtime: New default AgentRuntime instance.
        """
        self.default_runtime = runtime
        logger.info("Default channel runtime updated")

    def set_runtime(self, channel_id: str, runtime: AgentRuntime) -> None:
        """
        Set custom AgentRuntime for a channel

        Args:
            channel_id: Channel ID
            runtime: Custom AgentRuntime
        """
        if channel_id not in self._runtime_envs:
            raise ValueError(f"Channel not registered: {channel_id}")

        self._runtime_envs[channel_id].agent_runtime = runtime
        logger.info(f"Set custom runtime for channel: {channel_id}")

    def set_message_handler(self, channel_id: str, handler: MessageHandler) -> None:
        """
        Set custom message handler for a channel

        This overrides the default Agent Runtime handler.

        Args:
            channel_id: Channel ID
            handler: Custom message handler
        """
        if channel_id not in self._runtime_envs:
            raise ValueError(f"Channel not registered: {channel_id}")

        self._runtime_envs[channel_id].custom_message_handler = handler
        logger.info(f"Set custom message handler for channel: {channel_id}")

    # =========================================================================
    # Lifecycle Management
    # =========================================================================

    async def start_channel(self, channel_id: str) -> bool:
        """
        Start a specific channel

        Args:
            channel_id: Channel to start

        Returns:
            True if started successfully
        """
        env = self._runtime_envs.get(channel_id)
        if not env:
            logger.error(f"Channel not found: {channel_id}")
            return False

        if not env.enabled:
            logger.info(f"Channel disabled, skipping: {channel_id}")
            return False

        # Get or create channel instance
        channel = self._get_or_create_channel(channel_id)
        if not channel:
            return False

        try:
            env.state = ChannelState.STARTING
            await self._emit_event(ChannelEventType.STARTING, channel_id, {})

            # Set up message handler
            handler = self._create_message_handler(channel_id)
            channel.set_message_handler(handler)

            # Start channel with config
            await channel.start(env.config)

            env.state = ChannelState.RUNNING
            env.error = None

            from datetime import datetime

            env.started_at = datetime.now().isoformat()

            logger.info(f"✅ Channel started: {channel_id}")
            await self._emit_event(ChannelEventType.STARTED, channel_id, {})
            return True

        except Exception as e:
            env.state = ChannelState.ERROR
            env.error = str(e)
            logger.error(f"❌ Failed to start channel {channel_id}: {e}")
            await self._emit_event(ChannelEventType.ERROR, channel_id, {"error": str(e)})
            return False

    async def _start_channel_with_backoff(self, channel_id: str) -> None:
        """Start a channel and automatically restart it with backoff on failure.

        Mirrors TS startChannelInternal() restart logic in server-channels.ts.
        Runs as a background task; exits when manually stopped or max retries reached.
        """
        rkey = channel_id
        self._manually_stopped.discard(rkey)
        self._restart_attempts.pop(rkey, None)

        while True:
            success = await self.start_channel(channel_id)

            # Wait for channel to finish (it runs until stopped or errors)
            channel = self._channels.get(channel_id)
            if channel and hasattr(channel, "_running"):
                # Poll until channel stops running or is manually stopped
                try:
                    while channel._running and rkey not in self._manually_stopped:
                        await asyncio.sleep(1.0)
                except asyncio.CancelledError:
                    break

            if rkey in self._manually_stopped:
                logger.debug(f"Channel {channel_id} manually stopped — not restarting")
                break

            attempt = self._restart_attempts.get(rkey, 0) + 1
            self._restart_attempts[rkey] = attempt

            if attempt > MAX_RESTART_ATTEMPTS:
                logger.error(
                    f"Channel {channel_id} giving up after {MAX_RESTART_ATTEMPTS} restart attempts"
                )
                break

            delay_ms = _compute_backoff_ms(attempt)
            delay_s = delay_ms / 1000.0
            logger.info(
                f"Channel {channel_id} auto-restart attempt {attempt}/{MAX_RESTART_ATTEMPTS} "
                f"in {delay_s:.1f}s"
            )

            try:
                await asyncio.sleep(delay_s)
            except asyncio.CancelledError:
                break

            if rkey in self._manually_stopped:
                break

    async def stop_channel(self, channel_id: str) -> bool:
        """
        Stop a specific channel

        Args:
            channel_id: Channel to stop

        Returns:
            True if stopped successfully
        """
        # Mark as manually stopped to suppress auto-restart
        self._manually_stopped.add(channel_id)
        self._restart_attempts.pop(channel_id, None)

        # Cancel the background task if running
        task = self._channel_tasks.pop(channel_id, None)
        if task and not task.done():
            task.cancel()

        channel = self._channels.get(channel_id)
        if not channel:
            logger.warning(f"Channel not found or not started: {channel_id}")
            return False

        env = self._runtime_envs.get(channel_id)
        if env:
            env.state = ChannelState.STOPPING

        await self._emit_event(ChannelEventType.STOPPING, channel_id, {})

        try:
            await channel.stop()

            if env:
                env.state = ChannelState.STOPPED

            logger.info(f"Channel stopped: {channel_id}")
            await self._emit_event(ChannelEventType.STOPPED, channel_id, {})
            return True

        except Exception as e:
            if env:
                env.state = ChannelState.ERROR
                env.error = str(e)
            logger.error(f"Failed to stop channel {channel_id}: {e}")
            await self._emit_event(ChannelEventType.ERROR, channel_id, {"error": str(e)})
            return False

    async def restart_channel(self, channel_id: str) -> bool:
        """
        Restart a channel

        Args:
            channel_id: Channel to restart

        Returns:
            True if restarted successfully
        """
        await self.stop_channel(channel_id)
        return await self.start_channel(channel_id)

    async def start_all(self) -> dict[str, bool]:
        """Start all enabled channels, with auto-restart backoff in background.

        Mirrors TS startChannels() — launches each enabled channel in a background
        task that automatically restarts with exponential backoff on failure.

        Returns:
            Dict mapping channel_id to initial start success status
        """
        self._running = True
        results: dict[str, bool] = {}

        for channel_id, env in self._runtime_envs.items():
            if not env.enabled:
                continue

            # Start the channel once to get immediate feedback
            ok = await self.start_channel(channel_id)
            results[channel_id] = ok

            # Launch background task for auto-restart management
            # The task monitors the channel and restarts it with backoff
            if ok:
                self._manually_stopped.discard(channel_id)
                task = asyncio.create_task(
                    self._monitor_channel_for_restart(channel_id),
                    name=f"channel-monitor-{channel_id}",
                )
                self._channel_tasks[channel_id] = task

        return results

    async def _monitor_channel_for_restart(self, channel_id: str) -> None:
        """Background task: monitor a running channel and restart it with backoff.

        Runs continuously until the channel is manually stopped or max retries exceeded.
        Mirrors TS trackedPromise restart loop in server-channels.ts.
        """
        rkey = channel_id
        while True:
            channel = self._channels.get(channel_id)

            # Wait until channel stops running
            try:
                while (
                    channel is not None
                    and getattr(channel, "_running", False)
                    and rkey not in self._manually_stopped
                ):
                    await asyncio.sleep(2.0)
                    channel = self._channels.get(channel_id)
            except asyncio.CancelledError:
                return

            if rkey in self._manually_stopped:
                return

            # Channel stopped unexpectedly — attempt restart with backoff
            attempt = self._restart_attempts.get(rkey, 0) + 1
            self._restart_attempts[rkey] = attempt

            if attempt > MAX_RESTART_ATTEMPTS:
                logger.error(
                    f"Channel {channel_id}: giving up after {MAX_RESTART_ATTEMPTS} restart attempts"
                )
                return

            delay_ms = _compute_backoff_ms(attempt)
            delay_s = delay_ms / 1000.0
            logger.info(
                f"Channel {channel_id}: auto-restart attempt {attempt}/{MAX_RESTART_ATTEMPTS} "
                f"in {delay_s:.1f}s"
            )

            env = self._runtime_envs.get(channel_id)
            if env:
                env.state = ChannelState.STOPPED

            try:
                await asyncio.sleep(delay_s)
            except asyncio.CancelledError:
                return

            if rkey in self._manually_stopped:
                return

            await self.start_channel(channel_id)

    async def stop_all(self) -> None:
        """Stop all running channels, cancelling auto-restart tasks."""
        self._running = False

        # Cancel all background monitor tasks
        for channel_id, task in list(self._channel_tasks.items()):
            if not task.done():
                task.cancel()
        self._channel_tasks.clear()

        for channel_id, channel in list(self._channels.items()):
            if channel.is_running():
                await self.stop_channel(channel_id)

    # =========================================================================
    # Query Methods
    # =========================================================================

    def get_channel(self, channel_id: str) -> ChannelPlugin | None:
        """Get channel instance by ID"""
        return self._channels.get(channel_id)

    def get_runtime_env(self, channel_id: str) -> ChannelRuntimeEnv | None:
        """Get runtime environment for a channel"""
        return self._runtime_envs.get(channel_id)

    def get_runtime(self, channel_id: str) -> AgentRuntime | None:
        """
        Get AgentRuntime for a channel

        Returns channel-specific runtime if set, otherwise default runtime.
        """
        env = self._runtime_envs.get(channel_id)
        if env and env.agent_runtime:
            return env.agent_runtime
        return self.default_runtime

    def list_channels(self) -> list[str]:
        """List all registered channel IDs"""
        all_ids = set(self._channel_classes.keys())
        all_ids.update(self._channels.keys())
        return sorted(all_ids)

    def list_running(self) -> list[str]:
        """List running channel IDs"""
        return [ch_id for ch_id, ch in self._channels.items() if ch.is_running()]

    def list_enabled(self) -> list[str]:
        """List enabled channel IDs"""
        return [ch_id for ch_id, env in self._runtime_envs.items() if env.enabled]

    def get_runtime_snapshot(self) -> dict[str, dict[str, Any]]:
        """Return runtime status snapshot for all channels.

        Mirrors TS getRuntimeSnapshot() in server-channels.ts.
        """
        snapshot: dict[str, dict[str, Any]] = {}
        for channel_id in self.list_channels():
            env = self._runtime_envs.get(channel_id)
            channel = self._channels.get(channel_id)
            snap: dict[str, Any] = {
                "channel_id": channel_id,
                "enabled": env.enabled if env else False,
                "configured": True,
                "running": channel.is_running() if channel else False,
                "state": env.state.value if env else "registered",
                "last_error": env.error if env else None,
                "started_at": env.started_at if env else None,
                "reconnect_attempts": self._restart_attempts.get(channel_id, 0),
                "manually_stopped": channel_id in self._manually_stopped,
            }
            snapshot[channel_id] = snap
        return snapshot

    def get_all_channels(self) -> list[dict[str, Any]]:
        """
        Get all channels with full details
        
        Returns list of channel info dicts with:
        - id: channel ID
        - label: channel label
        - running: whether channel is running
        - connected: whether channel is connected
        - healthy: whether channel is healthy
        - state: channel state
        - enabled: whether channel is enabled
        - capabilities: channel capabilities
        """
        channels = []
        for channel_id in self.list_channels():
            channel = self._channels.get(channel_id)
            env = self._runtime_envs.get(channel_id)

            channel_info = {
                "id": channel_id,
                "enabled": env.enabled if env else False,
                "state": env.state.value if env else "unknown",
            }

            if channel:
                channel_info.update({
                    "label": channel.label,
                    "running": channel.is_running(),
                    "connected": channel.is_connected(),
                    "healthy": channel.is_healthy(),
                    "capabilities": channel.capabilities.model_dump(),
                })
            else:
                # Channel class registered but not instantiated
                channel_info.update({
                    "label": channel_id,
                    "running": False,
                    "connected": False,
                    "healthy": False,
                    "capabilities": {},
                })

            channels.append(channel_info)

        return channels

    def get_status(self, channel_id: str) -> dict[str, Any] | None:
        """Get channel status"""
        channel = self._channels.get(channel_id)
        env = self._runtime_envs.get(channel_id)

        if not env:
            return None

        result = env.to_dict()

        if channel:
            result.update(
                {
                    "running": channel.is_running(),
                    "connected": channel.is_connected(),
                    "healthy": channel.is_healthy(),
                    "label": channel.label,
                    "capabilities": channel.capabilities.model_dump(),
                }
            )

            metrics = channel.get_metrics()
            if metrics:
                result["metrics"] = metrics.to_dict()

        return result

    def get_all_status(self) -> dict[str, Any]:
        """Get status of all channels"""
        channels = {}
        for channel_id in self.list_channels():
            status = self.get_status(channel_id)
            if status:
                channels[channel_id] = status

        return {
            "running": self._running,
            "total": len(channels),
            "running_count": len(self.list_running()),
            "enabled_count": len(self.list_enabled()),
            "channels": channels,
        }

    # =========================================================================
    # Event System
    # =========================================================================

    def add_event_listener(self, listener: ChannelEventListener) -> None:
        """Add event listener for channel events"""
        self._event_listeners.append(listener)

    def remove_event_listener(self, listener: ChannelEventListener) -> None:
        """Remove event listener"""
        if listener in self._event_listeners:
            self._event_listeners.remove(listener)

    async def _emit_event(
        self,
        event_type_str: str,
        channel_id: str,
        data: dict[str, Any],
    ) -> None:
        """
        Emit channel event to all listeners using unified Event system

        Args:
            event_type_str: String event type (e.g., "registered", "started")
            channel_id: Channel ID
            data: Event data
        """
        # Map string event type to EventType enum
        event_type_map = {
            "registered": EventType.CHANNEL_REGISTERED,
            "unregistered": EventType.CHANNEL_UNREGISTERED,
            "starting": EventType.CHANNEL_STARTING,
            "started": EventType.CHANNEL_STARTED,
            "ready": EventType.CHANNEL_READY,
            "stopping": EventType.CHANNEL_STOPPING,
            "stopped": EventType.CHANNEL_STOPPED,
            "error": EventType.CHANNEL_ERROR,
        }

        event_type = event_type_map.get(event_type_str, EventType.CHANNEL_ERROR)

        # Create unified Event
        event = Event(type=event_type, source="channel-manager", channel_id=channel_id, data=data)

        # Notify legacy listeners (for backward compatibility)
        for listener in self._event_listeners:
            try:
                await listener(event_type_str, channel_id, data)
            except Exception as e:
                logger.error(f"Event listener error: {e}")

    # =========================================================================
    # Internal Methods
    # =========================================================================

    def _get_or_create_channel(self, channel_id: str) -> ChannelPlugin | None:
        """Get existing channel or create from class"""
        if channel_id in self._channels:
            return self._channels[channel_id]

        if channel_id in self._channel_classes:
            channel_class = self._channel_classes[channel_id]
            channel = channel_class()
            self._channels[channel_id] = channel
            return channel

        return None

    def _create_message_handler(self, channel_id: str) -> MessageHandler:
        """
        Create message handler for a channel

        This is where the magic happens:
        - Builds complete MsgContext from InboundMessage
        - Normalizes and finalizes context (sender metadata, mention gating, etc.)
        - Gets the appropriate AgentRuntime (channel-specific or default)
        - Creates a handler that processes messages through the Agent
        - Sends responses back via the channel
        """

        async def handler(message: InboundMessage) -> None:
            env = self._runtime_envs.get(channel_id)

            # Check for custom handler first
            if env and env.custom_message_handler:
                await env.custom_message_handler(message)
                return

            # Get runtime
            runtime = self.get_runtime(channel_id)
            if not runtime:
                logger.error(f"No AgentRuntime available for channel: {channel_id}")
                return

            # Get channel for sending response
            channel = self._channels.get(channel_id)
            if not channel:
                logger.error(f"Channel not found: {channel_id}")
                return

            logger.info(f"📨 [{channel_id}] Message from {message.sender_name}: {message.text}")

            try:
                # Build MsgContext from InboundMessage
                from openclaw.auto_reply.inbound_context import (
                    MsgContext,
                    finalize_inbound_context,
                )

                # Build proper session key (align with TypeScript format)
                from openclaw.routing.session_key import build_agent_peer_session_key

                # Determine peer_kind based on chat_type
                peer_kind = "dm" if message.chat_type == "dm" else message.chat_type or "dm"

                # Build session key: agent:main:telegram:dm:8366053063
                session_key = build_agent_peer_session_key(
                    agent_id=self.session_manager.agent_id if self.session_manager else "main",
                    channel=channel_id,
                    peer_kind=peer_kind,
                    peer_id=str(message.chat_id),
                    dm_scope="per-channel-peer"  # Each channel+peer gets own session
                )

                logger.info(f"[{channel_id}] Built session key: {session_key}")

                # Propagate command metadata from InboundMessage (set by command_dispatcher.py)
                _meta = message.metadata or {}
                _command_authorized = bool(_meta.get("command_authorized", False))
                _command_body = _meta.get("command_body") or message.text or ""
                _command_source = _meta.get("command_source") or (
                    "native" if _meta.get("event_type") == "command" else None
                )

                ctx = MsgContext(
                    Body=message.text or "",
                    RawBody=message.text or "",
                    BodyForAgent=_command_body or message.text or "",
                    CommandBody=_command_body or message.text or "",
                    SessionKey=session_key,  # Use proper session key
                    From=message.sender_id,
                    To=channel_id,
                    ChatType=message.chat_type,
                    SenderName=message.sender_name,
                    SenderId=message.sender_id,
                    ConversationLabel=f"{channel_id}:{message.chat_id}",
                    OriginatingChannel=channel_id,
                    OriginatingTo=message.chat_id,
                    CommandAuthorized=_command_authorized,
                    CommandSource=_command_source,  # type: ignore[call-arg]
                )

                # Add reply context if present
                if message.reply_to:
                    ctx.ReplyToId = message.reply_to

                # Add media metadata if present (legacy URL-based path)
                if message.metadata:
                    media_url = message.metadata.get("file_url") or message.metadata.get("photo_url")
                    if media_url:
                        ctx.MediaUrls = [media_url]
                        ctx.MediaUrl = media_url

                # Finalize context (applies normalization, sender metadata, etc.)
                ctx = finalize_inbound_context(ctx)

                logger.debug(f"[{channel_id}] Context finalized: BodyForAgent length={len(ctx.BodyForAgent or '')}, ChatType={ctx.ChatType}")

                # Get or create session using session key (will query store for UUID)
                session = None
                session_workspace: str | None = None
                workspace_root: str | None = str(Path.home() / ".openclaw" / "workspace")
                if self.session_manager:
                    session = self.session_manager.get_or_create_session_by_key(session_key)
                    logger.info(f"[{channel_id}] Session created/retrieved: key={session_key}, uuid={session.session_id}")

                    # Resolve session workspace for file generation
                    from openclaw.agents.session_workspace import resolve_session_workspace_dir
                    _workspace_root = session.workspace_dir if session else Path.home() / ".openclaw" / "workspace"
                    session_workspace = str(resolve_session_workspace_dir(
                        workspace_root=_workspace_root,
                        session_key=session_key
                    ))
                    workspace_root = str(_workspace_root)
                    logger.info(f"[{channel_id}] Session workspace: {session_workspace}")

                # Use BodyForAgent (properly formatted with sender metadata for groups)
                message_text = ctx.BodyForAgent or ctx.Body

                logger.info(f"[{channel_id}] Starting dispatch with {len(self.tools)} tools")

                from openclaw.auto_reply.reply.typing import create_typing_controller

                # Wire up typing indicator (mirrors TS bot-message-dispatch.ts)
                _typing_target = str(message.chat_id)
                async def _send_typing() -> None:
                    if hasattr(channel, "send_typing"):
                        try:
                            await channel.send_typing(_typing_target)
                        except Exception:
                            pass

                typing_ctrl = create_typing_controller(on_reply_start=_send_typing)
                await typing_ctrl.on_reply_start()
                await typing_ctrl.start_typing_loop()

                # Build image data URLs from inbound attachments, and transcribe audio.
                # Mirrors TS bot-message-context.ts allMedia / audio-preflight flow.
                inbound_images: list[str] | None = None
                inbound_attachments = getattr(message, "attachments", None) or []
                for att in inbound_attachments:
                    # att is a ChatAttachment Pydantic model — access via attributes, not .get()
                    if isinstance(att, dict):
                        mime = att.get("mime_type") or att.get("mimeType") or ""
                        content = att.get("content") or ""
                        att_type = att.get("type") or ""
                        filename = att.get("filename") or att.get("file_name") or ""
                    else:
                        mime = att.mime_type or ""
                        content = att.content or ""
                        att_type = att.type or ""
                        filename = getattr(att, "filename", "") or getattr(att, "file_name", "") or ""
                    if content and (att_type == "image" or mime.startswith("image/")):
                        if inbound_images is None:
                            inbound_images = []
                        inbound_images.append(f"data:{mime or 'image/jpeg'};base64,{content}")
                    elif content and (att_type in ("voice", "audio") or mime.startswith("audio/")):
                        # Audio/voice attachment — transcribe and replace placeholder text.
                        # Mirrors TS audio-preflight.ts transcribeFirstAudio().
                        try:
                            _audio_cfg: dict = {}
                            try:
                                from openclaw.config.loader import load_config as _lc
                                _raw_cfg = _lc()
                                if hasattr(_raw_cfg, "model_dump"):
                                    _audio_cfg = _raw_cfg.model_dump()
                                elif isinstance(_raw_cfg, dict):
                                    _audio_cfg = _raw_cfg
                            except Exception:
                                pass
                            audio_transcript = await _transcribe_audio_attachment(
                                content=content,
                                mime=mime,
                                filename=filename or "voice.ogg",
                                config=_audio_cfg,
                            )
                            if audio_transcript:
                                message_text = audio_transcript
                                logger.info(
                                    f"[{channel_id}] Audio transcription: {len(audio_transcript)} chars"
                                )
                        except Exception as _audio_err:
                            logger.warning(
                                f"[{channel_id}] Audio transcription failed: {_audio_err}"
                            )

                # Build a channel send function for the ReplyContext
                async def _channel_send(
                    text: str | None,
                    target: Any,
                    *,
                    reply_to: Any = None,
                    media_url: str | None = None,
                    media_type: str | None = None,
                    **_kw: Any,
                ) -> None:
                    if media_url:
                        await channel.send_media(
                            target=target,
                            media_url=media_url,
                            media_type=media_type or "document",
                            reply_to=reply_to,
                        )
                    elif text:
                        await channel.send_text(
                            target=target,
                            text=text,
                            reply_to=reply_to,
                        )

                # Resolve session_id for active-run tracking
                session_id_for_run = session.session_id if session else session_key

                # Resolve queue settings from session entry
                from openclaw.auto_reply.reply.queue import QueueSettings
                _queue_settings = QueueSettings()
                if self.session_manager:
                    try:
                        _entry = self.session_manager.get_session_entry(session_key)
                        if _entry and hasattr(_entry, "queueMode") and _entry.queueMode:
                            _queue_settings.mode = _entry.queueMode
                    except Exception:
                        pass

                # Build ReplyContext and dispatch via pipeline
                # (steer / enqueue-followup / interrupt / run-now)
                from openclaw.auto_reply.reply.agent_runner import ReplyContext, run_prepared_reply

                reply_ctx = ReplyContext(
                    session_id=session_id_for_run,
                    session_key=session_key,
                    message_text=message_text,
                    runtime=runtime,
                    session=session,
                    tools=self.tools,
                    channel_send=_channel_send,
                    chat_target=message.chat_id,
                    channel_id=channel_id,
                    reply_to_id=message.message_id,
                    queue_settings=_queue_settings,
                    images=inbound_images,
                    system_prompt=self.system_prompt,
                    originating_channel=channel_id,
                    originating_to=message.chat_id,
                    typing_ctrl=typing_ctrl,
                )

                # Fire-and-forget: handler returns immediately.
                # run_prepared_reply handles steer/queue/run logic and will
                # call typing_ctrl.mark_run_complete() / mark_dispatch_idle()
                # on its own when the turn finishes.
                asyncio.ensure_future(run_prepared_reply(reply_ctx))

            except Exception as e:
                try:
                    typing_ctrl.cleanup()
                except Exception:
                    pass
                logger.error(f"Error dispatching message: {e}", exc_info=True)
                try:
                    await channel.send_text(
                        target=message.chat_id,
                        text=f"Sorry, I encountered an error: {str(e)[:100]}",
                    )
                except Exception:
                    pass

        return handler

    def to_dict(self) -> dict[str, Any]:
        """Convert manager to dictionary"""
        return self.get_all_status()


# ============================================================================
# Plugin Discovery
# ============================================================================


def discover_channel_plugins() -> dict[str, type[ChannelPlugin]]:
    """
    Discover available channel plugin classes

    This scans the channels module and returns all available plugin classes.

    Returns:
        Dict mapping channel_id to plugin class
    """
    from ..channels import (
        DiscordChannel,
        EnhancedDiscordChannel,
        EnhancedTelegramChannel,
        SlackChannel,
        TelegramChannel,
        WebChatChannel,
    )

    # Try to import optional channels
    plugins: dict[str, type[ChannelPlugin]] = {}

    # Core channels (always available)
    core_channels = [
        ("telegram", TelegramChannel),
        ("telegram-enhanced", EnhancedTelegramChannel),
        ("discord", DiscordChannel),
        ("discord-enhanced", EnhancedDiscordChannel),
        ("slack", SlackChannel),
        ("webchat", WebChatChannel),
    ]

    for channel_id, channel_class in core_channels:
        try:
            # Verify it's a valid channel
            instance = channel_class()
            actual_id = instance.id or channel_id
            plugins[actual_id] = channel_class
            logger.debug(f"Discovered channel plugin: {actual_id}")
        except Exception as e:
            logger.debug(f"Could not load channel {channel_id}: {e}")

    # Try to load additional optional channels
    optional_channels = [
        ("whatsapp", "WhatsAppChannel"),
        ("signal", "SignalChannel"),
        ("matrix", "MatrixChannel"),
        ("teams", "TeamsChannel"),
        ("line", "LineChannel"),
        ("imessage", "iMessageChannel"),
    ]

    for channel_id, class_name in optional_channels:
        try:
            module = __import__(f"openclaw.channels.{channel_id}", fromlist=[class_name])
            channel_class = getattr(module, class_name, None)
            if channel_class:
                instance = channel_class()
                actual_id = instance.id or channel_id
                plugins[actual_id] = channel_class
                logger.debug(f"Discovered optional channel: {actual_id}")
        except Exception:
            pass  # Optional channel not available

    return plugins


def load_channel_plugins(
    config: dict[str, Any] | None = None,
) -> dict[str, type[ChannelPlugin]]:
    """
    Load channel plugins based on configuration

    Args:
        config: Optional config dict with channel settings
               {"channels": {"telegram": {"enabled": true}, ...}}

    Returns:
        Dict of enabled channel plugins
    """
    all_plugins = discover_channel_plugins()

    if not config:
        return all_plugins

    # Filter by config
    channels_config = config.get("channels", {})

    enabled_plugins = {}
    for channel_id, plugin_class in all_plugins.items():
        channel_config = channels_config.get(channel_id, {})

        # Default to enabled if not specified
        if channel_config.get("enabled", True):
            enabled_plugins[channel_id] = plugin_class

    return enabled_plugins
