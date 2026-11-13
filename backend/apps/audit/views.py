from __future__ import annotations

import django_filters
from rest_framework import serializers, viewsets

from apps.audit.models import AuditLog, LoginLog


class AuditLogSerializer(serializers.ModelSerializer[AuditLog]):
    class Meta:
        model = AuditLog
        fields = [
            "id",
            "created_at",
            "actor",
            "actor_label",
            "action",
            "module",
            "resource_type",
            "resource_id",
            "ip",
            "user_agent",
            "request_id",
            "result",
            "changes",
            "details",
        ]


class LoginLogSerializer(serializers.ModelSerializer[LoginLog]):
    class Meta:
        model = LoginLog
        fields = ["id", "created_at", "username", "ip", "user_agent", "success", "reason"]


class AuditLogFilter(django_filters.FilterSet):
    since = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="gte")
    until = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = AuditLog
        fields = ["module", "action", "actor", "result", "resource_type", "resource_id"]


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet[AuditLog]):
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    filterset_class = AuditLogFilter
    search_fields = ["action", "actor_label", "resource_id", "ip"]
    ordering_fields = ["created_at", "action", "module"]
    api_module = "audit"


class LoginLogFilter(django_filters.FilterSet):
    since = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="gte")
    until = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = LoginLog
        fields = ["username", "success", "reason"]


class LoginLogViewSet(viewsets.ReadOnlyModelViewSet[LoginLog]):
    queryset = LoginLog.objects.all()
    serializer_class = LoginLogSerializer
    filterset_class = LoginLogFilter
    search_fields = ["username", "ip"]
    ordering_fields = ["created_at"]
    api_module = "audit"
