"""Delivery queue for reliable message delivery

Ports TypeScript src/infra/outbound/delivery-queue.ts functionality.
Implements write-ahead logging with atomic file operations and retry logic.

Features:
- Atomic enqueue/ack/fail operations
- Exponential backoff retry (5s, 25s, 2m, 10m)
- Max 5 retries before moving to failed/
- Startup recovery of pending deliveries
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

from openclaw.config.paths import resolve_state_dir

logger = logging.getLogger(__name__)

DELIVERY_QUEUE_DIR = "delivery-queue"
DELIVERY_QUEUE_FAILED_DIR = "failed"
MAX_RETRIES = 5
RETRY_DELAYS_MS = [5000, 25000, 120000, 600000]  # 5s, 25s, 2m, 10m


class DeliveryQueueEntry:
    """A single delivery queue entry"""

    def __init__(
        self,
        id: str,
        enqueued_at: int,
        channel: str,
        to: str,
        account_id: str,
        payloads: list[dict[str, Any]],
        retry_count: int = 0,
        last_error: str | None = None,
        thread_id: str | int | None = None,
    ):
        self.id = id
        self.enqueued_at = enqueued_at
        self.channel = channel
        self.to = to
        self.account_id = account_id
        self.payloads = payloads
        self.retry_count = retry_count
        self.last_error = last_error
        self.thread_id = thread_id

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON storage"""
        data = {
            "id": self.id,
            "enqueuedAt": self.enqueued_at,
            "channel": self.channel,
            "to": self.to,
            "accountId": self.account_id,
            "payloads": self.payloads,
            "retryCount": self.retry_count,
        }
        if self.last_error is not None:
            data["lastError"] = self.last_error
        if self.thread_id is not None:
            data["threadId"] = self.thread_id
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeliveryQueueEntry:
        """Deserialize from JSON dict"""
        return cls(
            id=data["id"],
            enqueued_at=data["enqueuedAt"],
            channel=data["channel"],
            to=data["to"],
            account_id=data["accountId"],
            payloads=data["payloads"],
            retry_count=data.get("retryCount", 0),
            last_error=data.get("lastError"),
            thread_id=data.get("threadId"),
        )


def ensure_queue_dir(state_dir: Path | None = None) -> tuple[Path, Path]:
    """Ensure delivery queue directories exist
    
    Args:
        state_dir: State directory (defaults to ~/.openclaw)
        
    Returns:
        Tuple of (queue_dir, failed_dir)
    """
    if state_dir is None:
        state_dir = Path(resolve_state_dir())

    queue_dir = state_dir / DELIVERY_QUEUE_DIR
    failed_dir = queue_dir / DELIVERY_QUEUE_FAILED_DIR

    queue_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    failed_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    return queue_dir, failed_dir


def enqueue_delivery(
    queue_dir: Path, delivery: DeliveryQueueEntry
) -> None:
    """Enqueue delivery with atomic write
    
    Args:
        queue_dir: Queue directory
        delivery: Delivery entry to enqueue
    """
    entry_path = queue_dir / f"{delivery.id}.json"
    temp_path = queue_dir / f"{delivery.id}.tmp"

    try:
        # Write to temp file
        temp_path.write_text(
            json.dumps(delivery.to_dict(), indent=2), encoding="utf-8"
        )

        # Atomic rename
        temp_path.replace(entry_path)

        logger.debug(
            f"Enqueued delivery {delivery.id} to {delivery.channel}:{delivery.to}"
        )
    except Exception as e:
        logger.error(f"Failed to enqueue delivery {delivery.id}: {e}")
        if temp_path.exists():
            temp_path.unlink()
        raise


def ack_delivery(queue_dir: Path, delivery_id: str) -> None:
    """Acknowledge successful delivery and remove from queue
    
    Args:
        queue_dir: Queue directory
        delivery_id: Delivery ID to acknowledge
    """
    entry_path = queue_dir / f"{delivery_id}.json"

    try:
        if entry_path.exists():
            entry_path.unlink()
            logger.debug(f"Acknowledged delivery {delivery_id}")
    except Exception as e:
        logger.error(f"Failed to ack delivery {delivery_id}: {e}")


def fail_delivery(queue_dir: Path, delivery_id: str, error: str) -> None:
    """Mark delivery as failed and update retry count
    
    Args:
        queue_dir: Queue directory
        delivery_id: Delivery ID that failed
        error: Error message
    """
    entry_path = queue_dir / f"{delivery_id}.json"

    try:
        if not entry_path.exists():
            logger.warning(f"Delivery {delivery_id} not found for fail update")
            return

        # Load existing entry
        raw = entry_path.read_text(encoding="utf-8")
        data = json.loads(raw)
        delivery = DeliveryQueueEntry.from_dict(data)

        # Update retry count and error
        delivery.retry_count += 1
        delivery.last_error = error

        # Check if should move to failed
        if delivery.retry_count >= MAX_RETRIES:
            move_to_failed(queue_dir, delivery_id)
            logger.warning(
                f"Delivery {delivery_id} exceeded max retries, moved to failed/"
            )
            return

        # Update entry atomically
        temp_path = queue_dir / f"{delivery_id}.tmp"
        temp_path.write_text(
            json.dumps(delivery.to_dict(), indent=2), encoding="utf-8"
        )
        temp_path.replace(entry_path)

        logger.debug(
            f"Updated failed delivery {delivery_id} (retry {delivery.retry_count}/{MAX_RETRIES})"
        )
    except Exception as e:
        logger.error(f"Failed to update delivery {delivery_id}: {e}")


