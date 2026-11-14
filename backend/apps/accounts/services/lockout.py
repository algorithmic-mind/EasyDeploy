"""Login brute-force protection: per-IP and per-username counters in the cache (Redis in prod).

After ``security.login_max_failures`` failures inside the lockout window, the IP or username is
locked for ``security.login_lockout_minutes``. Each failure also adds a growing delay.
"""

from __future__ import annotations

import hashlib
import time

from django.core.cache import cache

from apps.accounts.errors import LoginLocked
from apps.panel.services import get_setting

MAX_DELAY_SECONDS = 2.0
GENERATION_KEY = "login:generation"


def _key(kind: str, value: str) -> str:
    # The generation lets `reset_all_lockouts` invalidate every counter and lock at once.
    generation = cache.get(GENERATION_KEY, 0)
    digest = hashlib.sha256(value.lower().encode()).hexdigest()[:32]
    return f"login:{generation}:{kind}:{digest}"


class LoginGuard:
    def __init__(self, ip: str, username: str) -> None:
        self.subjects = [("ip", ip or "unknown")]
        if username:
            self.subjects.append(("user", username))
        self.max_failures = int(get_setting("security.login_max_failures"))
        self.lock_seconds = int(get_setting("security.login_lockout_minutes")) * 60

    def check(self) -> None:
        """Raise ``LoginLocked`` with ``retry_after`` if any subject is locked."""
        now = time.time()
        for kind, value in self.subjects:
            until = cache.get(_key(f"lock:{kind}", value))
            if until and until > now:
                raise LoginLocked(details={"retry_after": int(until - now) + 1})

    def failure(self, *, sleep: bool = True) -> int:
        """Count a failure; lock when the threshold is reached. Returns the highest count."""
        highest = 0
        for kind, value in self.subjects:
            key = _key(f"fail:{kind}", value)
            cache.add(key, 0, self.lock_seconds)
            try:
                count = cache.incr(key)
            except ValueError:  # expired between add and incr
                cache.set(key, 1, self.lock_seconds)
                count = 1
            highest = max(highest, count)
            if count >= self.max_failures:
                cache.set(
                    _key(f"lock:{kind}", value), time.time() + self.lock_seconds, self.lock_seconds
                )
                cache.delete(key)
        if sleep and highest >= 2:
            time.sleep(min(0.25 * 2 ** (highest - 2), MAX_DELAY_SECONDS))
        return highest

    def success(self) -> None:
        for kind, value in self.subjects:
            cache.delete(_key(f"fail:{kind}", value))


def reset_all_lockouts() -> None:
    """Clear every IP and username lock (``edctl reset-password`` recovers a locked-out admin)."""
    try:
        cache.incr(GENERATION_KEY)
    except ValueError:
        cache.set(GENERATION_KEY, 1, None)
