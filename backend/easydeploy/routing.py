"""WebSocket routes (§5.4). Every consumer requires an authenticated session."""

from __future__ import annotations

from apps.tasks.routing import websocket_urlpatterns as task_ws

websocket_urlpatterns = [*task_ws]
