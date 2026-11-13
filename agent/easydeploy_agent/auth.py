"""Bearer-token authentication and sudo tokens for sensitive ops.

Sudo token: ``<expiry>.<hex HMAC-SHA256(agent_token, "sudo:<actor>:<expiry>")>``. The API mints
one only while the user is in sudo mode (§9.1); the agent verifies it for ops flagged
``sensitive`` so a forged request without the shared secret cannot run them.
"""

from __future__ import annotations

import hashlib
import hmac
import time

from easydeploy_agent.errors import OpError

SUDO_TOKEN_MAX_TTL = 900


class AuthError(OpError):
    status_code = 401

    def __init__(self, message: str = "Missing or invalid agent token") -> None:
        super().__init__("agent.unauthorized", message)


class SudoRequiredError(OpError):
    status_code = 403

    def __init__(self) -> None:
        super().__init__("agent.sudo_required", "This operation requires a valid sudo token")


def _sign(secret: str, actor: str, expiry: int) -> str:
    msg = f"sudo:{actor}:{expiry}".encode()
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


def make_sudo_token(secret: str, actor: str, ttl: int = 600, now: float | None = None) -> str:
    expiry = int((now if now is not None else time.time()) + min(ttl, SUDO_TOKEN_MAX_TTL))
    return f"{expiry}.{_sign(secret, actor, expiry)}"


def verify_sudo_token(secret: str, token: str, actor: str, now: float | None = None) -> bool:
    current = now if now is not None else time.time()
    expiry_s, sep, sig = token.partition(".")
    if not sep or not expiry_s.isdigit():
        return False
    expiry = int(expiry_s)
    if not current < expiry <= current + SUDO_TOKEN_MAX_TTL:
        return False
    return hmac.compare_digest(sig, _sign(secret, actor, expiry))


class Authenticator:
    def __init__(self, token: str) -> None:
        if len(token) < 32:
            raise ValueError("agent token must be at least 32 characters")
        self._token = token

    def check_bearer(self, header: str | None) -> None:
        if not header or not header.startswith("Bearer "):
            raise AuthError()
        if not hmac.compare_digest(header[7:].strip().encode(), self._token.encode()):
            raise AuthError()

    def check_sudo(self, token: str | None, actor: str | None) -> None:
        if not token or not actor or not verify_sudo_token(self._token, token, actor):
            raise SudoRequiredError()
