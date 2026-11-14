"""One DRF exception handler mapping every error to the envelope (§10.1)::

{"error": {"code": "...", "message": "...", "details": {...}, "request_id": "..."}}
"""

from __future__ import annotations

from typing import Any

import structlog
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from django.utils.translation import gettext as _
from rest_framework import exceptions as drf_exc
from rest_framework.response import Response

from apps.core.errors import EasyDeployError
from apps.core.request_context import current_request_id

log = structlog.get_logger(__name__)

_DRF_CODES: dict[type[Exception], str] = {
    drf_exc.NotAuthenticated: "auth.not_authenticated",
    drf_exc.AuthenticationFailed: "auth.authentication_failed",
    drf_exc.PermissionDenied: "permission_denied",
    drf_exc.NotFound: "not_found",
    drf_exc.MethodNotAllowed: "method_not_allowed",
    drf_exc.NotAcceptable: "not_acceptable",
    drf_exc.UnsupportedMediaType: "unsupported_media_type",
    drf_exc.Throttled: "throttled",
    drf_exc.ParseError: "parse_error",
}


def envelope(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "request_id": current_request_id(),
        }
    }


def _flatten(detail: Any) -> Any:
    if isinstance(detail, dict):
        return {k: _flatten(v) for k, v in detail.items()}
    if isinstance(detail, list):
        return [_flatten(v) for v in detail]
    return str(detail)


def exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    if isinstance(exc, EasyDeployError):
        return Response(envelope(exc.code, str(exc.message), exc.details), status=exc.status_code)
    if isinstance(exc, Http404):
        exc = drf_exc.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = drf_exc.PermissionDenied()

    if isinstance(exc, drf_exc.ValidationError):
        details = _flatten(exc.detail)
        if not isinstance(details, dict):
            details = {"non_field_errors": details}
        return Response(
            envelope("validation_error", _("Some fields are invalid."), details), status=400
        )
    if isinstance(exc, drf_exc.APIException):
        code = next((c for t, c in _DRF_CODES.items() if isinstance(exc, t)), "error")
        headers: dict[str, str] = {}
        if getattr(exc, "auth_header", None):
            headers["WWW-Authenticate"] = exc.auth_header  # type: ignore[attr-defined]
        wait = getattr(exc, "wait", None)
        if isinstance(exc, drf_exc.Throttled) and wait is not None:
            headers["Retry-After"] = str(int(wait))
        message = str(exc.detail)
        if isinstance(exc, drf_exc.PermissionDenied) and message.startswith("CSRF Failed"):
            code, message = "auth.csrf_failed", _("CSRF verification failed. Reload the page.")
        # 401 needs WWW-Authenticate; session-only APIs answer 403 like DRF does.
        return Response(envelope(code, message), status=exc.status_code, headers=headers)

    log.error("unhandled API error", view=str(context.get("view")), exc_info=exc)
    return Response(envelope("internal_error", _("An internal error occurred.")), status=500)
