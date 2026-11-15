"""Terminal endpoints under ``/api/v1/terminal/`` (§9.10). The PTY itself is a WebSocket."""

from __future__ import annotations

from typing import Any

from django.db.models import QuerySet
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView

from apps.accounts.permissions import RequireSudo
from apps.accounts.services import session
from apps.audit.services import record
from apps.core.permissions import IsPanelAdmin
from apps.panel.services import get_setting
from apps.terminal.models import Snippet
from apps.terminal.serializers import SnippetSerializer, TerminalCheckSerializer


class TerminalCheckView(APIView):
    """Confirms sudo mode before the UI opens ``/ws/terminal/...`` (a 403 triggers the prompt)."""

    api_module = "terminal"
    permission_classes = [IsAuthenticated, IsPanelAdmin, RequireSudo]

    @extend_schema(request=None, responses=TerminalCheckSerializer)
    def post(self, request: Request) -> Response:
        return Response(
            {
                "sudo_until": session.sudo_until(request._request),
                "idle_minutes": int(get_setting("terminal.idle_minutes")),
            }
        )


class SnippetViewSet(viewsets.ModelViewSet[Snippet]):
    api_module = "terminal"
    serializer_class = SnippetSerializer
    search_fields = ["name", "command", "description"]
    ordering_fields = ["name", "created_at"]
    filterset_fields: list[str] = []

    def get_queryset(self) -> QuerySet[Snippet]:
        return Snippet.objects.all()

    def _audit(self, action: str, snippet: Snippet, **extra: Any) -> None:
        record(
            f"terminal.snippet_{action}",
            request=self.request._request,
            resource_type="snippet",
            resource_id=str(snippet.pk),
            details={"name": snippet.name, **extra},
        )

    def perform_create(self, serializer: BaseSerializer[Snippet]) -> None:
        snippet = serializer.save(created_by=self.request.user)
        self._audit("created", snippet)

    def perform_update(self, serializer: BaseSerializer[Snippet]) -> None:
        snippet = serializer.save()
        self._audit("updated", snippet)

    def perform_destroy(self, instance: Snippet) -> None:
        self._audit("deleted", instance)
        instance.delete()
