"""API key scopes and sudo mode as DRF permissions."""

from __future__ import annotations

from typing import Any

from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request

from apps.accounts.errors import ApiKeyForbidden, SudoRequired
from apps.accounts.models import ApiKey
from apps.accounts.services import api_keys, session

# Modules that may never be reached with an API key (credential and key management).
SESSION_ONLY_MODULES = frozenset({"accounts"})


class ApiKeyScopePermission(BasePermission):
    """For API-key requests, require ``<module>:read|write`` (or ``*:…``) for the view's module."""

    def has_permission(self, request: Request, view: Any) -> bool:
        key = request.auth
        if not isinstance(key, ApiKey):
            return True
        module = getattr(view, "api_module", None)
        if module is None or module in SESSION_ONLY_MODULES:
            raise ApiKeyForbidden()
        if not api_keys.allows(key, module, write=request.method not in SAFE_METHODS):
            raise ApiKeyForbidden(
                details={
                    "required": f"{module}:{'read' if request.method in SAFE_METHODS else 'write'}"
                }
            )
        return True


class RequireSudo(BasePermission):
    """Sensitive actions need a re-authentication within the last N minutes (session only)."""

    def has_permission(self, request: Request, view: Any) -> bool:
        if isinstance(request.auth, ApiKey):
            raise ApiKeyForbidden()
        if session.sudo_until(request._request) is None:
            raise SudoRequired()
        return True


class SessionOnly(BasePermission):
    def has_permission(self, request: Request, view: Any) -> bool:
        if isinstance(request.auth, ApiKey):
            raise ApiKeyForbidden()
        return True
