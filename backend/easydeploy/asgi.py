"""ASGI entry point: HTTP via Django, WebSockets via Channels (served by Uvicorn)."""

from __future__ import annotations

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "easydeploy.settings.prod")
django_asgi_app = get_asgi_application()

# Imported after Django is set up.
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402

from apps.accounts.ws import PanelWebsocketAuthMiddleware  # noqa: E402
from easydeploy.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": PanelWebsocketAuthMiddleware(URLRouter(websocket_urlpatterns)),
    }
)
