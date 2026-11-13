"""WebSocket authentication: Django session + timeout check; unauthenticated sockets are closed."""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import urlsplit

from channels.auth import AuthMiddlewareStack
from channels.db import database_sync_to_async

from apps.accounts.services import session as session_svc
from apps.panel.services import get_setting

WS_CLOSE_UNAUTHENTICATED = 4401
WS_CLOSE_FORBIDDEN_ORIGIN = 4403


class _RequireAuth:
    def __init__(self, inner: Any) -> None:
        self.inner = inner

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> Any:
        user = scope.get("user")
        sess = scope.get("session")
        if user is None or not user.is_authenticated or sess is None or await _expired(sess):
            await receive()  # consume websocket.connect
            await send({"type": "websocket.close", "code": WS_CLOSE_UNAUTHENTICATED})
            return None
        return await self.inner(scope, receive, send)


@database_sync_to_async
def _expired(sess: Any) -> bool:
    now = time.time()
    login_at = float(sess.get(session_svc.LOGIN_AT_KEY, 0))
    last_seen = float(sess.get(session_svc.LAST_SEEN_KEY, 0))
    idle = int(get_setting("security.session_idle_minutes")) * 60
    absolute = int(get_setting("security.session_absolute_hours")) * 3600
    return (now - last_seen) > idle or (now - login_at) > absolute


class SameOriginValidator:
    """Reject cross-site WebSocket handshakes: the Origin's host must equal the Host header.

    ``ALLOWED_HOSTS`` is ``*`` (the panel is reached by IP), so Channels'
    ``AllowedHostsOriginValidator`` would accept any origin.
    """

    def __init__(self, inner: Any) -> None:
        self.inner = inner

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> Any:
        headers = dict(scope.get("headers") or [])
        origin = headers.get(b"origin", b"").decode("latin-1")
        host = headers.get(b"host", b"").decode("latin-1").lower()
        origin_host = urlsplit(origin).netloc.lower() if origin else ""
        if not origin_host or origin_host != host:
            await receive()
            await send({"type": "websocket.close", "code": WS_CLOSE_FORBIDDEN_ORIGIN})
            return None
        return await self.inner(scope, receive, send)


def PanelWebsocketAuthMiddleware(inner: Any) -> Any:  # noqa: N802  (middleware factory)
    return SameOriginValidator(AuthMiddlewareStack(_RequireAuth(inner)))
