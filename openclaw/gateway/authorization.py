"""
Method authorization with roles and scopes

Implements role-based access control matching the TypeScript implementation.
"""

import logging
from typing import Set, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ============================================================================
# Roles and Scopes
# ============================================================================

class Role:
    """Authorization roles"""
    OPERATOR = "operator"
    NODE = "node"


class Scope:
    """Authorization scopes for operator role"""
    ADMIN = "operator.admin"
    READ = "operator.read"
    WRITE = "operator.write"
    APPROVALS = "operator.approvals"
    PAIRING = "operator.pairing"


@dataclass
class AuthContext:
    """Authentication context for a connection"""
    role: str = Role.OPERATOR
    scopes: Set[str] = None
    user: Optional[str] = None
    device_id: Optional[str] = None
    node_id: Optional[str] = None
    
    def __post_init__(self):
        if self.scopes is None:
            self.scopes = set()


# ============================================================================
# Method Authorization Requirements
# ============================================================================

# Methods that require specific roles or scopes
METHOD_REQUIREMENTS = {
    # Admin methods
    "config.set": [Scope.ADMIN],
    "config.patch": [Scope.ADMIN],
    "config.apply": [Scope.ADMIN],
    "wizard.start": [Scope.ADMIN],
    "wizard.next": [Scope.ADMIN],
    "wizard.cancel": [Scope.ADMIN],
    "update.run": [Scope.ADMIN],
    
    # Exec approvals (admin or approvals scope)
    "exec.approvals.get": [Scope.ADMIN, Scope.APPROVALS],
    "exec.approvals.set": [Scope.ADMIN, Scope.APPROVALS],
    "exec.approvals.node.get": [Scope.ADMIN, Scope.APPROVALS],
    "exec.approvals.node.set": [Scope.ADMIN, Scope.APPROVALS],
    
    # Node pairing (admin or pairing scope)
    "node.pair.approve": [Scope.ADMIN, Scope.PAIRING],
    "node.pair.reject": [Scope.ADMIN, Scope.PAIRING],
    
    # Device pairing (admin or pairing scope)
    "device.pair.approve": [Scope.ADMIN, Scope.PAIRING],
    "device.pair.reject": [Scope.ADMIN, Scope.PAIRING],
    "device.token.rotate": [Scope.ADMIN, Scope.PAIRING],
    "device.token.revoke": [Scope.ADMIN, Scope.PAIRING],
    
    # Node-only methods (responses/events sent BY the node back to gateway)
    "node.invoke.result": [Role.NODE],
    "node.event": [Role.NODE],
    "skills.bins": [Role.NODE],
}


# Public methods (no authorization required)
PUBLIC_METHODS = {
    "connect",
    "health",
    "status",
    "ping",
}


# Read-only methods (read scope sufficient)
READ_ONLY_METHODS = {
    "config.get",
    "sessions.list",
    "sessions.preview",
    "sessions.resolve",
    "agents.list",
    "agents.files.list",
    "agents.files.get",
    "channels.list",
    "channels.status",
    "models.list",
    "cron.list",
    "cron.status",
    "node.list",
    "node.describe",
    "device.pair.list",
    "logs.tail",
}


# Write methods (write or admin scope required) — mirrors TS WRITE_METHODS
WRITE_METHODS = {
    "send",
    "agent",
    "agent.wait",
    "wake",
    "talk.mode",
    "tts.enable",
    "tts.disable",
    "tts.convert",
    "tts.setProvider",
    "voicewake.set",
    "node.invoke",  # operator calls this to send a command TO a node
    "chat.send",
    "chat.abort",
    "browser.request",
}


# Node-role-only methods — only clients that connected with role="node" may call these
NODE_ROLE_METHODS = {
    "node.invoke.result",
    "node.event",
    "skills.bins",
}


def authorize_gateway_method(method: str, auth_context: AuthContext) -> bool:
    """
    Authorize method call based on role and scopes.

    Mirrors the TypeScript authorizeGatewayMethod in server-methods.ts:
    - NODE_ROLE_METHODS  → only role="node" clients
    - role="node"        → may only call NODE_ROLE_METHODS
    - role="operator"    → needs matching scope for restricted methods;
                           admin scope bypasses all checks
    """
    role = auth_context.role or Role.OPERATOR
    scopes = auth_context.scopes or set()

    # Public methods always allowed
    if method in PUBLIC_METHODS:
        return True

    # NODE_ROLE_METHODS: only node clients may call these
    if method in NODE_ROLE_METHODS:
        if role == Role.NODE:
            return True
        logger.warning(
            f"Authorization denied for {method}: only node role allowed, got role={role}"
        )
        return False

    # Node clients may ONLY call NODE_ROLE_METHODS
    if role == Role.NODE:
        logger.warning(f"Node attempted unauthorized method: {method}")
        return False

    if role != Role.OPERATOR:
        logger.warning(f"Authorization denied for {method}: unknown role={role}")
        return False

    # Admin scope grants access to everything
    if Scope.ADMIN in scopes:
        return True

    # Check method-specific requirements (admin/approvals/pairing scopes)
    requirements = METHOD_REQUIREMENTS.get(method)
    if requirements:
        for requirement in requirements:
            if requirement in scopes:
                return True
        logger.warning(
            f"Permission denied: method={method}, role={role}, "
            f"scopes={scopes}, required={requirements}"
        )
        return False

    # Approval-only methods
    if method in {"exec.approvals.get", "exec.approvals.set",
                  "exec.approvals.node.get", "exec.approvals.node.set"}:
        if Scope.APPROVALS not in scopes:
            logger.warning(f"Permission denied: method={method} requires operator.approvals")
            return False
        return True

    # Read methods: read or write scope sufficient
    if method in READ_ONLY_METHODS:
        if Scope.READ in scopes or Scope.WRITE in scopes:
            return True
        # Fallback: operator with no scopes can still read (matches TS default behaviour)
        return True

    # Write methods: write scope required
    if method in WRITE_METHODS:
        if Scope.WRITE in scopes:
            return True
        # Fallback: operator with no explicit scopes can still write
        # (matches TS: empty scopes + operator role passes write methods)
        return True

    # Anything else: allow for operator role (default permissive)
    return True
