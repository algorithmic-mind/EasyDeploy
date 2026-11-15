from django.urls import re_path

from apps.terminal.consumers import TerminalConsumer

websocket_urlpatterns = [
    re_path(r"^ws/terminal/(?P<session>[A-Za-z0-9_-]{1,64})/$", TerminalConsumer.as_asgi()),
]
