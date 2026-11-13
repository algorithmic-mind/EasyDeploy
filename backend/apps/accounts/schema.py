"""OpenAPI security schemes for the custom authentication classes."""

from __future__ import annotations

from typing import Any

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class SessionAuthScheme(OpenApiAuthenticationExtension):
    target_class = "apps.accounts.authentication.SessionAuthentication"
    name = "sessionAuth"

    def get_security_definition(self, auto_schema: Any) -> dict[str, str]:
        return {"type": "apiKey", "in": "cookie", "name": "ed_session"}


class ApiKeyAuthScheme(OpenApiAuthenticationExtension):
    target_class = "apps.accounts.authentication.ApiKeyAuthentication"
    name = "apiKeyAuth"

    def get_security_definition(self, auto_schema: Any) -> dict[str, str]:
        return {"type": "apiKey", "in": "header", "name": "X-API-Key"}
