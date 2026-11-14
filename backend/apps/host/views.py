"""Host endpoints: processes, services (§9.11) and system logs (§9.14), all through the agent."""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import record
from apps.core.agent_client import get_agent

Any_ = inline_serializer("AgentResult", {"result": serializers.DictField()})


def _agent(request: Request, op: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    return get_agent().call(op, params or {}, actor=str(request.user.pk))


class HostView(APIView):
    api_module = "host"


class ProcessListView(HostView):
    @extend_schema(
        parameters=[
            OpenApiParameter("sort", str, enum=["cpu", "memory", "pid", "name"]),
            OpenApiParameter("limit", int),
        ],
        responses=inline_serializer(
            "ProcessList",
            {
                "processes": serializers.ListField(child=serializers.DictField()),
                "total": serializers.IntegerField(),
            },
        ),
    )
    def get(self, request: Request) -> Response:
        params: dict[str, Any] = {"sort": request.query_params.get("sort", "cpu")}
        if limit := request.query_params.get("limit"):
            params["limit"] = int(limit) if limit.isdigit() else limit
        return Response(_agent(request, "proc.list", params))


class ProcessDetailView(HostView):
    @extend_schema(
        operation_id="host_process_detail",
        responses=inline_serializer("ProcessDetail", {"process": serializers.DictField()}),
    )
    def get(self, request: Request, pid: int) -> Response:
        return Response(_agent(request, "proc.detail", {"pid": pid}))


class SignalSerializer(serializers.Serializer[Any]):
    signal = serializers.ChoiceField(choices=["TERM", "INT", "HUP", "KILL"], default="TERM")


class ProcessSignalView(HostView):
    @extend_schema(
        request=SignalSerializer,
        responses=inline_serializer(
            "SignalResult", {"pid": serializers.IntegerField(), "signal": serializers.CharField()}
        ),
    )
    def post(self, request: Request, pid: int) -> Response:
        data = SignalSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        result = _agent(
            request, "proc.signal", {"pid": pid, "signal": data.validated_data["signal"]}
        )
        record(
            "host.process_signal",
            request=request._request,
            resource_type="process",
            resource_id=str(pid),
            details={"signal": result["signal"]},
        )
        return Response(result)


class ServiceListView(HostView):
    @extend_schema(
        responses=inline_serializer(
            "ServiceList", {"units": serializers.ListField(child=serializers.DictField())}
        )
    )
    def get(self, request: Request) -> Response:
        return Response(_agent(request, "service.list"))


class ServiceActionSerializer(serializers.Serializer[Any]):
    action = serializers.ChoiceField(
        choices=["start", "stop", "restart", "reload", "enable", "disable"]
    )


class ServiceActionView(HostView):
    @extend_schema(
        request=ServiceActionSerializer,
        responses=inline_serializer(
            "ServiceActionResult",
            {
                "unit": serializers.CharField(),
                "action": serializers.CharField(),
                "active_state": serializers.CharField(),
            },
        ),
    )
    def post(self, request: Request, unit: str) -> Response:
        data = ServiceActionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        action = data.validated_data["action"]
        result = _agent(request, "service.action", {"unit": unit, "action": action})
        record(
            "host.service_action",
            request=request._request,
            resource_type="service",
            resource_id=result["unit"],
            details={"action": action, "active_state": result["active_state"]},
        )
        return Response(result)


JournalResponse = inline_serializer(
    "JournalResult", {"entries": serializers.ListField(child=serializers.DictField())}
)


class JournalView(HostView):
    """journald entries (System logs page, service details)."""

    @extend_schema(
        parameters=[
            OpenApiParameter("unit", str),
            OpenApiParameter("priority", int),
            OpenApiParameter("since", str, description="YYYY-MM-DD[ HH:MM[:SS]]"),
            OpenApiParameter("until", str),
            OpenApiParameter("grep", str),
            OpenApiParameter("lines", int),
        ],
        responses=JournalResponse,
    )
    def get(self, request: Request) -> Response:
        params: dict[str, Any] = {}
        for key in ("unit", "since", "until", "grep"):
            if value := request.query_params.get(key):
                params[key] = value
        for key in ("priority", "lines"):
            if (value := request.query_params.get(key)) not in (None, ""):
                params[key] = int(value) if str(value).isdigit() else value
        return Response(_agent(request, "journal.query", params))
