from __future__ import annotations

from django.conf import settings
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.agent_client import get_agent

SystemInfo = inline_serializer(
    "SystemInfo",
    {
        "hostname": serializers.CharField(),
        "os_name": serializers.CharField(),
        "os_version": serializers.CharField(),
        "kernel": serializers.CharField(),
        "arch": serializers.CharField(),
        "cpu_model": serializers.CharField(),
        "cpu_cores": serializers.IntegerField(),
        "cpu_threads": serializers.IntegerField(),
        "memory_total": serializers.IntegerField(),
        "swap_total": serializers.IntegerField(),
        "uptime_seconds": serializers.IntegerField(),
        "agent_version": serializers.CharField(),
        "panel_version": serializers.CharField(),
    },
)


class SystemInfoView(APIView):
    """Static host information for the Overview page (from agent ``system.info``)."""

    api_module = "dashboard"

    @extend_schema(responses=SystemInfo)
    def get(self, request: Request) -> Response:
        info = get_agent().call("system.info", actor=str(request.user.pk))
        info.pop("boot_time", None)
        info.pop("executor", None)
        info.pop("os_id", None)
        info["panel_version"] = settings.VERSION
        return Response(info)
