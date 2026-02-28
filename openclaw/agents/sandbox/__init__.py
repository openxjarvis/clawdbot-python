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

__all__ = [
    "DockerSandbox",
    "DockerSandboxConfig",
    "exec_docker",
    "ensure_docker_image",
    "docker_container_state",
    "DEFAULT_SANDBOX_IMAGE",
    "SANDBOX_AGENT_WORKSPACE_MOUNT",
    "compute_sandbox_config_hash",
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
]
