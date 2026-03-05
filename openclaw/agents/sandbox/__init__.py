"""Docker sandbox system for isolated code execution

Matches TypeScript openclaw/src/agents/sandbox/
"""

from .docker import (
    DockerSandbox,
    DockerSandboxConfig,
    exec_docker,
    ensure_docker_image,
    docker_container_state,
)
from .constants import DEFAULT_SANDBOX_IMAGE, SANDBOX_AGENT_WORKSPACE_MOUNT
from .config_hash import compute_sandbox_config_hash
from .registry import SandboxRegistry, get_sandbox_registry
from .fs_bridge import SandboxFsBridge, SandboxFsStat, SandboxResolvedPath, create_sandbox_fs_bridge
from .context import (
    SandboxContext,
    SandboxToolPolicy,
    SandboxBrowserContext,
    SandboxWorkspaceInfo,
    resolve_sandbox_context,
    get_sandbox_workspace_info,
    resolve_sandbox_scope_key,
    resolve_sandbox_workspace_dir,
)
from .validate_security import (
    validate_sandbox_security,
    validate_bind_mounts,
    validate_network_mode,
    validate_seccomp_profile,
    validate_apparmor_profile,
    get_blocked_bind_reason,
    BLOCKED_HOST_PATHS,
)
# New modules — TS alignment
from .runtime_status import (
    resolve_sandbox_runtime_status,
    format_sandbox_tool_policy_blocked_message,
)
from .sanitize_env_vars import (
    sanitize_env_vars,
    EnvVarSanitizationResult,
    get_blocked_patterns,
    get_allowed_patterns,
)
from .tool_policy import (
    is_tool_allowed,
    resolve_sandbox_tool_policy_for_agent,
    DEFAULT_SANDBOX_TOOL_ALLOW,
    DEFAULT_SANDBOX_TOOL_DENY,
)
from .config import (
    ResolvedSandboxConfig,
    ResolvedSandboxDockerConfig,
    ResolvedSandboxBrowserConfig,
    ResolvedSandboxPruneConfig,
    resolve_sandbox_config_for_agent,
)
from .manage import (
    SandboxContainerInfo,
    list_sandbox_containers,
    remove_sandbox_container,
    ensure_docker_container_is_running,
)
from .prune import (
    maybe_prune_sandboxes,
    should_prune_sandbox_entry,
)
from .workspace import ensure_sandbox_workspace

__all__ = [
    # docker
    "DockerSandbox",
    "DockerSandboxConfig",
    "exec_docker",
    "ensure_docker_image",
    "docker_container_state",
    # constants
    "DEFAULT_SANDBOX_IMAGE",
    "SANDBOX_AGENT_WORKSPACE_MOUNT",
    # config_hash
    "compute_sandbox_config_hash",
    # registry
    "SandboxRegistry",
    "get_sandbox_registry",
    # fs_bridge
    "SandboxFsBridge",
    "SandboxFsStat",
    "SandboxResolvedPath",
    "create_sandbox_fs_bridge",
    # context
    "SandboxContext",
    "SandboxToolPolicy",
    "SandboxBrowserContext",
    "SandboxWorkspaceInfo",
    "resolve_sandbox_context",
    "get_sandbox_workspace_info",
    "resolve_sandbox_scope_key",
    "resolve_sandbox_workspace_dir",
    # security
    "validate_sandbox_security",
    "validate_bind_mounts",
    "validate_network_mode",
    "validate_seccomp_profile",
    "validate_apparmor_profile",
    "get_blocked_bind_reason",
    "BLOCKED_HOST_PATHS",
    # runtime_status (P1 — fixes live broken import)
    "resolve_sandbox_runtime_status",
    "format_sandbox_tool_policy_blocked_message",
    # sanitize_env_vars (P1 — security)
    "sanitize_env_vars",
    "EnvVarSanitizationResult",
    "get_blocked_patterns",
    "get_allowed_patterns",
    # tool_policy
    "is_tool_allowed",
    "resolve_sandbox_tool_policy_for_agent",
    "DEFAULT_SANDBOX_TOOL_ALLOW",
    "DEFAULT_SANDBOX_TOOL_DENY",
    # config
    "ResolvedSandboxConfig",
    "ResolvedSandboxDockerConfig",
    "ResolvedSandboxBrowserConfig",
    "ResolvedSandboxPruneConfig",
    "resolve_sandbox_config_for_agent",
    # manage
    "SandboxContainerInfo",
    "list_sandbox_containers",
    "remove_sandbox_container",
    "ensure_docker_container_is_running",
    # prune
    "maybe_prune_sandboxes",
    "should_prune_sandbox_entry",
    # workspace
    "ensure_sandbox_workspace",
]
