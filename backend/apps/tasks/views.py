from __future__ import annotations

from typing import Any

from django.db.models import QuerySet
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import record
from apps.tasks import services
from apps.tasks.models import Task
from apps.tasks.tasks import run_diagnostics


class TaskSerializer(serializers.ModelSerializer[Task]):
    class Meta:
        model = Task
        fields = [
            "id",
            "kind",
            "title_key",
            "title_params",
            "status",
            "progress",
            "progress_message",
            "resource_type",
            "resource_id",
            "parent",
            "created_by",
            "created_at",
            "started_at",
            "finished_at",
            "result",
            "error",
        ]


TaskAccepted = inline_serializer("TaskAccepted", {"task_id": serializers.UUIDField()})
TaskLog = inline_serializer(
    "TaskLog", {"lines": serializers.ListField(child=serializers.CharField())}
)


class TaskViewSet(viewsets.ReadOnlyModelViewSet[Task]):
    serializer_class = TaskSerializer
    filterset_fields = ["status", "kind", "resource_type", "resource_id", "parent"]
    search_fields = ["kind", "title_key", "resource_id"]
    ordering_fields = ["created_at", "finished_at", "status"]
    api_module = "tasks"

    def get_queryset(self) -> QuerySet[Task]:
        return Task.objects.all()

    @extend_schema(responses=TaskLog)
    @action(detail=True, methods=["get"])
    def log(self, request: Request, pk: str | None = None) -> Response:
        return Response({"lines": services.read_log(self.get_object())})

    @extend_schema(request=None, responses=TaskSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request: Request, pk: str | None = None) -> Response:
        task = self.get_object()
        if services.cancel(task):
            record(
                "tasks.cancelled",
                request=request._request,
                resource_type="task",
                resource_id=str(task.id),
            )
        task.refresh_from_db()
        return Response(TaskSerializer(task).data)


class DiagnosticsView(APIView):
    """Runs a self-check (database, agent) as a Task — exercises the whole task pipeline."""

    api_module = "tasks"

    @extend_schema(request=None, responses={202: TaskAccepted})
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        task = services.start_task(
            run_diagnostics,
            kind="panel.diagnostics",
            title_key="tasks.titles.diagnostics",
            user=request.user,
        )
        record("tasks.diagnostics_started", request=request._request, resource_id=str(task.id))
        return Response({"task_id": str(task.id)}, status=status.HTTP_202_ACCEPTED)
