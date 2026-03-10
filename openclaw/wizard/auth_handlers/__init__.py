"""Auth handlers package

Handler chain for applying authentication choices.
Mirrors openclaw/src/commands/auth-choice.apply.ts architecture.
"""
from .base import ApplyAuthChoiceResult, AuthChoiceHandler

__all__ = ["ApplyAuthChoiceResult", "AuthChoiceHandler"]
