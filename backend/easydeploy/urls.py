"""URL configuration. All API routes live under ``/api/v1/`` (§10.1)."""

from __future__ import annotations

from django.urls import URLPattern, URLResolver, include, path, re_path
from drf_spectacular.views import SpectacularAPIView

from apps.core import views as core_views

api_v1: list[URLPattern | URLResolver] = [
    path("health", core_views.HealthView.as_view(), name="health"),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("auth/", include("apps.accounts.urls")),
    path("audit/", include("apps.audit.urls")),
    path("", include("apps.tasks.urls")),
    path("panel/", include("apps.panel.urls")),
    path("dashboard/", include("apps.dashboard.urls")),
    path("monitoring/", include("apps.monitoring.urls")),
    path("host/", include("apps.host.urls")),
    path("files/", include("apps.files.urls")),
]

urlpatterns = [
    path("api/v1/", include((api_v1, "api"), namespace="v1")),
    re_path(r"^api/", core_views.api_not_found),
    # Production: Nginx serves /assets/* directly; every other path returns the SPA's index.html
    # so the entrance middleware also guards the SPA shell.
    re_path(r"^(?!api/|ws/|assets/).*$", core_views.spa_index, name="spa"),
]

handler404 = "apps.core.views.not_found"
handler500 = "apps.core.views.server_error"
