"""
Auth profile rotation with cooldown management
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone, timedelta
import sys

# Python 3.9 compatibility
if sys.version_info >= (3, 11):
    from datetime import UTC
else:
    UTC = timezone.utc

from .profile import AuthProfile, ProfileStore, calculate_auth_profile_cooldown_ms

logger = logging.getLogger(__name__)


class RotationManager:
    """
    Manage authentication profile rotation with cooldown

    Features:
    - Automatic failover to next available profile
    - Cooldown period after failures
    - Rate limit handling
    - Usage tracking
    """

    DEFAULT_COOLDOWN_MINUTES = 5
    DEFAULT_MAX_FAILURES = 3

    def __init__(
        self,
        store: ProfileStore,
        cooldown_minutes: int = DEFAULT_COOLDOWN_MINUTES,
        max_failures: int = DEFAULT_MAX_FAILURES,
    ):
        """
        Initialize rotation manager

        Args:
            store: Profile store
            cooldown_minutes: Minutes to cool down after failure
            max_failures: Max failures before cooldown
        """
        self.store = store
        self.cooldown_minutes = cooldown_minutes
        self.max_failures = max_failures

    def get_next_profile(
        self,
        provider: str,
        preferred_id: str | None = None,
        filter_fn: Callable[[AuthProfile], bool] | None = None,
    ) -> AuthProfile | None:
        """
        Get next available profile for provider

        Args:
            provider: Provider name
            preferred_id: Preferred profile ID (if available)
            filter_fn: Optional filter function

        Returns:
            Available profile or None
        """
        profiles = self.store.list_profiles(provider)

        if not profiles:
            logger.warning(f"No profiles found for provider: {provider}")
            return None

        # Apply filter if provided
        if filter_fn:
            profiles = [p for p in profiles if filter_fn(p)]

        # Filter out unavailable profiles
        available = [p for p in profiles if p.is_available()]

        if not available:
            logger.warning(f"All profiles for {provider} are in cooldown")
            return None

        # Try preferred profile first
        if preferred_id:
            for profile in available:
                if profile.id == preferred_id:
                    return profile

        # Sort by last used (least recently used first)
        available.sort(key=lambda p: p.last_used or datetime.min)

        return available[0]

    def mark_success(self, profile_id: str) -> None:
        """
        Mark profile as successfully used

        Args:
            profile_id: Profile ID
        """
        profile = self.store.get_profile(profile_id)
        if profile:
            profile.last_used = datetime.now(UTC)
            profile.failure_count = 0
            profile.cooldown_until = None
            self.store.add_profile(profile)
            logger.debug(f"Profile {profile_id} used successfully")

    def mark_failure(
        self,
        profile_id: str,
        reason: str = "unknown",
        is_rate_limit: bool = False,
        is_billing_error: bool = False,
        billing_backoff_ms: int = 5 * 60 * 60 * 1000,   # 5 hours default
        billing_max_ms: int = 24 * 60 * 60 * 1000,       # 24 hours cap
    ) -> None:
        """Mark profile as failed and apply exponential cooldown.

        Mirrors TS markAuthProfileFailure() in auth-profiles/usage.ts:
        - Increments errorCount
        - Uses calculateAuthProfileCooldownMs(errorCount) → 1min/5min/25min/1h
        - Billing errors use disabledUntil with 5h/24h backoff schedule

        Args:
            profile_id: Profile ID
            reason: Failure reason
            is_rate_limit: Whether failure was due to rate limit
            is_billing_error: Whether failure was a billing/payment error
            billing_backoff_ms: Billing backoff duration (default 5h)
            billing_max_ms: Max billing disable duration (default 24h)
        """
        profile = self.store.get_profile(profile_id)
        if not profile:
            return

        profile.error_count = (profile.error_count or 0) + 1
        profile.failure_count = profile.error_count

        now = datetime.now(UTC)

        if is_billing_error:
            # Billing disable: longer window, capped at billing_max_ms
            current_disabled = profile.disabled_until
            if current_disabled and current_disabled > now:
                # Extend proportionally
                remaining_ms = (current_disabled - now).total_seconds() * 1000
                next_ms = min(remaining_ms + billing_backoff_ms, billing_max_ms)
            else:
                next_ms = billing_backoff_ms
            profile.disabled_until = now + timedelta(milliseconds=next_ms)
            profile.disabled_reason = reason
            logger.warning(
                "Profile %s billing-disabled until %s (reason: %s)",
                profile_id, profile.disabled_until, reason,
            )
        else:
            # Exponential cooldown: 1m → 5m → 25m → 1h
            cooldown_ms = calculate_auth_profile_cooldown_ms(profile.error_count)
            profile.cooldown_until = now + timedelta(milliseconds=cooldown_ms)
            logger.warning(
                "Profile %s in cooldown until %s (reason: %s, errorCount: %d, cooldown: %ds)",
                profile_id, profile.cooldown_until, reason, profile.error_count, cooldown_ms // 1000,
            )

        self.store.add_profile(profile)

    def clear_expired_cooldowns(self) -> int:
        """Remove expired cooldowns from all profiles.

        Mirrors TS clearExpiredCooldowns().

        Returns:
            Number of profiles cleared.
        """
        now = datetime.now(UTC)
        cleared = 0
        for profile in self.store.list_profiles():
            changed = False
            if profile.cooldown_until and now >= profile.cooldown_until:
                profile.cooldown_until = None
                profile.error_count = 0
                profile.failure_count = 0
                changed = True
            if profile.disabled_until and now >= profile.disabled_until:
                profile.disabled_until = None
                profile.disabled_reason = None
                changed = True
            if changed:
                self.store.add_profile(profile)
                cleared += 1
        return cleared

    def mark_billing_disable(
        self,
        profile_id: str,
        reason: str = "billing_error",
        backoff_ms: int = 5 * 60 * 60 * 1000,
        max_ms: int = 24 * 60 * 60 * 1000,
    ) -> None:
        """Apply a billing-level disable window to a profile.

        Mirrors TS markAuthProfileBillingDisable().
        """
        self.mark_failure(
            profile_id,
            reason=reason,
            is_billing_error=True,
            billing_backoff_ms=backoff_ms,
            billing_max_ms=max_ms,
        )

    def reset_profile(self, profile_id: str) -> None:
        """
        Reset profile cooldown and failures

        Args:
            profile_id: Profile ID
        """
        profile = self.store.get_profile(profile_id)
        if profile:
            profile.failure_count = 0
            profile.cooldown_until = None
            self.store.add_profile(profile)
            logger.info(f"Profile {profile_id} reset")

    def get_status(self, provider: str | None = None) -> dict:
        """
        Get rotation status

        Args:
            provider: Filter by provider (optional)

        Returns:
            Status dictionary
        """
        profiles = self.store.list_profiles(provider)

        available = [p for p in profiles if p.is_available()]
        in_cooldown = [p for p in profiles if not p.is_available()]

        return {
            "total": len(profiles),
            "available": len(available),
            "in_cooldown": len(in_cooldown),
            "profiles": [
                {
                    "id": p.id,
                    "provider": p.provider,
                    "available": p.is_available(),
                    "failures": p.failure_count,
                    "cooldown_until": p.cooldown_until.isoformat() if p.cooldown_until else None,
                }
                for p in profiles
            ],
        }
