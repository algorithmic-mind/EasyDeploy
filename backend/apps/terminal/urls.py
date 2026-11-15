from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.terminal import views

router = SimpleRouter(trailing_slash=False)
router.register("snippets", views.SnippetViewSet, basename="snippet")

urlpatterns = [
    path("check", views.TerminalCheckView.as_view(), name="terminal-check"),
    *router.urls,
]
