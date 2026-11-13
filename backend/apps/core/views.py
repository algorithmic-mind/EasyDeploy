"""Core views: health check, SPA shell, JSON error pages."""

from __future__ import annotations

from typing import Any

from django.db import connections
from django.http import FileResponse, HttpRequest, HttpResponse, JsonResponse
from django.http.response import HttpResponseBase
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.conf import ed_path
from apps.core.exceptions import envelope
from apps.core.net import client_ip, is_local


class HealthView(APIView):
    """``/api/v1/health`` — status only, no auth, answered **only** for localhost (§10.1)."""

    authentication_classes: list[Any] = []
    permission_classes = [AllowAny]

    @extend_schema(
        responses=inline_serializer("Health", {"status": serializers.CharField()}),
        auth=[],
    )
    def get(self, request: Request) -> Response:
        if not is_local(client_ip(request)):
            return Response(envelope("not_found", _("Not found.")), status=404)
        try:
            with connections["default"].cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception:
            return Response({"status": "degraded"}, status=503)
        return Response({"status": "ok"})


def spa_index(request: HttpRequest) -> HttpResponseBase:
    """Serve the SPA shell; static assets are served by Nginx from the same directory."""
    index = ed_path("FRONTEND_DIR") / "index.html"
    if not index.exists():
        return HttpResponse(
            "Frontend bundle not found. In development run the Vite dev server.",
            status=404,
            content_type="text/plain; charset=utf-8",
        )
    response = FileResponse(index.open("rb"), content_type="text/html; charset=utf-8")
    response["Cache-Control"] = "no-store"
    return response


def api_not_found(request: HttpRequest, *args: Any, **kwargs: Any) -> JsonResponse:
    return JsonResponse(envelope("not_found", _("Not found.")), status=404)


def not_found(request: HttpRequest, exception: Exception | None = None) -> HttpResponse:
    if request.path.startswith("/api/"):
        return api_not_found(request)
    return HttpResponse("Not Found", status=404, content_type="text/plain; charset=utf-8")


def server_error(request: HttpRequest) -> HttpResponse:
    return JsonResponse(envelope("internal_error", _("An internal error occurred.")), status=500)


def csrf_failure(request: HttpRequest, reason: str = "") -> JsonResponse:
    return JsonResponse(
        envelope("auth.csrf_failed", _("CSRF verification failed. Reload the page.")),
        status=403,
    )
