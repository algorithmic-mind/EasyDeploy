"""Named locks so concurrent ops cannot corrupt shared state (nginx, ufw, docker-network, apt…)."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager

from easydeploy_agent.errors import LockTimeoutError


class LockManager:
    """Process-local named locks. The agent is a single process, so threading locks suffice."""

    def __init__(self, default_timeout: float = 120.0) -> None:
        self._guard = threading.Lock()
        self._locks: dict[str, threading.Lock] = {}
        self.default_timeout = default_timeout

    def _get(self, name: str) -> threading.Lock:
        with self._guard:
            lock = self._locks.get(name)
            if lock is None:
                lock = self._locks[name] = threading.Lock()
            return lock

    @contextmanager
    def hold(self, name: str | None, timeout: float | None = None) -> Iterator[None]:
        if not name:
            yield
            return
        lock = self._get(name)
        if not lock.acquire(timeout=self.default_timeout if timeout is None else timeout):
            raise LockTimeoutError(name)
        try:
            yield
        finally:
            lock.release()

    def is_locked(self, name: str) -> bool:
        return self._get(name).locked()
