"""Skill eligibility checking system."""
import os
import shutil
import sys
from typing import Optional


class SkillEligibilityChecker:
    """Checks if a skill can be loaded based on requirements."""
    
    def __init__(self, config: dict):
        self.config = config
    
    @staticmethod
    def _meta_get(metadata, key, default=None):
        """Get a value from metadata, supporting both dicts and Pydantic models."""
        if isinstance(metadata, dict):
            return metadata.get(key, default)
        return getattr(metadata, key, default)

    def check(self, skill) -> tuple[bool, Optional[str]]:
        """
        Check if a skill meets all requirements.
        
        Returns:
            (is_eligible, reason_if_not)
        """
        metadata = getattr(skill, 'metadata', {})
        mg = self._meta_get

        # Check if explicitly disabled in config
        skill_config = self._get_skill_config(skill.name)
        if skill_config.get('enabled') is False:
            return False, "Disabled in config"

        # Check OS requirements
        required_os = mg(metadata, 'os', []) or []
        if required_os and sys.platform not in required_os:
            return False, f"Requires OS: {', '.join(required_os)}"

        # Support both flat (requires_bins) and nested (requires.bins) schemas
        requires_raw = mg(metadata, 'requires', {}) or {}
        if isinstance(requires_raw, dict):
            requires_bins = requires_raw.get('bins', []) or []
            any_bins = requires_raw.get('anyBins', []) or []
            requires_env = requires_raw.get('env', []) or []
            requires_config = requires_raw.get('config', []) or []
        else:
            requires_bins = getattr(requires_raw, 'bins', []) or []
            any_bins = getattr(requires_raw, 'anyBins', []) or []
            requires_env = getattr(requires_raw, 'env', []) or []
            requires_config = getattr(requires_raw, 'config', []) or []

        # Flat field fallback (SkillMetadata.requires_bins / requires_env)
        if not requires_bins:
            requires_bins = mg(metadata, 'requires_bins', []) or []
        if not requires_env:
            requires_env = mg(metadata, 'requires_env', []) or []

        # Check required binaries
        for binary in requires_bins:
            if not shutil.which(binary):
                return False, f"Missing binary: {binary}"

        # Check anyBins (at least one must exist)
        if any_bins:
            if not any(shutil.which(b) for b in any_bins):
                return False, f"Missing any of: {', '.join(any_bins)}"

        # Check required environment variables
        primary_env = mg(metadata, 'primaryEnv', None)
        for env_var in requires_env:
            if os.getenv(env_var):
                continue
            if skill_config.get('env', {}).get(env_var):
                continue
            if primary_env == env_var and skill_config.get('apiKey'):
                continue
            return False, f"Missing env: {env_var}"

        # Check config requirements
        for config_path in requires_config:
            if not self._resolve_config_value(config_path):
                return False, f"Missing config: {config_path}"

        # always: true overrides all checks
        if mg(metadata, 'always', False) is True:
            return True, None

        return True, None
    
    def _get_skill_config(self, skill_name: str) -> dict:
        """Get skill-specific config."""
        return (
            self.config
            .get('skills', {})
            .get('entries', {})
            .get(skill_name, {})
        )
    
    def _resolve_config_value(self, path: str):
        """Resolve nested config value by dot-separated path."""
        parts = path.split('.')
        value = self.config
        
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
                if value is None:
                    return None
            else:
                return None
        
        return value
