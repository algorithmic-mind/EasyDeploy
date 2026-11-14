from django.urls import path

from apps.monitoring.consumers import LiveMetricsConsumer

websocket_urlpatterns = [path("ws/monitor/live/", LiveMetricsConsumer.as_asgi())]
