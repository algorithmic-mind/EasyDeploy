from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.tasks import views

router = SimpleRouter(trailing_slash=False)
router.register("tasks", views.TaskViewSet, basename="task")

urlpatterns = [
    path("tasks/diagnostics", views.DiagnosticsView.as_view(), name="task-diagnostics"),
    *router.urls,
]
