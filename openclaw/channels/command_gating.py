"""Command gating logic — mirrors src/channels/command-gating.ts"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CommandGatingModeWhenAccessGroupsOff = Literal["allow", "deny", "configured"]


@dataclass
class CommandAuthorizer:
    configured: bool
    allowed: bool


def resolve_command_authorized_from_authorizers(
    *,
    use_access_groups: bool,
    authorizers: list[CommandAuthorizer],
    mode_when_access_groups_off: CommandGatingModeWhenAccessGroupsOff = "allow",
) -> bool:
    if not use_access_groups:
        if mode_when_access_groups_off == "allow":
            return True
        if mode_when_access_groups_off == "deny":
            return False
        any_configured = any(a.configured for a in authorizers)
        if not any_configured:
            return True
        return any(a.configured and a.allowed for a in authorizers)
    return any(a.configured and a.allowed for a in authorizers)


def resolve_control_command_gate(
    *,
    use_access_groups: bool,
    authorizers: list[CommandAuthorizer],
    allow_text_commands: bool,
    has_control_command: bool,
    mode_when_access_groups_off: CommandGatingModeWhenAccessGroupsOff = "allow",
) -> dict:
    command_authorized = resolve_command_authorized_from_authorizers(
        use_access_groups=use_access_groups,
        authorizers=authorizers,
        mode_when_access_groups_off=mode_when_access_groups_off,
    )
    should_block = allow_text_commands and has_control_command and not command_authorized
    return {"commandAuthorized": command_authorized, "shouldBlock": should_block}
