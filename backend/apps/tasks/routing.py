from django.urls import path

from apps.tasks.consumers import TaskLogConsumer

websocket_urlpatterns = [
    path("ws/tasks/<uuid:task_id>/", TaskLogConsumer.as_asgi()),
]