def load_pending_deliveries(queue_dir: Path) -> list[DeliveryQueueEntry]:
    """Load all pending deliveries from queue
    
    Args:
        queue_dir: Queue directory
        
    Returns:
        List of pending delivery entries
    """
    deliveries = []

    try:
        for entry_path in queue_dir.glob("*.json"):
            try:
                raw = entry_path.read_text(encoding="utf-8")
                data = json.loads(raw)
                delivery = DeliveryQueueEntry.from_dict(data)
                deliveries.append(delivery)
            except Exception as e:
                logger.warning(f"Failed to load delivery from {entry_path}: {e}")

        if deliveries:
            logger.info(f"Loaded {len(deliveries)} pending deliveries")

    except Exception as e:
        logger.error(f"Failed to load pending deliveries: {e}")

    return deliveries


def move_to_failed(queue_dir: Path, delivery_id: str) -> None:
    """Move delivery to failed directory
    
    Args:
        queue_dir: Queue directory
        delivery_id: Delivery ID to move
    """
    entry_path = queue_dir / f"{delivery_id}.json"
    failed_dir = queue_dir / DELIVERY_QUEUE_FAILED_DIR
    failed_path = failed_dir / f"{delivery_id}.json"

    try:
        if entry_path.exists():
            entry_path.replace(failed_path)
            logger.info(f"Moved delivery {delivery_id} to failed/")
    except Exception as e:
        logger.error(f"Failed to move delivery {delivery_id} to failed/: {e}")


def _get_retry_delay_ms(retry_count: int) -> int:
    """Get delay in milliseconds for retry attempt
    
    Uses exponential backoff: 5s, 25s, 2m, 10m
    
    Args:
        retry_count: Current retry count (0-indexed)
        
    Returns:
        Delay in milliseconds
    """
    if retry_count >= len(RETRY_DELAYS_MS):
        return RETRY_DELAYS_MS[-1]
    return RETRY_DELAYS_MS[retry_count]


async def recover_pending_deliveries(
    queue_dir: Path,
    deliver_fn: Callable[[DeliveryQueueEntry], Awaitable[bool]],
) -> None:
    """Recover and retry pending deliveries from queue
    
    Args:
        queue_dir: Queue directory
        deliver_fn: Async function to deliver entry, returns True on success
    """
    deliveries = load_pending_deliveries(queue_dir)

    if not deliveries:
        logger.debug("No pending deliveries to recover")
        return

    logger.info(f"Recovering {len(deliveries)} pending deliveries...")

    for delivery in deliveries:
        # Calculate delay based on retry count
        delay_ms = _get_retry_delay_ms(delivery.retry_count)
        age_ms = int(datetime.now(UTC).timestamp() * 1000) - delivery.enqueued_at

        # If delivery is old enough, retry immediately
        # Otherwise, schedule retry after delay
        if age_ms >= delay_ms:
            asyncio.create_task(_retry_delivery(queue_dir, delivery, deliver_fn))
        else:
            remaining_delay_ms = delay_ms - age_ms
            asyncio.create_task(
                _retry_delivery_after_delay(
                    queue_dir, delivery, deliver_fn, remaining_delay_ms
                )
            )


async def _retry_delivery_after_delay(
    queue_dir: Path,
    delivery: DeliveryQueueEntry,
    deliver_fn: Callable[[DeliveryQueueEntry], Awaitable[bool]],
    delay_ms: int,
) -> None:
    """Retry delivery after delay
    
    Args:
        queue_dir: Queue directory
        delivery: Delivery entry
        deliver_fn: Delivery function
        delay_ms: Delay in milliseconds
    """
    await asyncio.sleep(delay_ms / 1000.0)
    await _retry_delivery(queue_dir, delivery, deliver_fn)


async def _retry_delivery(
    queue_dir: Path,
    delivery: DeliveryQueueEntry,
    deliver_fn: Callable[[DeliveryQueueEntry], Awaitable[bool]],
) -> None:
    """Retry a single delivery
    
    Args:
        queue_dir: Queue directory
        delivery: Delivery entry
        deliver_fn: Delivery function
    """
    try:
        logger.debug(
            f"Retrying delivery {delivery.id} (attempt {delivery.retry_count + 1}/{MAX_RETRIES})"
        )

        success = await deliver_fn(delivery)

        if success:
            ack_delivery(queue_dir, delivery.id)
            logger.info(f"Successfully delivered queued message {delivery.id}")
        else:
            fail_delivery(
                queue_dir, delivery.id, "Delivery function returned False"
            )

    except Exception as e:
        logger.error(f"Failed to retry delivery {delivery.id}: {e}")
        fail_delivery(queue_dir, delivery.id, str(e))


def ensure_delivery_queue_dirs(base_dir: Path | None = None) -> tuple[Path, Path]:
    """Create the delivery queue directories (and other standard state dirs) if they do not exist.

    Returns (queue_dir, failed_dir).
    """
    if base_dir is None:
        base_dir = resolve_state_dir()
    queue_dir = base_dir / DELIVERY_QUEUE_DIR
    failed_dir = queue_dir / DELIVERY_QUEUE_FAILED_DIR
    queue_dir.mkdir(parents=True, exist_ok=True)
    failed_dir.mkdir(parents=True, exist_ok=True)
    # Also ensure other standard top-level dirs (mirrors TS ensureStateDirs)
    for extra_dir in ("credentials", "logs"):
        (base_dir / extra_dir).mkdir(parents=True, exist_ok=True)
    return queue_dir, failed_dir
