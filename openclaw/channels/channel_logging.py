"""Channel logging helpers — mirrors src/channels/logging.ts"""
from __future__ import annotations

from typing import Callable

LogFn = Callable[[str], None]


def log_inbound_drop(*, log: LogFn, channel: str, reason: str, target: str | None = None) -> None:
    target_str = f" target={target}" if target else ""
    log(f"{channel}: drop {reason}{target_str}")


def log_typing_failure(
    *,
    log: LogFn,
    channel: str,
    target: str | None = None,
    action: str | None = None,
    error: object,
) -> None:
    target_str = f" target={target}" if target else ""
    action_str = f" action={action}" if action else ""
    log(f"{channel} typing{action_str} failed{target_str}: {error!s}")


def log_ack_failure(
    *,
    log: LogFn,
    channel: str,
    target: str | None = None,
    error: object,
) -> None:
    target_str = f" target={target}" if target else ""
    log(f"{channel} ack cleanup failed{target_str}: {error!s}")
