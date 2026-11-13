"""DRF authentication: API keys (``X-API-Key``) and CSRF-protected sessions."""

from __future__ import annotations

from typing import Any

from rest_framework import authentication, exceptions
from rest_framework.request import Request

from apps.accounts.models import ApiKey, User
from apps.accounts.services import api_keys
from apps.core.net import client_ip


class ApiKeyAuthentication(authentication.BaseAuthentication):
    header = "HTTP_X_API_KEY"

    def authenticate(self, request: Request) -> tuple[User, ApiKey] | None:
        raw = request.META.get(self.header)
        if not raw:
            return None
        ip = client_ip(request._request)
        key = api_keys.lookup(raw, ip)
        if key is None:
            raise exceptions.AuthenticationFailed("Invalid or expired API key.")
        api_keys.touch(key, ip)
        return key.user, key

    def authenticate_header(self, request: Request) -> str:
        # Makes DRF answer 401 (not 403) for unauthenticated requests.
        return "X-API-Key"


class SessionAuthentication(authentication.SessionAuthentication):
    """Session auth with CSRF enforcement (DRF default behavior, kept explicit)."""


def enforce_csrf(request: Request) -> None:
    """CSRF check for anonymous endpoints (login, 2FA) that DRF would otherwise exempt."""
    SessionAuthentication().enforce_csrf(request)


class CsrfProtectedMixin:
    def initial(self, request: Request, *args: Any, **kwargs: Any) -> None:
        enforce_csrf(request)
        super().initial(request, *args, **kwargs)  # type: ignore[misc]
