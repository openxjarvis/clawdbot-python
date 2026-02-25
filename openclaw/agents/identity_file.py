"""Agent identity file loading

Fully aligned with TypeScript openclaw/src/agents/identity-file.ts

Load agent identity from IDENTITY.md file in workspace.
Format is simple markdown with key: value pairs.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_IDENTITY_FILENAME = "IDENTITY.md"

# Placeholder values to ignore (mirrors TS IDENTITY_PLACEHOLDER_VALUES)
IDENTITY_PLACEHOLDER_VALUES = {
    "pick something you like",
    "ai? robot? familiar? ghost in the machine? something weirder?",
    "how do you come across? sharp? warm? chaotic? calm?",
    "your signature - pick one that feels right",
    "workspace-relative path, http(s) url, or data uri",
}


@dataclass
class AgentIdentityFile:
    """Agent identity loaded from file"""
    name: str | None = None
    emoji: str | None = None
    theme: str | None = None
    creature: str | None = None
    vibe: str | None = None
    avatar: str | None = None


def normalize_identity_value(value: str) -> str:
    """
    Normalize identity value for placeholder detection.
    
    Mirrors TS normalizeIdentityValue() from identity-file.ts lines 22-31
    """
    normalized = value.strip()
    
    # Remove surrounding *_ markdown
    normalized = re.sub(r'^[*_]+|[*_]+$', '', normalized).strip()
    
    # Remove surrounding parentheses
    if normalized.startswith('(') and normalized.endswith(')'):
        normalized = normalized[1:-1].strip()
    
    # Normalize dashes and spaces
    normalized = normalized.replace('\u2013', '-').replace('\u2014', '-')
    normalized = re.sub(r'\s+', ' ', normalized).lower()
    
    return normalized


def is_identity_placeholder(value: str) -> bool:
    """
    Check if value is a placeholder.
    
    Mirrors TS isIdentityPlaceholder() from identity-file.ts lines 33-36
    """
    normalized = normalize_identity_value(value)
    return normalized in IDENTITY_PLACEHOLDER_VALUES


def parse_identity_markdown(content: str) -> AgentIdentityFile:
    """
    Parse identity from markdown content.
    
    Mirrors TS parseIdentityMarkdown() from identity-file.ts lines 38-78
    
    Format:
    - name: Agent Name
    - emoji: 🤖
    - theme: blue
    - creature: AI Assistant
    - vibe: professional
    - avatar: avatar.png
    
    Args:
        content: Markdown file content
    
    Returns:
        Parsed AgentIdentityFile
    """
    identity = AgentIdentityFile()
    
    lines = content.split('\n')
    for line in lines:
        # Remove leading "- " or "* "
        cleaned = line.strip()
        cleaned = re.sub(r'^\s*[-*]\s*', '', cleaned)
        
        # Find colon separator
        if ':' not in cleaned:
            continue
        
        colon_idx = cleaned.index(':')
        label = cleaned[:colon_idx].replace('*', '').replace('_', '').strip().lower()
        value = cleaned[colon_idx + 1:].strip()
        
        # Remove surrounding markdown
        value = re.sub(r'^[*_]+|[*_]+$', '', value).strip()
        
        if not value:
            continue
        
        # Skip placeholders
        if is_identity_placeholder(value):
            continue
        
        # Map to identity fields
        if label == 'name':
            identity.name = value
        elif label == 'emoji':
            identity.emoji = value
        elif label == 'creature':
            identity.creature = value
        elif label == 'vibe':
            identity.vibe = value
        elif label == 'theme':
            identity.theme = value
        elif label == 'avatar':
            identity.avatar = value
    
    return identity


def identity_has_values(identity: AgentIdentityFile) -> bool:
    """
    Check if identity has any non-None values.
    
    Mirrors TS identityHasValues() from identity-file.ts lines 80-89
    """
    return bool(
        identity.name
        or identity.emoji
        or identity.theme
        or identity.creature
        or identity.vibe
        or identity.avatar
    )


def load_identity_from_file(identity_path: Path) -> AgentIdentityFile | None:
    """
    Load identity from file path.
    
    Mirrors TS loadIdentityFromFile() from identity-file.ts lines 91-102
    
    Args:
        identity_path: Path to IDENTITY.md file
    
    Returns:
        Parsed identity or None if file not found/invalid
    """
    try:
        content = identity_path.read_text(encoding='utf-8')
        parsed = parse_identity_markdown(content)
        
        if not identity_has_values(parsed):
            return None
        
        return parsed
    except Exception as e:
        logger.debug(f"Failed to load identity from {identity_path}: {e}")
        return None


def load_agent_identity_from_workspace(workspace: Path) -> AgentIdentityFile | None:
    """
    Load agent identity from workspace IDENTITY.md file.
    
    Mirrors TS loadAgentIdentityFromWorkspace() from identity-file.ts lines 104-107
    
    Args:
        workspace: Workspace directory path
    
    Returns:
        Parsed identity or None if not found
    """
    identity_path = workspace / DEFAULT_IDENTITY_FILENAME
    return load_identity_from_file(identity_path)


def merge_agent_identity(
    workspace_identity: AgentIdentityFile | None,
    config_identity: Any = None,
) -> IdentityConfig | None:
    """
    Merge identity from workspace and config.
    
    Priority: config overrides workspace.
    
    Args:
        workspace_identity: Identity loaded from IDENTITY.md
        config_identity: Identity from config (IdentityConfig)
    
    Returns:
        Merged IdentityConfig
    """
    from openclaw.agents.identity import IdentityConfig
    
    result = IdentityConfig()
    
    # Apply workspace values first
    if workspace_identity:
        result.name = workspace_identity.name
        result.theme = workspace_identity.theme
        result.emoji = workspace_identity.emoji
        result.avatar = workspace_identity.avatar
        result.creature = workspace_identity.creature
        result.vibe = workspace_identity.vibe
    
    # Override with config values (config takes precedence)
    if config_identity:
        if hasattr(config_identity, 'name') and config_identity.name:
            result.name = config_identity.name
        if hasattr(config_identity, 'theme') and config_identity.theme:
            result.theme = config_identity.theme
        if hasattr(config_identity, 'emoji') and config_identity.emoji:
            result.emoji = config_identity.emoji
        if hasattr(config_identity, 'avatar') and config_identity.avatar:
            result.avatar = config_identity.avatar
        if hasattr(config_identity, 'creature') and config_identity.creature:
            result.creature = config_identity.creature
        if hasattr(config_identity, 'vibe') and config_identity.vibe:
            result.vibe = config_identity.vibe
    
    # Return None if no values set
    if not any([
        result.name,
        result.theme,
        result.emoji,
        result.avatar,
        result.creature,
        result.vibe,
    ]):
        return None
    
    return result
