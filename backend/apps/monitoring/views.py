from __future__ import annotations

from django.core.cache import cache
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.agent_client import get_agent
from apps.core.errors import ValidationFailed
from apps.monitoring import services

HistoryPoints = inline_serializer(
    "HistoryPoint",
    {
        "ts": serializers.DateTimeField(),
        **{f: serializers.FloatField() for f in services.AVERAGED},
    },
    many=True,
)


class CurrentMetricsView(APIView):
    """One-shot live metrics (rates relative to the last stored sample)."""

    api_module = "monitoring"

    @extend_schema(responses=inline_serializer("CurrentMetrics", {"data": serializers.DictField()}))
    def get(self, request: Request) -> Response:
        current = get_agent().call("system.metrics", actor=str(request.user.pk))
        return Response({"data": services.with_rates(current, cache.get(services.LAST_KEY))})


class HistoryView(APIView):
    api_module = "monitoring"

    @extend_schema(
        parameters=[
            OpenApiParameter("range", str, enum=list(services.RANGES), default="1h"),
        ],
        responses=inline_serializer(
            "MetricsHistory",
            {"range": serializers.CharField(), "points": HistoryPoints},
        ),
    )
    def get(self, request: Request) -> Response:
        range_key = request.query_params.get("range", "1h")
        if range_key not in services.RANGES:
            raise ValidationFailed(details={"range": [f"one of {', '.join(services.RANGES)}"]})
        return Response({"range": range_key, "points": services.history(range_key)})
