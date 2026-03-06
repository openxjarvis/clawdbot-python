"""Gateway process lock — ensures only one gateway instance runs at a time.

Mirrors TypeScript: openclaw/src/infra/gateway-lock.ts

The lock file lives at:
  ~/.openclaw/gateway.<config_hash>.lock

It contains JSON: { pid, createdAt, configPath, port }

Acquisition uses O_CREAT|O_EXCL (exclusive create) so it's atomic on POSIX.
On acquisition:
  - If the file doesn't exist → create it and write our PID.
  - If the file exists and the owning PID is dead → remove stale lock and retry.
  - If the file exists and the owning PID is alive → raise GatewayLockError.

Release: delete the lock file in a finally block.

The --force flag (CLI) kills the old process, waits for it to exit, then acquires.
"""
from __future__ import annotations

import errno
import hashlib
import json
import logging
import os
import signal
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

from ..config.paths import resolve_state_dir

logger = logging.getLogger(__name__)

_LOCK_STALE_WAIT_S = 5.0       # max seconds to wait for old process to die
_LOCK_POLL_INTERVAL_S = 0.1    # polling interval while waiting
_FORCE_KILL_TIMEOUT_S = 3.0    # seconds before escalating SIGTERM → SIGKILL


# ---------------------------------------------------------------------------
# Lock file path
# ---------------------------------------------------------------------------

def _config_hash(config_path: Optional[str]) -> str:
    """Short hash of the config path for per-config lock files."""
    raw = str(config_path or "default")
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def resolve_gateway_lock_path(config_path: Optional[str] = None) -> Path:
    """Return the lock file path for the given config (or default)."""
    state_dir = resolve_state_dir()
    h = _config_hash(config_path)
    return state_dir / f"gateway.{h}.lock"


# ---------------------------------------------------------------------------
# PID liveness check
# ---------------------------------------------------------------------------

def _is_pid_alive(pid: int) -> bool:
    """Return True if the process with the given PID is still alive."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)  # signal 0: no-op but checks if process exists
        return True
    except OSError as exc:
        if exc.errno == errno.ESRCH:
            return False   # No such process
        if exc.errno == errno.EPERM:
            return True    # Process exists but we don't have permission
        return False


def _kill_pid(pid: int, force: bool = False) -> None:
    """Send SIGTERM (or SIGKILL if force=True) to the given PID."""
    try:
        sig = signal.SIGKILL if force else signal.SIGTERM
        os.kill(pid, sig)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Lock acquire / release
# ---------------------------------------------------------------------------

class GatewayLockHandle:
    """Represents a successfully acquired gateway lock."""

    def __init__(self, lock_path: Path, pid: int) -> None:
        self._lock_path = lock_path
        self._pid = pid
        self._released = False

    def release(self) -> None:
        if self._released:
            return
        self._released = True
        try:
            self._lock_path.unlink(missing_ok=True)
            logger.debug("Gateway lock released: %s", self._lock_path)
        except Exception as exc:
            logger.debug("Error releasing gateway lock: %s", exc)

    def __repr__(self) -> str:
        return f"GatewayLockHandle(pid={self._pid}, path={self._lock_path})"


def _write_lock(lock_path: Path, port: Optional[int], config_path: Optional[str]) -> None:
    payload = {
        "pid": os.getpid(),
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "configPath": str(config_path or ""),
        "port": port,
    }
    lock_path.write_text(json.dumps(payload))


def _read_lock(lock_path: Path) -> Optional[dict]:
    try:
        return json.loads(lock_path.read_text())
    except Exception:
        return None


def acquire_gateway_lock(
    config_path: Optional[str] = None,
    port: Optional[int] = None,
    force: bool = False,
) -> GatewayLockHandle:
    """Acquire the gateway PID lock.

    Parameters
    ----------
    config_path : str, optional
        Path to the gateway config file (used to derive the lock filename).
    port : int, optional
        Gateway port — stored in the lock file for diagnostics.
    force : bool
        If True, kill any existing gateway process and wait for it to exit
        before acquiring.  Mirrors TS ``--force`` / ``forceFreePortAndWait``.

    Raises
    ------
    GatewayLockError
        If another gateway process is already running and ``force=False``.
    """
    from ..gateway.error_codes import GatewayLockError  # avoid circular import

    lock_path = resolve_gateway_lock_path(config_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    for _attempt in range(3):
        # 1. Try exclusive create (O_CREAT | O_EXCL)
        try:
            fd = os.open(str(lock_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.close(fd)
            _write_lock(lock_path, port, config_path)
            logger.debug("Gateway lock acquired: %s (pid=%d)", lock_path, os.getpid())
            return GatewayLockHandle(lock_path, os.getpid())
        except OSError as exc:
            if exc.errno != errno.EEXIST:
                raise

        # 2. Lock file exists — read it
        existing = _read_lock(lock_path)
        if existing is None:
            # Corrupt / unreadable lock — remove and retry
            lock_path.unlink(missing_ok=True)
            continue

        old_pid = existing.get("pid", 0)
        if not _is_pid_alive(old_pid):
            # Stale lock — remove and retry
            logger.info(
                "Removing stale gateway lock (pid %d is no longer alive): %s",
                old_pid,
                lock_path,
            )
            lock_path.unlink(missing_ok=True)
            continue

        # 3. Another live gateway is running
        if force:
            logger.warning(
                "Gateway already running (pid=%d) — killing it (--force)", old_pid
            )
            _kill_pid(old_pid, force=False)  # SIGTERM first
            deadline = time.monotonic() + _FORCE_KILL_TIMEOUT_S
            while _is_pid_alive(old_pid) and time.monotonic() < deadline:
                time.sleep(_LOCK_POLL_INTERVAL_S)
            if _is_pid_alive(old_pid):
                logger.warning("Process %d didn't exit on SIGTERM — escalating to SIGKILL", old_pid)
                _kill_pid(old_pid, force=True)
                time.sleep(0.5)
            lock_path.unlink(missing_ok=True)
            continue
        else:
            raise GatewayLockError(
                host="127.0.0.1",
                port=port or 0,
                cause=None,
            ) from None

    raise RuntimeError("Failed to acquire gateway lock after 3 attempts")


@contextmanager
def gateway_lock_ctx(
    config_path: Optional[str] = None,
    port: Optional[int] = None,
    force: bool = False,
) -> Generator[GatewayLockHandle, None, None]:
    """Context manager that acquires and releases the gateway PID lock."""
    handle = acquire_gateway_lock(config_path=config_path, port=port, force=force)
    try:
        yield handle
    finally:
        handle.release()
