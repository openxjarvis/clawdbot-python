"""Mention gating logic — mirrors src/channels/mention-gating.ts"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MentionGateResult:
    effective_was_mentioned: bool
    should_skip: bool


@dataclass
class MentionGateWithBypassResult(MentionGateResult):
    should_bypass_mention: bool


def resolve_mention_gating(
    *,
    require_mention: bool,
    can_detect_mention: bool,
    was_mentioned: bool,
    implicit_mention: bool = False,
    should_bypass_mention: bool = False,
) -> MentionGateResult:
    effective = was_mentioned or implicit_mention or should_bypass_mention
    should_skip = require_mention and can_detect_mention and not effective
    return MentionGateResult(
        effective_was_mentioned=effective,
        should_skip=should_skip,
    )


def resolve_mention_gating_with_bypass(
    *,
    is_group: bool,
    require_mention: bool,
    can_detect_mention: bool,
    was_mentioned: bool,
    implicit_mention: bool = False,
    has_any_mention: bool = False,
    allow_text_commands: bool,
    has_control_command: bool,
    command_authorized: bool,
) -> MentionGateWithBypassResult:
    should_bypass = (
        is_group
        and require_mention
        and not was_mentioned
        and not has_any_mention
        and allow_text_commands
        and command_authorized
        and has_control_command
    )
    base = resolve_mention_gating(
        require_mention=require_mention,
        can_detect_mention=can_detect_mention,
        was_mentioned=was_mentioned,
        implicit_mention=implicit_mention,
        should_bypass_mention=should_bypass,
    )
    return MentionGateWithBypassResult(
        effective_was_mentioned=base.effective_was_mentioned,
        should_skip=base.should_skip,
        should_bypass_mention=should_bypass,
    )
