from __future__ import annotations

from typing import Any

from django.conf import settings
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.panel.services import get_setting


class PanelInfoView(APIView):
    """Public panel branding for the login page (reachable only after the entrance)."""

    permission_classes = [AllowAny]
    authentication_classes: list[Any] = []

    @extend_schema(
        responses=inline_serializer(
            "PanelInfo",
            {
                "name": serializers.CharField(),
                "default_language": serializers.CharField(),
                "languages": serializers.ListField(child=serializers.CharField()),
            },
        ),
        auth=[],
    )
    def get(self, request: Request) -> Response:
        return Response(
            {
                "name": get_setting("panel.name"),
                "default_language": get_setting("panel.default_language"),
                "languages": [code for code, _name in settings.LANGUAGES],
            }
        )


class PanelVersionView(APIView):
    @extend_schema(
        responses=inline_serializer("PanelVersion", {"version": serializers.CharField()})
    )
    def get(self, request: Request) -> Response:
        return Response({"version": settings.VERSION})
