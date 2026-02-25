"""Agent identity configuration

Fully aligned with TypeScript openclaw/src/agents/identity.ts

Provides functions for resolving agent identity from:
- Config (agents.list[].identity)
- Workspace IDENTITY.md file
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class IdentityConfig:
    """Agent identity configuration"""
    name: str | None = None
    theme: str | None = None
    emoji: str | None = None
    avatar: str | None = None
    creature: str | None = None
    vibe: str | None = None


def resolve_agent_identity(cfg: Any, agent_id: str) -> IdentityConfig | None:
    """
    Resolve agent identity from config.
    
    Mirrors TS resolveAgentIdentity() from identity.ts lines 6-11
    
    Args:
        cfg: Configuration object
        agent_id: Agent ID
    
    Returns:
        IdentityConfig or None if not configured
    """
    from openclaw.agents.agent_scope import resolve_agent_config
    
    agent_config = resolve_agent_config(cfg, agent_id)
    if not agent_config or not hasattr(agent_config, 'identity'):
        return None
    
    identity_raw = agent_config.identity
    if not identity_raw:
        return None
    
    # Convert from config object to IdentityConfig
    if isinstance(identity_raw, dict):
        return IdentityConfig(
            name=identity_raw.get('name'),
            theme=identity_raw.get('theme'),
            emoji=identity_raw.get('emoji'),
            avatar=identity_raw.get('avatar'),
            creature=identity_raw.get('creature'),
            vibe=identity_raw.get('vibe'),
        )
    
    # Handle object with attributes
    if hasattr(identity_raw, 'name'):
        return IdentityConfig(
            name=getattr(identity_raw, 'name', None),
            theme=getattr(identity_raw, 'theme', None),
            emoji=getattr(identity_raw, 'emoji', None),
            avatar=getattr(identity_raw, 'avatar', None),
            creature=getattr(identity_raw, 'creature', None),
            vibe=getattr(identity_raw, 'vibe', None),
        )
    
    return None


def resolve_identity_name_prefix(cfg: Any, agent_id: str) -> str | None:
    """
    Resolve identity name prefix (with brackets).
    
    Mirrors TS resolveIdentityNamePrefix() from identity.ts lines 48-57
    
    Args:
        cfg: Configuration object
        agent_id: Agent ID
    
    Returns:
        Identity name prefix like "[AgentName]" or None
    """
    name = resolve_identity_name(cfg, agent_id)
    if not name:
        return None
    return f"[{name}]"


def resolve_identity_name(cfg: Any, agent_id: str) -> str | None:
    """
    Resolve identity name (without brackets).
    
    Mirrors TS resolveIdentityName() from identity.ts lines 60-62
    
    Args:
        cfg: Configuration object
        agent_id: Agent ID
    
    Returns:
        Identity name or None
    """
    identity = resolve_agent_identity(cfg, agent_id)
    if not identity or not identity.name:
        return None
    return identity.name.strip() or None


def resolve_ack_reaction(
    cfg: Any,
    agent_id: str,
    channel: str | None = None,
    account_id: str | None = None,
) -> str:
    """
    Resolve acknowledgment reaction for agent.
    
    Mirrors TS resolveAckReaction() from identity.ts lines 13-46
    
    Priority (L1 highest):
    1. Channel account level (channels.<channel>.accounts.<accountId>.ackReaction)
    2. Channel level (channels.<channel>.ackReaction)
    3. Global messages level (messages.ackReaction)
    4. Agent identity emoji fallback
    5. Default: "👀"
    
    Args:
        cfg: Configuration object
        agent_id: Agent ID
        channel: Channel name
        account_id: Account ID
    
    Returns:
        Reaction string (emoji)
    """
    DEFAULT_ACK_REACTION = "👀"
    
    # L1: Channel account level
    if channel and account_id:
        try:
            if hasattr(cfg, 'channels'):
                channels = cfg.channels
                if hasattr(channels, channel):
                    channel_cfg = getattr(channels, channel)
                    if hasattr(channel_cfg, 'accounts'):
                        accounts = channel_cfg.accounts
                        if isinstance(accounts, dict) and account_id in accounts:
                            account_cfg = accounts[account_id]
                            if isinstance(account_cfg, dict):
                                ack = account_cfg.get('ackReaction')
                            elif hasattr(account_cfg, 'ackReaction'):
                                ack = account_cfg.ackReaction
                            else:
                                ack = None
                            
                            if ack is not None:
                                return str(ack).strip()
        except Exception:
            pass
    
    # L2: Channel level
    if channel:
        try:
            if hasattr(cfg, 'channels'):
                channels = cfg.channels
                if hasattr(channels, channel):
                    channel_cfg = getattr(channels, channel)
                    if hasattr(channel_cfg, 'ackReaction'):
                        ack = channel_cfg.ackReaction
                        if ack is not None:
                            return str(ack).strip()
        except Exception:
            pass
    
    # L3: Global messages level
    if hasattr(cfg, 'messages') and cfg.messages:
        if hasattr(cfg.messages, 'ackReaction'):
            ack = cfg.messages.ackReaction
            if ack is not None:
                return str(ack).strip()
    
    # L4: Agent identity emoji fallback
    identity = resolve_agent_identity(cfg, agent_id)
    if identity and identity.emoji:
        emoji = identity.emoji.strip()
        if emoji:
            return emoji
    
    return DEFAULT_ACK_REACTION
