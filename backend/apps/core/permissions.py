"""Permission classes. MVP has one role (admin); the layer is ready for RBAC (ADR-0019)."""

from __future__ import annotations

from typing import Any

from rest_framework.permissions import BasePermission
from rest_framework.request import Request


class IsPanelAdmin(BasePermission):
    def has_permission(self, request: Request, view: Any) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, "role", None) == "admin")
