"""WebSocket routes (§5.4). Every consumer requires an authenticated session."""

from __future__ import annotations

from apps.monitoring.routing import websocket_urlpatterns as monitor_ws
from apps.tasks.routing import websocket_urlpatterns as task_ws
from apps.terminal.routing import websocket_urlpatterns as terminal_ws

websocket_urlpatterns = [*task_ws, *monitor_ws, *terminal_ws]
